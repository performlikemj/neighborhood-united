from django.db import models
from chefs.models import Chef
import requests
import json
from django.conf import settings
from datetime import date
from django.utils import timezone
from custom_auth.models import CustomUser


class Ingredient(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='ingredients')
    name = models.CharField(max_length=200)
    spoonacular_id = models.IntegerField(null=True) 

    class Meta:
        unique_together = ('spoonacular_id', 'chef',)

    def __str__(self):
        return self.name


class MealType(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Dish(models.Model):
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='dishes')
    name = models.CharField(max_length=200)
    ingredients = models.ManyToManyField(Ingredient)
    featured = models.BooleanField(default=False)
    meal_types = models.ManyToManyField(MealType)

    
    # Nutritional information
    calories = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    carbohydrates = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    protein = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.get_nutritional_info()



    def get_nutritional_info(self):
        # Your Spoonacular API Key
        spoonacular_api_key = "your_spoonacular_api_key"

        # Base URL for the ingredients search endpoint
        search_url = "https://api.spoonacular.com/food/ingredients/search"

        # Base URL for the get ingredient information endpoint
        info_url = "https://api.spoonacular.com/food/ingredients/{id}/information"

        # Aggregate nutritional information for all ingredients
        total_nutrition = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
        }

        # For each ingredient in the dish
        for ingredient in self.ingredients.all():
            # Parameters for the search request
            search_params = {
                "query": ingredient.name,
                "number": 1,
                "apiKey": spoonacular_api_key,
            }

            # Make the search request
            search_response = requests.get(search_url, params=search_params)

            # Check the search response status
            if search_response.status_code == 200:
                # Parse the search JSON response
                search_data = search_response.json()

                # Check if we got any results
                if search_data["totalResults"] > 0:
                    # Get the first result
                    search_result = search_data["results"][0]

                    # Make a second request to fetch ingredient information
                    info_response = requests.get(info_url.format(id=search_result['id']), params={"apiKey": spoonacular_api_key})

                    # Check the information response status
                    if info_response.status_code == 200:
                        # Parse the information JSON response
                        info_data = info_response.json()

                        # Add the ingredient's nutritional information to the total
                        for nutrient in info_data['nutrition']['nutrients']:
                            if nutrient['name'].lower() == 'calories':
                                total_nutrition['calories'] += nutrient['amount']
                            elif nutrient['name'].lower() == 'protein':
                                total_nutrition['protein'] += nutrient['amount']
                            elif nutrient['name'].lower() == 'fat':
                                total_nutrition['fat'] += nutrient['amount']
                            elif nutrient['name'].lower() == 'carbohydrates':
                                total_nutrition['carbs'] += nutrient['amount']

        # Return the total nutritional information
        return total_nutrition

class Menu(models.Model):
    PARTY_SIZE_CHOICES = [(i, i) for i in range(1, 51)]  # Replace 51 with your maximum party size + 1
    name = models.CharField(max_length=200, default='Menu Name')
    chef = models.ForeignKey(Chef, on_delete=models.CASCADE, related_name='menus')
    created_date = models.DateField(auto_now_add=True)
    start_date = models.DateField()  # The first day the menu is available
    end_date = models.DateField()  # The last day the menu is available
    dishes = models.ManyToManyField(Dish)
    price = models.DecimalField(max_digits=6, decimal_places=2)  # Adding price field
    party_size = models.IntegerField(choices=PARTY_SIZE_CHOICES, default=1)
    description = models.TextField(blank=True)  # Adding description field



    class Meta:
        unique_together = ('chef', 'start_date', 'end_date', 'party_size')

    def __str__(self):
        return f'{self.chef.user.username} - {self.start_date} to {self.end_date}'


class Order(models.Model):
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)  # Order is related to a menu
    order_date = models.DateTimeField(auto_now_add=True)
    special_requests = models.TextField(blank=True)

    def __str__(self):
        return f'Order {self.id} - {self.customer_name}'

    def total_price(self):
        """Calculate the total price of the order"""
        return self.menu.price  # Using menu's price directly
    
    
class Cart(models.Model):
    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    menus = models.ManyToManyField(Menu)

    def __str__(self):
        return f'Cart for {self.customer.user.username}'


