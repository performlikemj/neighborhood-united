"""
Focus: Handling dietary preferences and custom dietary rules.
"""
import json
import logging
# Note: @shared_task decorators removed as part of Celery-to-sync migration.
# These functions are now called synchronously.
from django.conf import settings
try:
    from groq import Groq
except ImportError:
    Groq = None
from pydantic import ValidationError
import traceback
from meals.models import Meal, DietaryPreference, CustomDietaryPreference
from meals.pydantic_models import DietaryPreferenceDetail, DietaryPreferencesSchema
from shared.utils import create_or_update_dietary_preference, get_dietary_preference_info, get_groq_client
from typing import List, Optional

logger = logging.getLogger(__name__)

def handle_custom_dietary_preference(custom_prefs):
    """
    Handles the addition of a custom dietary preference.
    If it doesn't exist, generate its structure using OpenAI and append to JSON.
    """
    for custom_pref in custom_prefs:
        if custom_pref and not get_dietary_preference_info(custom_pref):
            try:
                # Step 4: Use OpenAI to generate structured JSON
                response = get_groq_client().chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {
                            "role": "system",
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
                gpt_output = response.choices[0].message.content
                new_pref_data = json.loads(gpt_output)
                if isinstance(new_pref_data, list):
                    candidate = next((item for item in new_pref_data if isinstance(item, dict)), None)
                    if candidate is None and new_pref_data:
                        first = new_pref_data[0]
                        if isinstance(first, str):
                            try:
                                inner = json.loads(first)
                                if isinstance(inner, dict):
                                    candidate = inner
                            except Exception:
                                pass
                    new_pref_data = candidate or {}
                
                # Handle null from LLM
                if new_pref_data is None:
                    logger.warning(f"LLM returned null for dietary preference {custom_pref}. Using empty dict.")
                    new_pref_data = {}
                
                # Validate the structure using Pydantic
                validated_pref = DietaryPreferenceDetail.model_validate(new_pref_data)
                # Step 5: Store in the database
                create_or_update_dietary_preference(
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

def assign_dietary_preferences(meal_id: int, gpt_tags: Optional[List[str]] = None):
    """
    Attach dietary tags to a Meal.
    If gpt_tags is supplied, trust & validate them;
    otherwise fall back to the OpenAI classification call.
    """
    try:
        meal = Meal.objects.get(id=meal_id)
        ALLOWED = set(dp.name for dp in DietaryPreference.objects.all())

        # 1. Use incoming tags if provided
        tags = []
        if gpt_tags:
            invalid = [t for t in gpt_tags if t not in ALLOWED]
            if invalid:
                logger.warning(f"GPT returned invalid tags {invalid}; they will be ignored.")
            tags = [t for t in gpt_tags if t in ALLOWED]

        # 2. If no tags yet, ask GPT to classify
        if not tags:
            messages = meal.generate_messages()
            response = get_groq_client().chat.completions.create(
                model="gpt-5-mini",
                input=messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "preferences",
                        "schema": DietaryPreferencesSchema.model_json_schema(),
                    }
                },
            )
            assistant_json = response.choices[0].message.content.strip()
            tags = meal.parse_dietary_preferences(assistant_json)

        # 3. Persist
        if not tags:
            logger.warning(f"No dietary preferences determined for '{meal.name}'.")
            return

        for name in tags:
            pref, _ = DietaryPreference.objects.get_or_create(name=name)
            meal.dietary_preferences.add(pref)

    except Meal.DoesNotExist:
        logger.error(f"Meal {meal_id} not found.")
    except ValidationError as ve:
        logger.error(f"Pydantic validation error for Meal '{meal.name}': {ve}")
        return

    except json.JSONDecodeError as je:
        logger.error(f"JSON decoding error for Meal '{meal.name}': {je}")
        logger.error(f"Response content: {assistant_json}")
        return

    except OpenAIError as oe:
        logger.error(f"OpenAI API error while assigning dietary preferences for Meal '{meal.name}': {oe}")
        return

    except Exception as e:
        logger.error(f"assign_dietary_preferences failed: {e}")
        logger.error(traceback.format_exc())
