from django.db import models
from pydantic import ValidationError
from chefs.models import Chef
from local_chefs.models import PostalCode, ChefPostalCode
import requests
import json
from django.conf import settings
from datetime import date, timedelta, timezone as py_tz
from zoneinfo import ZoneInfo
from django.utils import timezone
from typing import Optional
from custom_auth.models import CustomUser, Address
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import migrations
from pgvector.django import VectorExtension
from pgvector.django import VectorField
try:
    from openai import OpenAI, OpenAIError
except Exception:  # pragma: no cover - optional dependency may not be present in tests
    OpenAI = None

    class OpenAIError(Exception):
        """Fallback OpenAI error when SDK is unavailable."""

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
    # For user-generated meals, store a bundle of dishes (lightweight structure) to
    # cover heterogeneous households without creating persistent Dish rows.
    # Expected structure: [
    #   { "name": str, "dietary_tags": [str], "target_groups": [str],
    #     "notes": str | null, "ingredients": [str] | null, "is_chef_dish": false }
    # ]
    composed_dishes = models.JSONField(blank=True, null=True)

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
            if isinstance(parsed_response, list):
                candidate = next((item for item in parsed_response if isinstance(item, dict)), None)
                if candidate is None and parsed_response:
                    first = parsed_response[0]
                    if isinstance(first, str):
                        try:
                            inner = json.loads(first)
                            if isinstance(inner, dict):
                                candidate = inner
                        except Exception:
                            pass
                parsed_response = candidate or {}
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


class MealDish(models.Model):
    """
    Structured per-meal dish for user-generated meals.
    Keeps chef-created Dish model untouched.
    """
    meal = models.ForeignKey('Meal', on_delete=models.CASCADE, related_name='meal_dishes')
    name = models.CharField(max_length=200)
    dietary_tags = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    target_groups = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    notes = models.TextField(blank=True, null=True)
    # Free-form ingredient list for now; can be upgraded to structured name/qty/unit later
    ingredients = models.JSONField(blank=True, null=True)
    is_chef_dish = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['meal', 'name']),
        ]

    def __str__(self):
        return f"{self.name} (meal_id={self.meal_id})"

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
    approval_email_sent = models.BooleanField(default=False)
    instacart_url = models.URLField(max_length=1000, blank=True, null=True, help_text="URL to the Instacart shopping list for this meal plan")
    groq_auto_approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the first auto-approval triggered by Groq batch processing.",
    )
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
        Calculate the average rating of all meals in this meal plan using optimized database aggregation.
        FIXED: Previous implementation caused N+1 queries and memory exhaustion.
        """
        # Use database-level aggregation to avoid N+1 query problem
        avg_rating = self.meal.filter(
            reviews__isnull=False
        ).aggregate(
            avg_rating=Avg('reviews__rating')
        )['avg_rating']
        
        return avg_rating
        
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
            # Mark plan changed and require re‑approval after edits
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
    # Support for chef service orders in cart
    chef_service_orders = models.ManyToManyField('chef_services.ChefServiceOrder', blank=True, related_name='carts')

    def __str__(self):
        return f'Cart for {self.customer.username}'
    
    def get_all_chefs(self):
        """
        Get all unique chefs from cart items (meals and chef services).
        Returns a set of Chef objects.
        """
        from chefs.models import Chef
        chefs = set()
        
        # Get chefs from meals
        for meal in self.meal.all():
            if hasattr(meal, 'chef'):
                chefs.add(meal.chef)
        
        # Get chefs from chef service orders
        for service_order in self.chef_service_orders.filter(status='draft'):
            chefs.add(service_order.chef)
        
        return chefs
    
    def is_single_chef_cart(self):
        """
        Check if all cart items are from a single chef.
        Required for Stripe Connect checkout (can only transfer to one account).
        """
        chefs = self.get_all_chefs()
        return len(chefs) <= 1
    
    def get_cart_chef(self):
        """
        Get the chef for this cart if it's a single-chef cart.
        Returns None if cart is empty or has multiple chefs.
        """
        chefs = self.get_all_chefs()
        return list(chefs)[0] if len(chefs) == 1 else None
    

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
        Get the chef's timezone as a ZoneInfo timezone object.
        """
        timezone_str = self.get_chef_timezone()
        try:
            return ZoneInfo(timezone_str)
        except Exception:
            return ZoneInfo("UTC")
    
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
            dt = timezone.make_aware(dt, chef_tz)
            
        # Convert to UTC
        return dt.astimezone(py_tz.utc)
    
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
        return timezone.make_aware(naive_dt, chef_tz)
    
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


class MealPlanBatchJob(models.Model):
    """Tracks Groq batch submissions for weekly meal plan generation."""

    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    week_start_date = models.DateField()
    week_end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    completion_window = models.CharField(max_length=8, default="24h")
    batch_id = models.CharField(max_length=100, blank=True, null=True)
    input_file_id = models.CharField(max_length=100, blank=True, null=True)
    output_file_id = models.CharField(max_length=100, blank=True, null=True)
    error_file_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start_date", "-created_at"]

    def __str__(self):
        return f"MealPlanBatchJob({self.week_start_date}–{self.week_end_date}, status={self.status})"

    def register_members(self, entries):
        """Create or update request rows for the provided user/custom_id tuples."""
        for user_id, custom_id in entries:
            MealPlanBatchRequest.objects.update_or_create(
                job=self,
                user_id=user_id,
                defaults={
                    "custom_id": custom_id,
                    "status": MealPlanBatchRequest.STATUS_PENDING,
                    "response_payload": None,
                    "error": "",
                },
            )

    def mark_request_completed(self, *, custom_id: str, response_payload: Optional[dict] = None):
        request = self.requests.get(custom_id=custom_id)
        request.status = MealPlanBatchRequest.STATUS_COMPLETED
        request.response_payload = response_payload or {}
        request.completed_at = timezone.now()
        request.save(update_fields=["status", "response_payload", "completed_at"])

    def mark_request_failed(self, *, custom_id: str, error_message: str):
        request = self.requests.get(custom_id=custom_id)
        request.status = MealPlanBatchRequest.STATUS_FAILED
        request.error = error_message
        request.completed_at = timezone.now()
        request.save(update_fields=["status", "error", "completed_at"])

    def mark_failed(self, reason: str):
        self.status = self.STATUS_FAILED
        self.failure_reason = reason
        self.save(update_fields=["status", "failure_reason", "updated_at"])

    def mark_expired(self, reason: Optional[str] = None):
        self.status = self.STATUS_EXPIRED
        if reason:
            self.failure_reason = reason
        self.save(update_fields=["status", "failure_reason", "updated_at"])

    def pending_user_ids(self):
        return list(
            self.requests.filter(status=MealPlanBatchRequest.STATUS_PENDING).values_list("user_id", flat=True)
        )

    def users_requiring_fallback(self):
        if self.status in {self.STATUS_FAILED, self.STATUS_EXPIRED}:
            return list(self.requests.values_list("user_id", flat=True))
        return list(
            self.requests.exclude(status=MealPlanBatchRequest.STATUS_COMPLETED).values_list("user_id", flat=True)
        )


class MealPlanBatchRequest(models.Model):
    """Represents an individual request inside a Groq batch job."""

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_FALLBACK = "fallback_scheduled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_FALLBACK, "Fallback Scheduled"),
    ]

    job = models.ForeignKey(MealPlanBatchJob, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey('custom_auth.CustomUser', on_delete=models.CASCADE)
    custom_id = models.CharField(max_length=150, unique=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_PENDING)
    response_payload = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("job", "user")

    def __str__(self):
        return f"BatchRequest(user={self.user_id}, status={self.status})"


class SamplePlanPreview(models.Model):
    """Cached sample meal plan preview for users without chef access.
    
    This stores a one-time generated sample meal plan that shows users
    what their personalized meal plan could look like once a chef is available.
    The plan is read-only and cannot be regenerated.
    
    Structure of plan_data:
    {
        "meals": [
            {
                "day": "Monday",
                "meal_type": "Breakfast",
                "meal_name": "Greek Yogurt Parfait",
                "meal_description": "Creamy Greek yogurt layered with...",
                "servings": 2
            },
            ...
        ],
        "generated_for": {
            "dietary_preferences": ["Vegetarian"],
            "allergies": ["Peanuts"],
            "household_size": 2
        },
        "week_summary": "Your personalized week includes..."
    }
    """
    user = models.OneToOneField(
        'custom_auth.CustomUser',
        on_delete=models.CASCADE,
        related_name='sample_plan_preview'
    )
    plan_data = models.JSONField(
        help_text="JSON structure containing the sample meal plan preview"
    )
    preferences_snapshot = models.JSONField(
        blank=True,
        null=True,
        help_text="Snapshot of user preferences when plan was generated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Sample Plan Preview'
        verbose_name_plural = 'Sample Plan Previews'

    def __str__(self):
        return f"SamplePlanPreview(user={self.user_id}, created={self.created_at})"


# =============================================================================
# Collaborative Meal Planning Models (Chef-Customer)
# =============================================================================

class ChefMealPlan(models.Model):
    """Chef-created meal plan for a specific customer.
    
    Unlike user-generated MealPlan, this is created by the chef (with AI Sous Chef assistance)
    and can be collaboratively edited through customer suggestions.
    
    The date range is flexible - not forced to be weekly. Chefs can create plans
    for any date range based on their arrangement with the customer.
    """
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_ARCHIVED, 'Archived'),
    ]
    
    chef = models.ForeignKey(
        Chef,
        on_delete=models.CASCADE,
        related_name='created_meal_plans'
    )
    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='chef_meal_plans'
    )
    
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title for the plan (e.g., 'Holiday Week', 'Back to School')"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Chef's notes for the customer about this plan"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-start_date', '-created_at']
        indexes = [
            models.Index(fields=['chef', 'customer', 'status']),
            models.Index(fields=['customer', 'status', '-start_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['chef', 'customer', 'start_date'],
                name='unique_chef_customer_plan_start'
            ),
        ]
    
    def __str__(self):
        title = self.title or f"Plan {self.start_date}"
        return f"{title} for {self.customer.username} by Chef {self.chef.user.username}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})
    
    def publish(self):
        """Publish the plan to make it visible to the customer."""
        self.status = self.STATUS_PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=['status', 'published_at', 'updated_at'])
        
        # Update activity tracking on the connection
        from chef_services.models import ChefCustomerConnection
        ChefCustomerConnection.objects.filter(
            chef=self.chef,
            customer=self.customer,
            status=ChefCustomerConnection.STATUS_ACCEPTED
        ).update(last_plan_update_at=timezone.now())
    
    def archive(self):
        """Archive the plan (typically after the date range has passed)."""
        self.status = self.STATUS_ARCHIVED
        self.save(update_fields=['status', 'updated_at'])
    
    @property
    def pending_suggestions_count(self):
        """Count of customer suggestions awaiting chef review."""
        return self.suggestions.filter(status=MealPlanSuggestion.STATUS_PENDING).count()


class ChefMealPlanDay(models.Model):
    """Individual day in a chef-created meal plan.
    
    Days can be skipped for holidays, vacations, or other reasons.
    This gives flexibility for real-world meal planning scenarios.
    """
    plan = models.ForeignKey(
        ChefMealPlan,
        on_delete=models.CASCADE,
        related_name='days'
    )
    date = models.DateField()
    is_skipped = models.BooleanField(
        default=False,
        help_text="Whether this day is skipped (holiday, vacation, etc.)"
    )
    skip_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reason for skipping (e.g., 'Thanksgiving', 'Family vacation')"
    )
    notes = models.TextField(
        blank=True,
        help_text="Chef's notes for this specific day"
    )
    
    class Meta:
        ordering = ['date']
        unique_together = ('plan', 'date')
        indexes = [
            models.Index(fields=['plan', 'date']),
        ]
    
    def __str__(self):
        if self.is_skipped:
            return f"{self.date} (skipped: {self.skip_reason or 'no reason'})"
        return f"{self.date}"


class ChefMealPlanItem(models.Model):
    """Individual meal within a day of a chef meal plan.
    
    This represents a specific meal (breakfast, lunch, dinner, snack)
    that the chef has planned for the customer on a given day.
    """
    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('snack', 'Snack'),
    ]
    
    day = models.ForeignKey(
        ChefMealPlanDay,
        on_delete=models.CASCADE,
        related_name='items'
    )
    meal_type = models.CharField(
        max_length=20,
        choices=MEAL_TYPE_CHOICES
    )
    
    # Can link to an existing Meal or describe a custom meal
    meal = models.ForeignKey(
        'Meal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chef_plan_items',
        help_text="Link to an existing meal from the chef's menu"
    )
    custom_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Custom meal name if not using an existing meal"
    )
    custom_description = models.TextField(
        blank=True,
        help_text="Description for custom meals not in the database"
    )
    
    servings = models.PositiveIntegerField(
        default=1,
        help_text="Number of servings planned"
    )
    notes = models.TextField(
        blank=True,
        help_text="Chef's notes for this specific meal"
    )
    
    class Meta:
        ordering = ['meal_type']
        indexes = [
            models.Index(fields=['day', 'meal_type']),
        ]
    
    def __str__(self):
        name = self.meal.name if self.meal else self.custom_name or "Unnamed"
        return f"{self.get_meal_type_display()}: {name}"
    
    @property
    def display_name(self):
        """Return the meal name for display."""
        if self.meal:
            return self.meal.name
        return self.custom_name or "Unnamed Meal"
    
    @property
    def display_description(self):
        """Return the meal description for display."""
        if self.meal:
            return self.meal.description
        return self.custom_description


class MealPlanSuggestion(models.Model):
    """Customer's suggested change to a chef-created meal plan.
    
    This enables collaborative planning where customers can propose changes
    and chefs can approve, reject, or modify the suggestions.
    """
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_MODIFIED = 'modified'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_MODIFIED, 'Approved with Modifications'),
    ]
    
    SUGGESTION_TYPE_SWAP = 'swap_meal'
    SUGGESTION_TYPE_SKIP = 'skip_day'
    SUGGESTION_TYPE_ADD = 'add_day'
    SUGGESTION_TYPE_DIETARY = 'dietary_note'
    SUGGESTION_TYPE_GENERAL = 'general'
    
    SUGGESTION_TYPE_CHOICES = [
        (SUGGESTION_TYPE_SWAP, 'Swap this meal for something else'),
        (SUGGESTION_TYPE_SKIP, 'Skip this day'),
        (SUGGESTION_TYPE_ADD, 'Add a day to the plan'),
        (SUGGESTION_TYPE_DIETARY, 'Dietary concern/note'),
        (SUGGESTION_TYPE_GENERAL, 'General feedback'),
    ]
    
    plan = models.ForeignKey(
        ChefMealPlan,
        on_delete=models.CASCADE,
        related_name='suggestions'
    )
    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='meal_plan_suggestions'
    )
    
    # Target of the suggestion (optional - depends on type)
    target_item = models.ForeignKey(
        ChefMealPlanItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='suggestions',
        help_text="The specific meal item this suggestion is about"
    )
    target_day = models.ForeignKey(
        ChefMealPlanDay,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='suggestions',
        help_text="The specific day this suggestion is about"
    )
    
    suggestion_type = models.CharField(
        max_length=20,
        choices=SUGGESTION_TYPE_CHOICES
    )
    description = models.TextField(
        help_text="Customer's explanation of their suggestion"
    )
    
    # Chef's response
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    chef_response = models.TextField(
        blank=True,
        help_text="Chef's response to the suggestion"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['customer', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_suggestion_type_display()} by {self.customer.username} ({self.status})"
    
    def approve(self, response: str = ''):
        """Approve the suggestion."""
        self.status = self.STATUS_APPROVED
        self.chef_response = response
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'chef_response', 'reviewed_at'])
    
    def reject(self, response: str):
        """Reject the suggestion with a reason."""
        self.status = self.STATUS_REJECTED
        self.chef_response = response
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'chef_response', 'reviewed_at'])
    
    def approve_with_modifications(self, response: str):
        """Approve the suggestion with modifications."""
        self.status = self.STATUS_MODIFIED
        self.chef_response = response
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'chef_response', 'reviewed_at'])


class MealPlanGenerationJob(models.Model):
    """Tracks async AI meal generation jobs.
    
    When a chef requests meal suggestions, a job is created and processed
    in the background via Celery. The chef can continue working and check
    back for results.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]
    
    MODE_FULL_WEEK = 'full_week'
    MODE_FILL_EMPTY = 'fill_empty'
    MODE_SINGLE_SLOT = 'single_slot'
    
    MODE_CHOICES = [
        (MODE_FULL_WEEK, 'Generate Full Week'),
        (MODE_FILL_EMPTY, 'Fill Empty Slots'),
        (MODE_SINGLE_SLOT, 'Single Slot'),
    ]
    
    plan = models.ForeignKey(
        ChefMealPlan,
        on_delete=models.CASCADE,
        related_name='generation_jobs'
    )
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='meal_generation_jobs'
    )
    
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_FILL_EMPTY
    )
    target_day = models.CharField(max_length=20, blank=True)
    target_meal_type = models.CharField(max_length=20, blank=True)
    custom_prompt = models.TextField(blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    
    # Results stored as JSON
    suggestions = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    slots_requested = models.IntegerField(default=0)
    slots_generated = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['plan', 'status']),
            models.Index(fields=['chef', '-created_at']),
        ]
    
    def __str__(self):
        return f"Generation Job {self.id} for Plan {self.plan_id} ({self.status})"
    
    def mark_processing(self):
        """Mark job as started."""
        self.status = self.STATUS_PROCESSING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self, suggestions: list):
        """Mark job as completed with suggestions."""
        self.status = self.STATUS_COMPLETED
        self.suggestions = suggestions
        self.slots_generated = len(suggestions)
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'suggestions', 'slots_generated', 'completed_at'])
    
    def mark_failed(self, error: str):
        """Mark job as failed with error message."""
        self.status = self.STATUS_FAILED
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])
