# meals/models/core.py
"""
Core meal models: Ingredient, MealType, Dish, Meal, MealDish, Tag
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField

import json
import logging

from chefs.models import Chef
from local_chefs.models import ChefPostalCode
from custom_auth.models import CustomUser, Address

logger = logging.getLogger(__name__)


class PostalCodeManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            try:
                user_postal_code = user.address.normalized_postalcode
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


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

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
    dietary_preferences = models.ManyToManyField('DietaryPreference', blank=True, related_name='meals')
    custom_dietary_preferences = models.ManyToManyField(
        'CustomDietaryPreference', blank=True, related_name='meals'
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

        from datetime import timedelta
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
