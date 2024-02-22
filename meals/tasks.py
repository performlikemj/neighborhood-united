from celery import shared_task
from .models import Meal, Dish, Ingredient
from openai import OpenAI
from django.conf import settings

@shared_task
def update_embeddings():
    client = OpenAI(api_key=settings.OPENAI_KEY)

    def get_embedding(text, model="text-embedding-3-small"):
        text = text.replace("\n", " ")
        response = client.embeddings.create(input=[text], model=model)
        return response.data[0].embedding if response.data else None

    for meal in Meal.objects.filter(meal_embedding__isnull=True):
        meal.meal_embedding = get_embedding(str(meal))
        meal.save()

    for dish in Dish.objects.filter(dish_embedding__isnull=True):
        dish.dish_embedding = get_embedding(str(dish))
        dish.save()

    for ingredient in Ingredient.objects.filter(ingredient_embedding__isnull=True):
        ingredient.ingredient_embedding = get_embedding(str(ingredient))
        ingredient.save()
