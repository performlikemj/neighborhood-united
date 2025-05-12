# hood_united/meals/management/commands/update_dietary_preferences.py

from django.core.management.base import BaseCommand
from django.conf import settings
from meals.models import Meal, DietaryPreference
from meals.pydantic_models import DietaryPreferencesSchema
import logging
import openai
import time
import json

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update dietary preferences for all existing meals using OpenAI API.'

    def handle(self, *args, **options):
        client = openai.Client(api_key=settings.OPENAI_KEY)
        meals = Meal.objects.all()
        total_meals = meals.count()
        logger.info(f"Starting update of dietary preferences for {total_meals} meals.")

        for idx, meal in enumerate(meals, start=1):
            logger.info(f"Processing Meal {idx}/{total_meals}: '{meal.name}' (ID: {meal.id})")

            # Generate a prompt based on meal details
            messages = self.generate_messages(meal)

            try:
                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=messages,
                    text={
                        "format": {
                            'type': 'json_schema',
                            'name': 'dietary_preferences',
                            'schema': DietaryPreferencesSchema.model_json_schema()
                        }
                    }
                )

                dietary_prefs_text = response.output_text
                dietary_prefs = self.parse_dietary_preferences(dietary_prefs_text)
                # Clear existing dietary preferences
                meal.dietary_preferences.clear()

                # Assign new dietary preferences
                for pref_name in dietary_prefs:
                    pref, created = DietaryPreference.objects.get_or_create(name=pref_name)
                    meal.dietary_preferences.add(pref)

                meal.save()
                logger.info(f"Updated dietary preferences for '{meal.name}': {dietary_prefs}")

                # Respect OpenAI's rate limits
                time.sleep(1)  # Adjust sleep time based on your rate limits

            except Exception as e:
                logger.error(f"Failed to update dietary preferences for Meal ID {meal.id}: {e}")
                continue  # Proceed with the next meal

        logger.info("Completed updating dietary preferences for all meals.")

    def generate_messages(self, meal):
        """
        Generate the list of messages for the OpenAI API based on the meal's details.
        This returns an array of message objects.
        """
        prompt = (
            f"Analyze the following meal and determine its dietary preferences.\n\n"
            f"Meal Name: {meal.name}\n"
            f"Description: {meal.description}\n"
            f"Dishes: {', '.join(dish.name for dish in meal.dishes.all())}\n"
            f"Ingredients: {', '.join(ingredient.name for dish in meal.dishes.all() for ingredient in dish.ingredients.all())}\n"
            f"Please list all applicable dietary preferences (e.g., Vegetarian, Gluten-Free) for this meal."
        )

        # The messages array contains a system and a user message
        messages = [
            {"role": "developer", "content": "You are an assistant that assigns dietary preferences to meals."},
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
            return dietary_prefs
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return []