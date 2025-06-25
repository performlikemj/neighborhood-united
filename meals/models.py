from django.db import models
from pydantic import ValidationError
from chefs.models import Chef
from local_chefs.models import PostalCode, ChefPostalCode
import requests
import json
from django.conf import settings
from datetime import date, timedelta
from django.utils import timezone
from custom_auth.models import CustomUser, Address
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import migrations
from pgvector.django import VectorExtension
from pgvector.django import VectorField
from openai import OpenAI, OpenAIError
from meals.pydantic_models import ShoppingList as ShoppingListSchema, Instructions as InstructionsSchema, DietaryPreferencesSchema
from reviews.models import Review
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
import traceback
import numpy as np
import logging
import uuid
import dateutil.parser
from django.db.models import Avg, Sum, Count, Max, F, Q
from django.contrib.postgres.fields import ArrayField
import decimal
from django.db.models import UniqueConstraint

# Add status constants at the top of the file
# Shared statuses between ChefMealEvent and ChefMealOrder
STATUS_COMPLETED = 'completed'
STATUS_CANCELLED = 'cancelled'

# ChefMealEvent specific statuses
STATUS_SCHEDULED = 'scheduled'
STATUS_OPEN = 'open'
STATUS_CLOSED = 'closed'
STATUS_IN_PROGRESS = 'in_progress'
STATUS_COMPLETED = 'completed'
STATUS_CANCELLED = 'cancelled'

# ChefMealOrder specific statuses
STATUS_PLACED = 'placed'
STATUS_CONFIRMED = 'confirmed'
STATUS_REFUNDED = 'refunded'

logger = logging.getLogger(__name__)

OPENAI_API_KEY = getattr(settings, 'OPENAI_KEY', None)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

class Migration(migrations.Migration):
    operations = [
        VectorExtension()
    ]

class Ingredient(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=200)
    calories = models.FloatField(null=True, blank=True)  # Making all nutritional info blank=True
    fat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbohydrates = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    protein = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ingredient_embedding = VectorField(dimensions=1536, null=True)
    is_custom = models.BooleanField(default=True)  # Flag to distinguish custom ingredients from Spoonacular ones

    class Meta:
        unique_together = ('chef', 'name')
        indexes = [
            models.Index(fields=['name']),  # Add an index for name to improve search performance
            models.Index(fields=['chef', 'name']),  # Add a composite index for chef+name searches
        ]

    def __str__(self):
        # Start with the ingredient's name
        info = self.name

        # Add the chef's name
        info += f' by {self.chef.user.username}'

        # Add the calories, if available
        if self.calories is not None:
            info += f', {self.calories} kcal'

        return info


class MealType(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Dish(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='dishes')
    name = models.CharField(max_length=200)
    ingredients = models.ManyToManyField(Ingredient)
    featured = models.BooleanField(default=False)
    dish_embedding = VectorField(dimensions=1536, null=True)

    
    # Nutritional information
    calories = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbohydrates = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    protein = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        # First check if the object has been saved (has an ID)
        if self.id is None:
            return f"{self.name} (unsaved)"
        
        # Now it's safe to access many-to-many relationships
        try:
            ingredient_names = [i.name for i in self.ingredients.all()[:5]]
            ingredients_list = ', '.join(ingredient_names) if ingredient_names else "No ingredients"
            return f"{self.name} ({ingredients_list}{'...' if self.ingredients.count() > 5 else ''})"
        except Exception:
            # Fallback if anything goes wrong
            return f"{self.name} (ID: {self.id})"

    
    def update_nutritional_info(self):
        # Initialize nutritional values
        total_calories = 0
        total_fat = 0
        total_carbohydrates = 0
        total_protein = 0

        # Aggregate nutritional info from all ingredients
        for ingredient in self.ingredients.all():
            if ingredient.calories:
                total_calories += ingredient.calories
            if ingredient.fat:
                total_fat += ingredient.fat
            if ingredient.carbohydrates:
                total_carbohydrates += ingredient.carbohydrates
            if ingredient.protein:
                total_protein += ingredient.protein

        # Update dish nutritional information
        self.calories = total_calories
        self.fat = total_fat
        self.carbohydrates = total_carbohydrates
        self.protein = total_protein

    def save(self, *args, **kwargs):
        # For new instances, we need to save first to establish M2M relationships
        if not self.pk:
            super().save(*args, **kwargs)
            # After initial save, update nutritional info and save again
            self.update_nutritional_info()
            super().save(*args, **kwargs)
        else:
            # For existing instances, update nutritional info before saving
            self.update_nutritional_info()
            super().save(*args, **kwargs)



class PostalCodeManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            try:
                user_postal_code = user.address.input_postalcode
                user_country = user.address.country
                if user_postal_code and user_country:
                    # Get all chefs that serve this postal code with the user's country
                    chef_postal_codes = ChefPostalCode.objects.filter(
                        postal_code__code=user_postal_code,
                        postal_code__country=user_country
                    ).values_list('chef', flat=True)
                    return self.filter(chef__in=chef_postal_codes)
                return self.none()
            except (Address.DoesNotExist, AttributeError):
                return self.none()
        return self.none()

def clean_preference_name(value):
    if any(char in value for char in '{}[]"\''):
        raise ValidationError('Preference name cannot contain brackets or quotes')
    return value

class DietaryPreference(models.Model):
    name = models.CharField(
        max_length=100, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[^{}\[\]"\']*$',
                message="Name cannot contain brackets or quotes",
                code="invalid_name"
            ),
            clean_preference_name
        ]
    )

    def __str__(self):
        return self.name


class DietaryPreferenceManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            user_prefs = user.dietary_preferences.all()  # Assuming this is a many-to-many relationship

            # If "Everything" is selected and there are no other preferences, return all meals
            if user_prefs.filter(name='Everything').exists() and user_prefs.count() == 1:
                return super().get_queryset()
            
            # If "Everything" is selected along with other preferences, ignore "Everything" and filter by other preferences
            if user_prefs.filter(name='Everything').exists() and user_prefs.count() > 1:
                user_prefs = user_prefs.exclude(name='Everything')
            
            # Otherwise, filter meals based on the remaining user's dietary preferences
            return super().get_queryset().filter(dietary_preferences__in=user_prefs)
        
        # If no preferences are set, return all meals (or adjust according to your logic)
        return super().get_queryset()


class CustomDietaryPreference(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    allowed = models.JSONField(default=list, blank=True)
    excluded = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name
    
class Meal(models.Model):
    MEAL_TYPE_CHOICES = [
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner'),
    ]
    name = models.CharField(max_length=200, default='Meal Name')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_meals') 
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='meals', null=True, blank=True)
    image = models.ImageField(upload_to='meals/', blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)  # The first day the meal is available
    dishes = models.ManyToManyField(Dish, blank=True)
    dietary_preferences = models.ManyToManyField(DietaryPreference, blank=True, related_name='meals')
    custom_dietary_preferences = models.ManyToManyField(
        CustomDietaryPreference, blank=True, related_name='meals'
    )    
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)  # Adding price field
    description = models.TextField(blank=True)  # Adding description field
    review_summary = models.TextField(blank=True, null=True)  # Adding summary field
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='Dinner')
    reviews = GenericRelation('reviews.Review', related_query_name='meal_reviews')
    objects = models.Manager()  # The default manager
    postal_objects = PostalCodeManager()  # Attach the custom manager
    dietary_objects = DietaryPreferenceManager()  # Attach the dietary preference manager
    meal_embedding = VectorField(dimensions=1536, null=True)
    macro_info = models.JSONField(blank=True, null=True)
    youtube_videos = models.JSONField(blank=True, null=True)

    class Meta:
        constraints = [
            # Your existing constraints here
            models.UniqueConstraint(fields=['name', 'creator'], condition=models.Q(creator__isnull=False), name='unique_meal_per_creator'),
            models.UniqueConstraint(fields=['chef', 'start_date', 'meal_type'], condition=models.Q(chef__isnull=False), name='unique_chef_meal_per_date_and_type')
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if the meal is new

        # Validate required fields for chef-created meals
        if self.chef and is_new:
            if self.start_date is None or self.price is None or not self.image:
                raise ValueError('start date, price, and image must be provided when a chef creates a meal')

        # Always save the instance first to ensure it has an ID
        super(Meal, self).save(*args, **kwargs)

        if not self.created_date:
            self.created_date = timezone.now()
        
        # For chef-created meals, validate dishes after save (so M2M can be established)
        # Skip this validation for new meals since dishes are likely being added after save
        if self.chef and not is_new and not self.dishes.exists():
            raise ValueError('At least one dish must be provided when a chef creates a meal')

    def generate_messages(self):
        """
        Generate the list of messages for the OpenAI API based on the meal's details.
        This returns an array of message objects.
        """
        # Gather dietary preferences
        dietary_prefs = [pref.name for pref in self.dietary_preferences.all()]
        custom_dietary_prefs = [pref.name for pref in self.custom_dietary_preferences.all()]
        all_dietary_prefs = dietary_prefs + custom_dietary_prefs
        dietary_prefs_str = ', '.join(all_dietary_prefs) if all_dietary_prefs else "None"

        prompt = (
            f"Analyze the following meal and determine its dietary preferences.\n\n"
            f"Meal Name: {self.name}\n"
            f"Description: {self.description}\n"
            f"Dishes: {', '.join(dish.name for dish in self.dishes.all())}\n"
            f"Ingredients: {', '.join(ingredient.name for dish in self.dishes.all() for ingredient in dish.ingredients.all())}\n"
            f"Existing Dietary Preferences: {dietary_prefs_str}\n"
            f"Please list all additional applicable dietary preferences (e.g., Vegetarian, Gluten-Free) for this meal in the following JSON format exactly as shown:\n"
            f"{{\n"
            f'  "dietary_preferences": [\n'
            f'    "Preference1",\n'
            f'    "Preference2"\n'
            f'  ]\n'
            f"}}"
        )

        # The messages array contains a system and a user message
        messages = [
            {"role": "developer", "content": (
                """
                Analyze the following meal details and determine its additional applicable dietary preferences.

                - Meal Name: [Provide the name of the meal here]
                - Description: [Provide a brief description of the meal here]
                - Dishes: [List the names of all dishes included in the meal]
                - Ingredients: [List all ingredients of the meal, separated by commas]
                - Existing Dietary Preferences: [List any existing dietary preferences associated with the meal]

                Include dietary preferences such as Vegetarian, Gluten-Free, Vegan, etc. Determine these from the meal details provided.

                # Steps

                1. **Analyze Meal Details:**
                - Review the meal name, description, dishes, and ingredients to understand the food components.
                - Note any existing dietary preferences to supplement them with new findings.

                2. **Determine Dietary Preferences:**
                - Identify if the meal is suitable for common dietary preferences like Vegetarian, Vegan, Gluten-Free, Dairy-Free, Nut-Free, etc.
                - Consider the ingredients and preparation methods described to identify potential new dietary preferences.

                3. **Compose Dietary Preferences:**
                - Prepare a list of all applicable dietary preferences for the meal.

                # Output Format

                The response should be in JSON format, listing all additional applicable dietary preferences:

                ```json
                {
                "dietary_preferences": [
                    "Preference1",
                    "Preference2"
                ]
                }
                ```

                # Examples

                **Input:**
                - Meal Name: "Quinoa Salad"
                - Description: "A healthy mix of quinoa, roasted vegetables, and a light lemon dressing."
                - Dishes: "Salad"
                - Ingredients: "quinoa, bell peppers, zucchini, lemon juice, olive oil, salt, pepper"
                - Existing Dietary Preferences: "Vegetarian"

                **Output:**
                ```json
                {
                "dietary_preferences": [
                    "Vegan",
                    "Gluten-Free"
                ]
                }
                ```

                (Note: Ensure real examples are detailed and comprehensive, using actual meal data.)
                """
            )},
            {"role": "user", "content": prompt}
        ]
        return messages


    def parse_dietary_preferences(self, response_content):
        """
        Parse the dietary preferences returned by OpenAI into a list.
        The response_content is expected to be a JSON string with a key "dietary_preferences".
        """
        try:
            # Parse the JSON string
            parsed_response = json.loads(response_content)
            # Extract the dietary preferences list
            dietary_prefs = parsed_response.get('dietary_preferences', [])
            if not isinstance(dietary_prefs, list):
                logger.error(f"'dietary_preferences' is not a list in response: {parsed_response}")
                return []
            return dietary_prefs
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            logger.error(f"Response content: {response_content}")
            return []


    def average_rating(self):
        """Calculate the average rating of the meal from its reviews."""
        qs = self.reviews.all()
        if not qs.exists():
            return None
        return qs.aggregate(models.Avg('rating'))['rating__avg']
    
    def is_chef_created(self):
        """Check if this meal was created by a chef."""
        return self.chef is not None
    
    def get_upcoming_events(self):
        """Get upcoming chef meal events for this meal."""
        from django.utils import timezone
        from django.db.models import F
        
        if not self.chef:
            return []
            
        now = timezone.now()
        return self.events.filter(
            event_date__gte=now.date(),
            status__in=['scheduled', 'open'],
            order_cutoff_time__gt=now,
            orders_count__lt=F('max_orders')
        ).order_by('event_date', 'event_time')

    def __str__(self):
        creator_info = self.chef.user.username if self.chef else (self.creator.username if self.creator else 'No creator')

        dietary_prefs = "No preferences"
        custom_dietary_prefs = "No custom preferences"
        if self.pk:
            try:
                dietary_prefs_list = [pref.name for pref in self.dietary_preferences.all()] or ["No preferences"]
                dietary_prefs = ", ".join(dietary_prefs_list)
            except Exception as e:
                dietary_prefs = "Error retrieving preferences"
                logger.error(f"Error accessing dietary preferences for meal '{self.name}': {e}")
            
            try:
                cdp_list = [pref.name for pref in self.custom_dietary_preferences.all()] or ["No custom preferences"]
                custom_dietary_prefs = ", ".join(cdp_list)
            except Exception as e:
                custom_dietary_prefs = "Error retrieving custom dietary preferences"
                logger.error(f"Error accessing custom dietary preferences for meal '{self.name}': {e}")

        description_str = f'Description: {self.description[:100]}...' if self.description else ''
        review_summary_str = f'Review Summary: {self.review_summary[:100]}...' if self.review_summary else ''
        return (
            f'{self.name} by {creator_info} (Preferences: {dietary_prefs}, Custom Preferences: {custom_dietary_prefs}). '
            f'{description_str} {review_summary_str} Start Date: {self.start_date}, Price: {self.price}'
        )

    def trimmed_embedding(self, length=10):
        """Return a trimmed version of the meal embedding."""
        # Ensure the embedding is a list and trim it to the specified length
        return self.meal_embedding[:length] if self.meal_embedding else []


    def is_available(self, week_shift=0):
        if not self.chef:
            return False

        week_shift = int(week_shift)  # User's ability to plan for future weeks
        current_date = timezone.now().date() + timedelta(weeks=week_shift) 
        return self.start_date <= current_date  

    def can_be_ordered(self):
        if not self.chef:
            return False

        """
        Check if the meal can be ordered (at least a day in advance).
        """
        current_date = timezone.now().date()
        return self.start_date > current_date

class MealPlan(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    meal = models.ManyToManyField(Meal, through='MealPlanMeal')
    reviews = GenericRelation('reviews.Review', related_query_name='mealplan_reviews')
    created_date = models.DateTimeField(auto_now_add=True)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    is_approved = models.BooleanField(default=False)  # Track if the meal plan is approved
    has_changes = models.BooleanField(default=False)  # Track if there are changes to the plan
    approval_token = models.UUIDField(default=uuid.uuid4, unique=True)   
    reminder_sent = models.BooleanField(default=False)
    approval_email_sent = models.BooleanField(default=False)
    instacart_url = models.URLField(max_length=1000, blank=True, null=True, help_text="URL to the Instacart shopping list for this meal plan")
    order = models.OneToOneField(
        'Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='associated_meal_plan'
    )

    MEAL_PREP_CHOICES = [
        ('daily', 'Daily Meal Instructions'),
        ('one_day_prep', 'One-Day Meal Prep'),
    ]
    meal_prep_preference = models.CharField(
        max_length=15,
        choices=MEAL_PREP_CHOICES,
        default='daily',
        help_text='User preference for this week.',
    )

    class Meta:
        unique_together = ('user', 'week_start_date', 'week_end_date')

    def clean(self):
        # Custom validation to ensure start_date is before end_date
        if self.week_start_date and self.week_end_date:
            if self.week_start_date >= self.week_end_date:
                raise ValidationError(('The start date must be before the end date.'))

        # Call the parent class's clean method
        super().clean()

    def __str__(self):
        return f"{self.user.username}'s MealPlan for {self.week_start_date} to {self.week_end_date}"

    def save(self, *args, **kwargs):
        was_approved = self.is_approved  # Track approval state before saving

        super().save(*args, **kwargs)  # Save normally

    def average_meal_rating(self):
        """
        Calculate the average rating of all meals in this meal plan.
        """
        meals = self.meal.all()
        if not meals.exists():
            return None
        ratings = [m.average_rating() for m in meals if m.average_rating() is not None]
        if not ratings:
            return None
        return sum(ratings) / len(ratings)
        
class MealPlanInstruction(models.Model):
    meal_plan = models.ForeignKey('MealPlan', on_delete=models.CASCADE)
    instruction_text = models.TextField()
    date = models.DateField()
    is_bulk_prep = models.BooleanField(default=False)

    def __str__(self):
        return f"Instruction for {self.meal_plan.user.username} on {self.date}"
    
class MealPlanMeal(models.Model):
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    MEAL_TYPE_CHOICES = [
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner'),
    ]

    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    meal_date = models.DateField(null=True, blank=True)
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='Dinner')
    already_paid = models.BooleanField(default=False, help_text="Flag indicating this meal was paid for in a previous order")

    class Meta:
        # Ensure a meal is unique per day within a specific meal plan, and meal type
        unique_together = ('meal_plan', 'day', 'meal_type')

    def __str__(self):
        meal_name = self.meal.name if self.meal else 'Unknown Meal'
        return f"{meal_name} on {self.day} ({self.meal_type}) for {self.meal_plan}"

    def save(self, *args, **kwargs):
        # Call super().save() before making changes to update meal plan
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # If this is a new MealPlanMeal or an update, we should update the MealPlan
        if is_new or self.meal_plan.has_changes:
            self.meal_plan.is_approved = False
            self.meal_plan.has_changes = True
            self.meal_plan.save()

    def delete(self, *args, **kwargs):
        try:
            # Add logging to trace what's happening
            logger.info(f"Attempting to delete MealPlanMeal for {self.meal_plan} on {self.day} ({self.meal_type}).")

            # Access and save the meal_plan before deletion
            meal_plan = self.meal_plan

            # Perform the deletion
            super().delete(*args, **kwargs)
            logger.info(f"Successfully deleted MealPlanMeal for {self.meal_plan} on {self.day} ({self.meal_type}).")

            # Update meal plan status and save changes
            meal_plan.is_approved = False
            meal_plan.has_changes = True
            meal_plan.save()
            logger.info(f"Updated MealPlan {meal_plan} after deleting associated MealPlanMeal.")

        except Exception as e:
            # Log the error with a detailed traceback
            logger.error(f"Error occurred while deleting MealPlanMeal: {e}")
            logger.error(traceback.format_exc())  # This will add the full traceback to the logs
            raise

class ShoppingList(models.Model):
    meal_plan = models.OneToOneField(MealPlan, on_delete=models.CASCADE, related_name='shopping_list')
    items = models.JSONField()  # Store the shopping list items as a JSON object
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Shopping List for {self.meal_plan}'

    def update_items(self, items):
        """Update the shopping list items."""
        self.items = items
        self.save()


class Instruction(models.Model):
    meal_plan_meal = models.OneToOneField(MealPlanMeal, on_delete=models.CASCADE, related_name='instructions', null=True, blank=True)
    content = models.JSONField()  # Store the instructions as a JSON object
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Instructions for {self.meal_plan_meal}'

    def update_content(self, content):
        """Update the instruction content."""
        self.content = content
        self.save()

class MealPlanThread(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    thread_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MealPlanThread for {self.user.username} with thread_id {self.thread_id}"

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class PantryItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Canned', 'Canned'),
        ('Dry', 'Dry Goods'),
    ]

    UNIT_CHOICES = [
        ('oz', 'Ounces'),
        ('lb', 'Pounds'),
        ('g', 'Grams'),
        ('kg', 'Kilograms'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='pantry_items')
    item_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)  
    marked_as_used = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True)
    expiration_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='Canned')
    notes = models.TextField(blank=True, null=True)
    weight_per_unit = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="How many ounces or grams per can/bag? (e.g. 14.5 for a 14.5 oz can.)"
    )
    weight_unit = models.CharField(
        max_length=5,
        choices=UNIT_CHOICES,
        blank=True, 
        null=True,
        help_text="The unit for weight_per_unit, e.g. 'oz', 'lb', 'g', etc."
    )

    class Meta:
        indexes = [
            models.Index(fields=['expiration_date']),
        ]
        unique_together = ('user', 'item_name', 'expiration_date')

    def is_expiring_soon(self):
        if self.expiration_date:
            days_until_expiration = (self.expiration_date - timezone.now().date()).days
            return days_until_expiration <= 7  # Consider items expiring within 7 days
        return False  # If no expiration date, assume it's not expiring soon

    def is_expired(self):
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False  # If no expiration date, assume it's not expired
    
    def available_quantity(self) -> int:
        return self.quantity - self.used_count
    
    def is_fully_used(self) -> bool:
        return self.available_quantity <= 0
    
    def __str__(self):
        return f"{self.item_name} (total={self.quantity}, used={self.used_count})"
    
class MealPlanMealPantryUsage(models.Model):
    """
    Captures how much of a given pantry item is used by a particular MealPlanMeal.
    """
    meal_plan_meal = models.ForeignKey('MealPlanMeal', on_delete=models.CASCADE, related_name='pantry_usage')
    pantry_item = models.ForeignKey('PantryItem', on_delete=models.CASCADE)
    quantity_used = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    usage_unit = models.CharField(
        max_length=5,
        choices=PantryItem.UNIT_CHOICES,
        blank=True, 
        null=True,
        help_text="Unit for quantity_used, e.g. 'oz', 'g', etc."
    )

    def __str__(self):
        return f"{self.meal_plan_meal} uses {self.quantity_used} {self.usage_unit} of {self.pantry_item.item_name}"
    
class Cart(models.Model):
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    meal = models.ManyToManyField(Meal)
    meal_plan = models.ForeignKey(MealPlan, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f'Cart for {self.customer.username}'
    

class Order(models.Model):
    # in your Order model
    ORDER_STATUS_CHOICES = [
        ('Placed', 'Placed'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Refunded', 'Refunded'),
        ('Delayed', 'Delayed')
    ]

    DELIVERY_CHOICES = [
        ('Pickup', 'Pickup'),
        ('Delivery', 'Delivery'),
    ]

    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    address = models.ForeignKey('custom_auth.Address', null=True, on_delete=models.SET_NULL)
    meal = models.ManyToManyField(Meal, through='OrderMeal')
    order_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='Placed')
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_CHOICES, default='Pickup')
    special_requests = models.TextField(blank=True)
    is_paid = models.BooleanField(default=False)
    meal_plan = models.ForeignKey(MealPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name='related_orders')
    
    # Stripe payment tracking
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Checkout Session ID")

    def save(self, *args, **kwargs):
        if not self.order_date:  # only update if order_date is not already set
            self.order_date = timezone.now()
        self.updated_at = timezone.now()  # always update the last updated time
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Order {self.id} - {self.customer.username}'

    def total_price(self):
        """
        Calculate the total price of the order, using OrderMeal's get_price method
        to ensure consistent pricing.
        """
        total = decimal.Decimal('0.00')  # Use Decimal for currency
        # Fetch related objects efficiently
        order_meals = self.ordermeal_set.select_related('meal', 'chef_meal_event', 'meal_plan_meal').all()

        for order_meal in order_meals:
            # Skip meals that have already been paid for
            meal_plan_meal = order_meal.meal_plan_meal
            if hasattr(meal_plan_meal, 'already_paid') and meal_plan_meal.already_paid:
                # Skip this item in the total calculation
                continue
                
            # Get the price using the OrderMeal's get_price method for consistency
            item_price = order_meal.get_price()
            
            # Ensure quantity is valid (should be integer, but convert for safety)
            quantity = decimal.Decimal(order_meal.quantity) if order_meal.quantity is not None else decimal.Decimal('0')
            total += item_price * quantity

        return total

   
class SystemUpdate(models.Model):
    subject = models.CharField(max_length=200)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey('custom_auth.CustomUser', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-sent_at']

class ChefMealEvent(models.Model):
    """
    Represents a specific meal offering by a chef that customers can order.
    
    This model allows chefs to schedule when they'll prepare a particular meal
    and make it available to customers. For example, a chef might offer their
    signature lasagna on Friday evening from 6-8pm with orders needed by Thursday.
    
    The dynamic pricing encourages group orders - as more customers order the same meal,
    the price decreases for everyone, benefiting both the chef (more orders) and
    customers (lower prices).
    """
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_OPEN, 'Open for Orders'),
        (STATUS_CLOSED, 'Closed for Orders'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='meal_events')
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='events')
    event_date = models.DateField(help_text="The date when the chef will prepare and serve this meal")
    event_time = models.TimeField(help_text="The time when the meal will be available for pickup/delivery")
    order_cutoff_time = models.DateTimeField(help_text="Deadline for placing orders (e.g., 24 hours before event)")
    
    max_orders = models.PositiveIntegerField(help_text="Maximum number of orders the chef can fulfill")
    min_orders = models.PositiveIntegerField(default=1, help_text="Minimum number of orders needed to proceed")
    
    base_price = models.DecimalField(max_digits=6, decimal_places=2, 
                                   help_text="Starting price per order")
    current_price = models.DecimalField(max_digits=6, decimal_places=2, 
                                      help_text="Current price based on number of orders")
    min_price = models.DecimalField(max_digits=6, decimal_places=2, 
                                  help_text="Minimum price per order")
    
    orders_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    description = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['event_date', 'event_time']
        unique_together = ('chef', 'meal', 'event_date', 'event_time', 'status')
    
    def __str__(self):
        return f"{self.meal.name} by {self.chef.user.username} on {self.event_date} at {self.event_time}"
    
    def get_chef_timezone(self):
        """
        Get the chef's timezone. Defaults to UTC if not set.
        """
        return self.chef.user.timezone if hasattr(self.chef.user, 'timezone') else 'UTC'
    
    def get_chef_timezone_object(self):
        """
        Get the chef's timezone as a pytz timezone object.
        """
        import pytz
        timezone_str = self.get_chef_timezone()
        try:
            return pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            return pytz.UTC
    
    def to_chef_timezone(self, dt):
        """
        Convert a datetime from UTC to the chef's timezone.
        """
        if not dt:
            return dt
            
        if not timezone.is_aware(dt):
            dt = timezone.make_aware(dt)
            
        return dt.astimezone(self.get_chef_timezone_object())
    
    def from_chef_timezone(self, dt):
        """
        Convert a datetime from the chef's timezone to UTC for storage.
        """
        if not dt:
            return dt
            
        # If the datetime is naive, assume it's in the chef's timezone and make it aware
        if not timezone.is_aware(dt):
            chef_tz = self.get_chef_timezone_object()
            dt = chef_tz.localize(dt)
            
        # Convert to UTC
        return dt.astimezone(timezone.utc)
    
    def get_event_datetime(self):
        """
        Combine event_date and event_time into a timezone-aware datetime.
        """
        import datetime
        if not self.event_date or not self.event_time:
            return None
            
        # Combine date and time
        naive_dt = datetime.datetime.combine(self.event_date, self.event_time)
        
        # Make it timezone-aware in the chef's timezone
        chef_tz = self.get_chef_timezone_object()
        return chef_tz.localize(naive_dt)
    
    def get_cutoff_time_in_chef_timezone(self):
        """
        Get the order cutoff time in the chef's timezone.
        """
        if not self.order_cutoff_time:
            return None
            
        return self.to_chef_timezone(self.order_cutoff_time)
    
    def save(self, *args, **kwargs):
        # If this is a new event, set the current price to the base price
        if not self.pk:
            self.current_price = self.base_price
        else:
            # If this is an existing event with orders, prevent price changes
            try:
                original = ChefMealEvent.objects.get(pk=self.pk)
                if original.orders_count > 0:
                    # Prevent changes to any price fields once orders exist
                    self.base_price = original.base_price
                    self.min_price = original.min_price
                    # Allow current_price changes only through the update_price method
                    # (for automatic group discounts)
                    if not kwargs.get('update_fields') or 'current_price' not in kwargs.get('update_fields', []):
                        self.current_price = original.current_price
            except ChefMealEvent.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)
    
    def update_price(self):
        """
        Update the price based on the number of orders.
        As more orders come in, the price decreases until it reaches min_price.
        
        The pricing algorithm works as follows:
        1. For each order after the first one, the price decreases by 5% of the difference 
           between base_price and min_price
        2. The price will never go below the min_price
        3. When price changes, all existing orders are updated to the new lower price
        
        This creates a win-win situation where:
        - It incentivizes customers to share/promote the meal to get more orders
        - Everyone benefits when more people join (price drops for all)
        - The chef benefits from higher volume
        - The minimum price protects the chef's profit margin
        """
        if self.orders_count <= 1:
            return
        
        # Simple pricing algorithm:
        # For each order after the first one, reduce price by 5% of the difference 
        # between base_price and min_price, until min_price is reached
        price_range = float(self.base_price) - float(self.min_price)
        discount_per_order = price_range * 0.05  # 5% of the range
        
        # Calculate the discount based on number of orders
        total_discount = discount_per_order * (self.orders_count - 1)
        
        # Don't go below min_price
        new_price = max(float(self.base_price) - total_discount, float(self.min_price))
        
        # Save the new price
        self.current_price = new_price
        self.save(update_fields=['current_price'])
        
        # Update pricing for all existing orders
        from decimal import Decimal
        ChefMealOrder.objects.filter(meal_event=self, status__in=['placed', 'confirmed']).update(
            price_paid=Decimal(new_price)
        )
    
    def is_available_for_orders(self):
        """Check if the event is open for new orders"""
        # Get current time in UTC
        now_utc = timezone.now()
        
        # Get chef's timezone
        chef_tz = self.get_chef_timezone_object()
        
        # Convert current time to chef's timezone
        now = now_utc.astimezone(chef_tz)
        
        # Make sure order_cutoff_time is a datetime object
        cutoff_time = self.order_cutoff_time
        if isinstance(cutoff_time, str):
            # If it's a string, parse it and make it timezone-aware
            try:
                cutoff_time = dateutil.parser.parse(cutoff_time)
                if not timezone.is_aware(cutoff_time):
                    cutoff_time = timezone.make_aware(cutoff_time)
            except Exception:
                # If parsing fails, default to not available
                return False
        
        # Convert cutoff time to chef's timezone for comparison
        if cutoff_time:
            cutoff_time = cutoff_time.astimezone(chef_tz)
        
        # Explicitly check all conditions that would make the event unavailable
        if self.status in [STATUS_CLOSED, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CANCELLED]:
            return False
            
        # Only SCHEDULED and OPEN statuses are valid for ordering
        if self.status not in [STATUS_SCHEDULED, STATUS_OPEN]:
            return False
            
        # Check time and capacity constraints
        if now >= cutoff_time:
            return False
            
        if self.orders_count >= self.max_orders:
            return False
            
        # If we passed all checks, the event is available
        return True
    
    def cancel(self):
        """Cancel the event and all associated orders"""
        self.status = STATUS_CANCELLED
        self.save()
        # Cancel all orders and initiate refunds
        self.orders.filter(status__in=[STATUS_PLACED, STATUS_CONFIRMED]).update(status=STATUS_CANCELLED)
        # Refund logic would be implemented separately

class ChefMealOrder(models.Model):
    """
    Represents a customer's order for a specific ChefMealEvent.
    Linked to the main Order model for unified order history.
    """
    STATUS_CHOICES = [
        (STATUS_PLACED, 'Placed'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
        (STATUS_COMPLETED, 'Completed')
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='chef_meal_orders')
    meal_event = models.ForeignKey(ChefMealEvent, on_delete=models.CASCADE, related_name='orders')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Add this link to tie the ChefMealOrder to the specific meal plan slot
    meal_plan_meal = models.ForeignKey(
        MealPlanMeal, 
        on_delete=models.SET_NULL, # Or CASCADE if a deleted slot should remove the order item
        null=True, 
        blank=True, 
        related_name='chef_order_item' # Use a specific related_name
    ) 

    quantity = models.PositiveIntegerField(default=1)
    # price_paid should store the *total* price paid for the quantity at the time of purchase/confirmation
    unit_price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    price_paid = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True) # Allow null initially
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    
    # Stripe payment details
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_refund_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Price adjustment tracking
    price_adjustment_processed = models.BooleanField(default=False, help_text="Whether price adjustment/refund has been processed")
    
    special_requests = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['customer', 'meal_event'],
                condition=Q(status__in=['placed', 'confirmed']),
                name='uniq_active_order_per_event'
            )
        ]
        ordering = ['-created_at']
    
    # Add property for backward compatibility with new service code
    @property
    def payment_intent_id(self):
        return self.stripe_payment_intent_id
    
    @payment_intent_id.setter
    def payment_intent_id(self, value):
        self.stripe_payment_intent_id = value
    
    def __str__(self):
        return f"Order #{self.id} - {self.meal_event.meal.name} by {self.customer.username}"
    
    def mark_as_paid(self):
        """
        Mark the order as paid and update the event's order count and pricing.
        This should ONLY be called when payment is confirmed.
        """
        if self.status == STATUS_PLACED:
            # Update status to confirmed
            self.status = STATUS_CONFIRMED
            self.save(update_fields=['status'])
            
            # Increment the orders count on the event
            # Ensure quantity is not None before using it
            quantity_to_add = self.quantity if self.quantity is not None else 1
            self.meal_event.orders_count += quantity_to_add
            self.meal_event.save() # Save the event after updating count
            
            # Update the price for all orders on the event
            self.meal_event.update_price()
            
            return True
        return False
    
    def cancel(self):
        """Cancel the order and update the event's orders count"""
        if self.status in [STATUS_PLACED, STATUS_CONFIRMED]:
            previous_status = self.status
            self.status = STATUS_CANCELLED
            self.save()
            
            # Only decrement the count if this was a confirmed (paid) order
            if previous_status == STATUS_CONFIRMED:
                # Decrement the orders count on the event
                # Ensure quantity is not None before using it
                quantity_to_remove = self.quantity if self.quantity is not None else 1
                self.meal_event.orders_count = max(0, self.meal_event.orders_count - quantity_to_remove) # Prevent negative count
                self.meal_event.save() # Save the event after updating count
                
                # Update pricing
                self.meal_event.update_price()
            
            # Refund logic would be implemented separately
            return True
        return False

class ChefMealReview(models.Model):
    """Reviews for chef meals with ratings and comments"""
    chef_meal_order = models.OneToOneField(ChefMealOrder, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='meal_reviews')
    meal_event = models.ForeignKey(ChefMealEvent, on_delete=models.CASCADE, related_name='reviews')
    
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('customer', 'meal_event')
    
    def __str__(self):
        return f"Review by {self.customer.username} for {self.meal_event.meal.name}"

class OrderMeal(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    meal_plan_meal = models.ForeignKey(MealPlanMeal, on_delete=models.CASCADE)  # Existing field
    chef_meal_event = models.ForeignKey(ChefMealEvent, null=True, blank=True, on_delete=models.SET_NULL) 
    quantity = models.IntegerField()
    
    # Store the price at the time of order creation to avoid discrepancies
    price_at_order = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                         help_text="Price at the time of order creation")

    def __str__(self):
        return f'{self.meal} - {self.order} on {self.meal_plan_meal.day}'
        
    def save(self, *args, **kwargs):
        # If this is a new order meal, set the price_at_order
        if not self.pk:
            # For chef meal events, always use the current_price from the event
            if self.chef_meal_event and self.chef_meal_event.current_price is not None:
                self.price_at_order = self.chef_meal_event.current_price
            # Otherwise use the meal price
            elif self.meal and self.meal.price is not None:
                self.price_at_order = self.meal.price
                
        super().save(*args, **kwargs)
    
    def get_price(self):
        """
        Returns the price for this order meal, prioritizing:
        1. Stored price_at_order if available
        2. Current chef_meal_event price if linked
        3. Base meal price as fallback
        """
        if self.price_at_order is not None:
            return self.price_at_order
        elif self.chef_meal_event and self.chef_meal_event.current_price is not None:
            return self.chef_meal_event.current_price
        elif self.meal and self.meal.price is not None:
            return self.meal.price
        return decimal.Decimal('0.00')  # Default fallback

# StripeConnect model to store chef's Stripe connection information
class StripeConnectAccount(models.Model):
    chef = models.OneToOneField(Chef, on_delete=models.CASCADE, related_name='stripe_account')
    stripe_account_id = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Stripe account for {self.chef.user.username}"

# Add platform fee configuration
class PlatformFeeConfig(models.Model):
    """Configures the platform fee percentage for chef meal orders"""
    fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ],
        help_text="Platform fee percentage (0-100)"
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Platform Fee: {self.fee_percentage}%"
    
    def save(self, *args, **kwargs):
        # Ensure only one active config exists
        if self.active:
            PlatformFeeConfig.objects.filter(active=True).exclude(pk=self.pk).update(active=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_fee(cls):
        """Get the currently active fee percentage"""
        try:
            return cls.objects.filter(active=True).first().fee_percentage
        except AttributeError:
            # Return a default value if no active fee config exists
            return 10  # 10% default

# Payment audit log
class PaymentLog(models.Model):
    """Logs all payment-related actions for auditing"""
    ACTION_CHOICES = [
        ('charge', 'Charge'),
        ('refund', 'Refund'),
        ('payout', 'Payout to Chef'),
        ('adjustment', 'Manual Adjustment'),
    ]
    
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='payment_logs')
    chef_meal_order = models.ForeignKey(ChefMealOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name='payment_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    chef = models.ForeignKey(Chef, null=True, blank=True, on_delete=models.SET_NULL)
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_id = models.CharField(max_length=255, blank=True)
    
    status = models.CharField(max_length=50)
    details = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        action_entity = f"Order #{self.order.id}" if self.order else f"ChefMealOrder #{self.chef_meal_order.id}" if self.chef_meal_order else "Unknown"
        return f"{self.action} - {action_entity} - {self.amount}"

class MealCompatibility(models.Model):
    """
    Stores the compatibility analysis results between a meal and a dietary preference.
    This caches the results of analyze_meal_compatibility to avoid redundant API calls.
    """
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='compatibility_analyses')
    preference_name = models.CharField(max_length=100)
    is_compatible = models.BooleanField(default=False)
    confidence = models.FloatField(default=0.0)
    reasoning = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('meal', 'preference_name')
        indexes = [
            models.Index(fields=['meal', 'preference_name']),
        ]
    
    def __str__(self):
        compatibility = "Compatible" if self.is_compatible else "Not compatible"
        return f"{self.meal.name} - {self.preference_name}: {compatibility} ({self.confidence:.2f})"

class MealAllergenSafety(models.Model):
    """
    Tracks whether a meal is safe for a user with allergies.
    This is a caching layer to avoid repeated API calls.
    """
    meal = models.ForeignKey('Meal', on_delete=models.CASCADE, related_name='allergen_safety_checks')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_safe = models.BooleanField(default=False)
    flagged_ingredients = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    reasoning = models.TextField(blank=True)
    last_checked = models.DateTimeField(auto_now=True)
    substitutions = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = ('meal', 'user')
        verbose_name_plural = 'Meal allergen safety checks'

    def __str__(self):
        return f"Allergen check: {self.meal.name} for {self.user.username} - {'Safe' if self.is_safe else 'Unsafe'}"