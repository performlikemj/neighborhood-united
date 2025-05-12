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
                            "role": "developer",
                            "content": (
                                """
                                Define a new dietary preference using the provided schema.

                                You will receive a request to outline a dietary preference including descriptions, allowed foods, and excluded foods according to the specified schema.

                                # Instructions

                                1. **Description**: Provide a detailed explanation of the dietary preference. Include cultural, nutritional, or health reasons that might justify or explain following this dietary preference.
                                
                                2. **Allowed Foods**: List foods that are permitted within this dietary preference. These should align with the preference's guidelines, focusing on foods typically consumed by those following it.
                                
                                3. **Excluded Foods**: List foods that are prohibited within this dietary preference. These should also adhere to the guidelines, focusing on common exclusions based on cultural, ethical, or health reasons.

                                # Output Format

                                Format your response according to the following JSON structure:

                                ```json
                                {
                                "description": "[A comprehensive description of the dietary preference.]",
                                "allowed": ["[Food 1]", "[Food 2]", "..."],
                                "excluded": ["[Food 1]", "[Food 2]", "..."]
                                }
                                ```

                                # Examples

                                **Example 1**

                                - Input: Vegan Dietary Preference

                                - Output:
                                ```json
                                {
                                    "description": "Veganism is a lifestyle and dietary preference that excludes all animal products including meat, dairy, eggs, and honey. It is often followed for ethical reasons, environmental concerns, or health benefits.",
                                    "allowed": ["fruits", "vegetables", "grains", "legumes", "nuts", "seeds"],
                                    "excluded": ["meat", "dairy", "eggs", "honey", "gelatin"]
                                }
                                ```

                                **Example 2**

                                - Input: Gluten-Free Dietary Preference

                                - Output:
                                ```json
                                {
                                    "description": "A gluten-free diet excludes all products containing gluten, a protein found in wheat, barley, and rye, primarily for managing celiac disease or gluten sensitivity.",
                                    "allowed": ["rice", "corn", "quinoa", "potatoes", "fruits", "vegetables"],
                                    "excluded": ["wheat", "barley", "rye", "oats (unless certified gluten-free)"]
                                }
                                ```

                                # Notes

                                - Ensure the lists of foods are specific and relevant to common foods found in the context of the dietary preference.
                                - When possible, include reasons for both the inclusion and exclusion of certain foods to provide clear justification.
                                """
                            )
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