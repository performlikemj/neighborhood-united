from django.db import models
from pydantic import ValidationError
from chefs.models import Chef
import requests
import json
from django.conf import settings
from datetime import date, timedelta
from django.utils import timezone
from custom_auth.models import CustomUser, Address
from django.contrib.contenttypes.fields import GenericRelation
from django.db import migrations
from pgvector.django import VectorExtension
from pgvector.django import VectorField
from openai import OpenAI, OpenAIError
from meals.pydantic_models import ShoppingList as ShoppingListSchema, Instructions as InstructionsSchema, DietaryPreferencesSchema
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
import traceback
import numpy as np
import logging

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

class Migration(migrations.Migration):
    operations = [
        VectorExtension()
    ]

class Ingredient(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=200)
    spoonacular_id = models.IntegerField(null=True) 
    calories = models.FloatField(null=True)
    fat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbohydrates = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    protein = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ingredient_embedding = VectorField(dimensions=1536, null=True)

    class Meta:
        unique_together = ('spoonacular_id', 'chef',)

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
        # Start with the basic dish info
        basic_info = f'{self.name} by {self.chef.user.username}'

        # Ingredients list
        ingredients_list = ', '.join([ingredient.name for ingredient in self.ingredients.all()][:5])  # Get top 5 ingredients for brevity
        ingredients_info = f'Ingredients: {ingredients_list}...'

        # Nutritional info, displayed only if available
        nutritional_info = ''
        if any([self.calories, self.fat, self.carbohydrates, self.protein]):
            nutritional_values = []
            if self.calories:
                nutritional_values.append(f'Calories: {self.calories} kcal')
            if self.fat:
                nutritional_values.append(f'Fat: {self.fat} g')
            if self.carbohydrates:
                nutritional_values.append(f'Carbs: {self.carbohydrates} g')
            if self.protein:
                nutritional_values.append(f'Protein: {self.protein} g')
            nutritional_info = ', '.join(nutritional_values)

        # Combine all the elements
        return f'{basic_info}. {ingredients_info} {nutritional_info}'

    
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
        # Update nutritional information before saving
        self.update_nutritional_info()
        super().save(*args, **kwargs)


class PostalCodeManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            try:
                user_postal_code = user.address.postalcode.code
                return super().get_queryset().filter(chef__serving_postalcodes__code=user_postal_code)
            except AttributeError:
                # Handle the case where the user doesn't have an associated postal code
                pass
        return super().get_queryset()

class DietaryPreference(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class DietaryPreferenceManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            user_prefs = user.dietary_preferences.all()  # Assuming this is now a many-to-many relationship
            if user_prefs.filter(name='Everything').exists():
                return super().get_queryset()
            else:
                return super().get_queryset().filter(dietary_preferences__in=user_prefs)
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
    PARTY_SIZE_CHOICES = [(i, i) for i in range(1, 51)]  # Replace 51 with your maximum party size + 1
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
    reviews = GenericRelation(
        'reviews.Review',  # The model to use
        'object_id',  # The foreign key on the related model (Review)
        'content_type',  # The content type field on the related model (Review)
    )
    objects = models.Manager()  # The default manager
    postal_objects = PostalCodeManager()  # Attach the custom manager
    dietary_objects = DietaryPreferenceManager()  # Attach the dietary preference manager
    meal_embedding = VectorField(dimensions=1536, null=True)
    
    class Meta:
        constraints = [
            # Your existing constraints here
            models.UniqueConstraint(fields=['name', 'creator'], condition=models.Q(creator__isnull=False), name='unique_meal_per_creator'),
            models.UniqueConstraint(fields=['chef', 'start_date'], condition=models.Q(chef__isnull=False), name='unique_chef_meal_per_date')
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if the meal is new

        super(Meal, self).save(*args, **kwargs)  # Save the instance before any operations

        if not self.created_date:
            self.created_date = timezone.now()
        
        # Validation for chef-created meals
        if self.chef:
            if self.start_date is None or self.price is None or not self.image:
                raise ValueError('start_date, price, and image must be provided when a chef creates a meal')
            if not self.dishes.exists():
                raise ValueError('At least one dish must be provided when a chef creates a meal')
        # Step 1: Save the instance first to ensure it has an ID
        if not self.pk:  # Check if the instance is new (i.e., no primary key yet)
            super(Meal, self).save(*args, **kwargs)

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
            {"role": "system", "content": "You are an assistant that assigns dietary preferences to meals."},
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

    def __str__(self):
        # Identify the creator
        creator_info = self.chef.user.username if self.chef else (self.creator.username if self.creator else 'No creator')

        # Initialize dietary preferences and custom dietary preferences
        dietary_prefs = "No preferences"
        custom_dietary_prefs = "No custom preferences"

        # Only access dietary preferences if the Meal instance has been saved
        if self.pk:  # Ensure the meal has an ID before accessing ManyToMany fields
            try:
                dietary_prefs_list = [pref.name for pref in self.dietary_preferences.all()] or ["No preferences"]
                dietary_prefs = ", ".join(dietary_prefs_list)
            except Exception as e:
                dietary_prefs = "Error retrieving preferences"
                logger.error(f"Error accessing dietary preferences for meal '{self.name}': {e}")
            
            try:
                custom_dietary_prefs_list = [pref.name for pref in self.custom_dietary_preferences.all()] or ["No custom preferences"]
                custom_dietary_prefs = ", ".join(custom_dietary_prefs_list)
            except Exception as e:
                custom_dietary_prefs = "Error retrieving custom preferences"
                logger.error(f"Error accessing custom dietary preferences for meal '{self.name}': {e}")

        # Description and review summary (if available)
        description = f'Description: {self.description[:100]}...' if self.description else ''
        review_summary = f'Review Summary: {self.review_summary[:100]}...' if self.review_summary else ''

        # Combine all the elements
        return (
            f'{self.name} by {creator_info} (Preferences: {dietary_prefs}, Custom Preferences: {custom_dietary_prefs}). '
            f'{description} {review_summary} Start Date: {self.start_date}, Price: {self.price}'
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
    created_date = models.DateTimeField(auto_now_add=True)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    is_approved = models.BooleanField(default=False)  # Track if the meal plan is approved
    has_changes = models.BooleanField(default=False)  # Track if there are changes to the plan
    order = models.OneToOneField(
        'Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='associated_meal_plan'
    )

    def clean(self):
        # Custom validation to ensure start_date is before end_date
        if self.week_start_date and self.week_end_date:
            if self.week_start_date >= self.week_end_date:
                raise ValidationError(('The start date must be before the end date.'))

        # Call the parent class's clean method
        super().clean()

    class Meta:
        unique_together = ('user', 'week_start_date', 'week_end_date')

    def __str__(self):
        return f"{self.user.username}'s MealPlan for {self.week_start_date} to {self.week_end_date}"

    def save(self, *args, **kwargs):
        was_approved = self.is_approved  # Track approval state before saving

        super().save(*args, **kwargs)  # Save normally

        # Only generate the shopping list if the meal plan was just approved
        if self.is_approved and not was_approved:
            self.generate_shopping_list()

    def generate_shopping_list(self):
        """Generate shopping list when the meal plan is approved."""
        from meals.tasks import generate_shopping_list
        generate_shopping_list.delay(self.id)
    

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
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='Dinner')

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

    # def delete(self, *args, **kwargs):
    #     # Update the meal plan's is_approved and has_changes flags on deletion
    #     meal_plan = self.meal_plan
    #     super().delete(*args, **kwargs)
    #     meal_plan.is_approved = False
    #     meal_plan.has_changes = True
    #     meal_plan.save()

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


    def save(self, *args, **kwargs):
        if not self.order_date:  # only update if order_date is not already set
            self.order_date = timezone.now()
        self.updated_at = timezone.now()  # always update the last updated time
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Order {self.id} - {self.customer.username}'

    def total_price(self):
        """Calculate the total price of the order."""
        total = 0
        for order_meal in self.ordermeal_set.all():
            total += order_meal.meal.price * order_meal.quantity
        return total

    
class OrderMeal(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    meal_plan_meal = models.ForeignKey(MealPlanMeal, on_delete=models.CASCADE)  # New field
    quantity = models.IntegerField()

    def __str__(self):
        return f'{self.meal} - {self.order} on {self.meal_plan_meal.day}'

class MealPlanThread(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    thread_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MealPlanThread for {self.user.username} with thread_id {self.thread_id}"

class PantryItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Canned', 'Canned'),
        ('Dry', 'Dry Goods'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='pantry_items')
    item_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    expiration_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='Canned')
    notes = models.TextField(blank=True, null=True)

    def is_expiring_soon(self):
        if self.expiration_date:
            days_until_expiration = (self.expiration_date - timezone.now().date()).days
            return days_until_expiration <= 7  # Consider items expiring within 7 days
        return False  # If no expiration date, assume it's not expiring soon

    def __str__(self):
        return f"{self.item_name} (x{self.quantity})"