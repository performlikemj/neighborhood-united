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
from pgvector.django import VectorExtension
from pgvector.django import VectorField
from django.db import migrations


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

class DietaryPreferenceManager(models.Manager):
    def for_user(self, user):
        if user.is_authenticated:
            dietary_preference = user.dietary_preference
            print(f'Dietary preference: {dietary_preference}')
            if dietary_preference == 'Everything':
                return super().get_queryset()
            else:
                return super().get_queryset().filter(dietary_preference=dietary_preference)
        return super().get_queryset()
    
class Meal(models.Model):
    DIETARY_CHOICES = [
    ('Vegan', 'Vegan'),
    ('Vegetarian', 'Vegetarian'),
    ('Pescatarian', 'Pescatarian'),
    ('Gluten-Free', 'Gluten-Free'),
    ('Keto', 'Keto'),
    ('Paleo', 'Paleo'),
    ('Halal', 'Halal'),
    ('Kosher', 'Kosher'),
    ('Low-Calorie', 'Low-Calorie'),
    ('Low-Sodium', 'Low-Sodium'),
    ('High-Protein', 'High-Protein'),
    ('Dairy-Free', 'Dairy-Free'),
    ('Nut-Free', 'Nut-Free'),
    ('Raw Food', 'Raw Food'),
    ('Whole 30', 'Whole 30'),
    ('Low-FODMAP', 'Low-FODMAP'),
    ('Diabetic-Friendly', 'Diabetic-Friendly'),
    ('Everything', 'Everything'),
    # ... add more as needed
    ]

    PARTY_SIZE_CHOICES = [(i, i) for i in range(1, 51)]  # Replace 51 with your maximum party size + 1
    name = models.CharField(max_length=200, default='Meal Name')
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='meals')
    image = models.ImageField(upload_to='meals/', blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()  # The first day the meal is available
    dishes = models.ManyToManyField(Dish)
    dietary_preference = models.CharField(max_length=20, choices=DIETARY_CHOICES, null=True, blank=True)
    price = models.DecimalField(max_digits=6, decimal_places=2)  # Adding price field
    party_size = models.IntegerField(choices=PARTY_SIZE_CHOICES, default=1)
    description = models.TextField(blank=True)  # Adding description field
    review_summary = models.TextField(blank=True, null=True)  # Adding summary field
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
        unique_together = ('chef', 'start_date')

    def __str__(self):
        # Basic meal info
        meal_info = f'{self.name} by {self.chef.user.username} ({self.dietary_preference})'
        
        # Description and review summary (if available)
        description = f'Description: {self.description[:100]}...' if self.description else ''
        review_summary = f'Review Summary: {self.review_summary[:100]}...' if self.review_summary else ''
        
        # Combining all the elements
        return f'{meal_info}. {description} {review_summary} Start Date: {self.start_date}, Party Size: {self.party_size}'


    def trimmed_embedding(self, length=10):
        """Return a trimmed version of the meal embedding."""
        # Ensure the embedding is a list and trim it to the specified length
        return self.meal_embedding[:length] if self.meal_embedding else []


    def is_available(self, week_shift=0):
        week_shift = int(week_shift)  # User's ability to plan for future weeks
        current_date = timezone.now().date() + timedelta(weeks=week_shift) 
        return self.start_date <= current_date  

    def can_be_ordered(self):
        """
        Check if the meal can be ordered (at least a day in advance).
        """
        current_date = timezone.now().date()
        return self.start_date > current_date


    def save(self, *args, **kwargs):
        if not self.created_date:
            self.created_date = timezone.now()
        super().save(*args, **kwargs)



class MealPlan(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    meal = models.ManyToManyField(Meal, through='MealPlanMeal')
    created_date = models.DateTimeField(auto_now_add=True)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
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
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)

    class Meta:
        # Ensure a meal is unique per day within a specific meal plan
        unique_together = ('meal_plan', 'meal', 'day')

    def __str__(self):
        meal_name = self.meal.name if self.meal else 'Unknown Meal'
        return f"{meal_name} on {self.day} for {self.meal_plan}"



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