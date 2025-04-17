"""
Focus: Handling dietary preferences and custom dietary rules.
"""
import json
import logging
from celery import shared_task
from django.conf import settings
from openai import OpenAI, OpenAIError
from pydantic import ValidationError
import traceback
from meals.models import Meal, DietaryPreference, CustomDietaryPreference
from meals.pydantic_models import DietaryPreferenceDetail, DietaryPreferencesSchema
from shared.utils import append_dietary_preference_to_json, get_dietary_preference_info

logger = logging.getLogger(__name__)

OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)


@shared_task
def handle_custom_dietary_preference(custom_prefs):
    """
    Handles the addition of a custom dietary preference.
    If it doesn't exist, generate its structure using OpenAI and append to JSON.
    """
    for custom_pref in custom_prefs:
        if custom_pref and not get_dietary_preference_info(custom_pref):
            try:
                # Step 4: Use OpenAI to generate structured JSON
                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {
                            "role": "system",
                            "content": "You are an assistant that helps define new dietary preferences."
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Provide a structured JSON definition for the following dietary preference, matching the existing format:\n\n"
                                f"Preference Name: {custom_pref}"
                            )
                        }
                    ],
                    #store=True,
                    #metadata={'tag': 'custom_dietary_preference'},
                    text={
                        "format": {
                            'type': 'json_schema',
                            'name': 'custom_dietary_preference',
                            'schema': DietaryPreferenceDetail.model_json_schema()
                        }
                    }
                )


                # Parse GPT response
                gpt_output = response.output_text
                new_pref_data = json.loads(gpt_output)
                # Validate the structure using Pydantic
                validated_pref = DietaryPreferenceDetail.model_validate(new_pref_data)
                # Step 5: Append to dietary_preferences.json
                append_dietary_preference_to_json(
                    preference_name=custom_pref,
                    definition=validated_pref.description,
                    allowed=validated_pref.allowed,
                    excluded=validated_pref.excluded
                )

                # Create the CustomDietaryPreference object in the database
                CustomDietaryPreference.objects.get_or_create(
                    name=custom_pref,
                    defaults={
                        'description': validated_pref.description,
                        'allowed': validated_pref.allowed,
                        'excluded': validated_pref.excluded,
                    }
                )

                logger.info(f"Custom dietary preference '{custom_pref}' added successfully.")

            except (OpenAIError, json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Error generating or appending dietary preference '{custom_pref}': {e}")
                logger.error(traceback.format_exc())
                return False
    return True  # If preference exists, nothing to do

@shared_task
def assign_dietary_preferences(meal_id):
    """
    Use OpenAI API to determine dietary preferences based on meal details.
    Returns a list of dietary preferences.
    """
    try:
        meal = Meal.objects.get(id=meal_id)
        messages = meal.generate_messages()
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=messages,
            #store=True,
            #metadata={'tag': 'dietary_preferences'},
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'preferences',
                    'schema': DietaryPreferencesSchema.model_json_schema()
                }
            }
        )  

        assistant_message_content = response.output_text.strip()

        dietary_prefs = meal.parse_dietary_preferences(assistant_message_content)

        if not dietary_prefs:
            logger.warning(f"No dietary preferences returned by OpenAI for '{meal.name}'.")
            return

        # Assign the dietary preferences to the meal
        for pref_name in dietary_prefs:
            pref, created = DietaryPreference.objects.get_or_create(name=pref_name)
            meal.dietary_preferences.add(pref)

        # logger.info(f"Assigned dietary preferences for '{meal.name}': {dietary_prefs}")

    except Meal.DoesNotExist:
        logger.error(f"Meal with ID {meal_id} does not exist.")
        return

    except ValidationError as ve:
        logger.error(f"Pydantic validation error for Meal '{meal.name}': {ve}")
        return

    except json.JSONDecodeError as je:
        logger.error(f"JSON decoding error for Meal '{meal.name}': {je}")
        logger.error(f"Response content: {assistant_message_content}")
        return

    except OpenAIError as oe:
        logger.error(f"OpenAI API error while assigning dietary preferences for Meal '{meal.name}': {oe}")
        return

    except Exception as e:
        logger.error(f"Unexpected error while assigning dietary preferences for Meal '{meal.name}': {e}")
        logger.error(traceback.format_exc())
        return