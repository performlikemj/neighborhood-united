"""
Focus: All embedding and similarity logic.
"""
import logging
from celery import shared_task
from django.conf import settings
from rest_framework.renderers import JSONRenderer
from meals.models import Meal, Dish, Ingredient
from chefs.models import Chef
from shared.utils import get_embedding
from openai import OpenAI
import json

logger = logging.getLogger(__name__)

OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

def prepare_meal_representation(meal: Meal) -> str:
    attributes = [meal.name, meal.description]
    
    dietary_prefs = [pref.name for pref in meal.dietary_preferences.all()]
    if dietary_prefs:
        attributes.append(f"Dietary Preferences: {', '.join(dietary_prefs)}")
    
    custom_diet_prefs = [pref.name for pref in meal.custom_dietary_preferences.all()]
    if custom_diet_prefs:
        attributes.append(f"Custom Dietary Preferences: {', '.join(custom_diet_prefs)}")
    
    if meal.meal_type:
        attributes.append(f"Meal Type: {meal.meal_type}")
    
    if meal.dishes.exists():
        dish_names = [dish.name for dish in meal.dishes.all()]
        attributes.append(f"Dishes: {', '.join(dish_names)}")
    
    if meal.review_summary:
        attributes.append(f"Review Summary: {meal.review_summary}")
    
    if meal.chef:
        attributes.append(f"Chef: {meal.chef.user.username}")
    
    return " | ".join(attributes)


@shared_task
def generate_meal_embedding(meal_id: int):
    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        logger.error(f"Meal with ID {meal_id} does not exist.")
        return None
    
    meal_representation = prepare_meal_representation(meal)
    try:
        embedding = get_embedding(meal_representation)
        if embedding:
            meal.meal_embedding = embedding
            meal.save(update_fields=['meal_embedding'])
            logger.info(f"Successfully updated embedding for meal {meal.id}.")
        else:
            logger.warning(f"get_embedding returned None for meal {meal.id}.")
    except Exception as e:
        logger.error(f"Failed to generate embedding for meal {meal.id}: {e}")
        # Optionally retry or handle differently.

def update_model_embeddings(queryset, embedding_func, embedding_field):
    for obj in queryset.filter(**{f"{embedding_field}__isnull": True}):
        embedding = embedding_func(obj)
        if embedding:
            setattr(obj, embedding_field, embedding)
            obj.save()
            logger.info(f"Updated embedding for {obj}")
        else:
            logger.warning(f"Could not update embedding for {obj}")

@shared_task
def update_embeddings():
    from meals.models import Meal, Dish, Ingredient  # Adjust the import path based on your project structure

    # For meals
    update_model_embeddings(Meal.objects, lambda m: generate_meal_embedding(m.id), 'meal_embedding')

    # For dishes
    update_model_embeddings(Dish.objects, lambda d: get_embedding(str(d)), 'dish_embedding')

    # For ingredients
    update_model_embeddings(Ingredient.objects, lambda i: get_embedding(str(i)), 'ingredient_embedding')

    # For chefs
    update_model_embeddings(Chef.objects, lambda c: get_embedding(str(c)), 'chef_embedding')

def serialize_data(data):
    """ Helper function to serialize data into JSON-compatible format """
    try:
        serialized_data = JSONRenderer().render(data)
        return json.loads(serialized_data)
    except Exception as e:
        logger.error(f"Error serializing data: {e}")
        raise