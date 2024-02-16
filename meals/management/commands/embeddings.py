from django.core.management.base import BaseCommand
from meals.models import Meal, Dish, Ingredient
from openai import OpenAI
from django.conf import settings

class Command(BaseCommand):
    help = 'Updates the embeddings for all meals, dishes, and ingredients'

    def handle(self, *args, **options):
        # Initialize the OpenAI client
        client = OpenAI(api_key=settings.OPENAI_KEY)

        # Function to get embeddings
        def get_embedding(text, model="text-embedding-3-small"):
            text = text.replace("\n", " ")
            return client.embeddings.create(input=[text], model=model).data[0].embedding

        # Process and update Meals
        for meal in Meal.objects.all():
            meal_str = str(meal)  # Get the string representation
            meal.meal_embedding = get_embedding(meal_str)  # Assign the generated embedding
            meal.save()  # Save the meal instance with the new embedding

        # Process and update Dishes
        for dish in Dish.objects.all():
            dish_str = str(dish)
            dish.dish_embedding = get_embedding(dish_str)
            dish.save()

        # Process and update Ingredients
        for ingredient in Ingredient.objects.all():
            ingredient_str = str(ingredient)
            ingredient.ingredient_embedding = get_embedding(ingredient_str)
            ingredient.save()

        self.stdout.write(self.style.SUCCESS('Successfully updated embeddings'))