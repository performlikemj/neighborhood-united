"""
Dietary preference tools for the OpenAI Responses API integration.

This module implements the dietary preference tools defined in the optimized tool structure,
connecting them to the existing dietary preference functionality in the application.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.db.models import Q
from openai import OpenAI, BadRequestError, OpenAIError
from custom_auth.models import CustomUser
from meals.models import DietaryPreference, Meal, CustomDietaryPreference
from meals.serializers import DietaryPreferenceSerializer, MealSerializer
from meals.pydantic_models import MealCompatibility
from django.conf import settings
import traceback
from shared.utils import (
    check_allergy_alert as _util_check_allergy_alert,
)
import re

api_key = settings.OPENAI_KEY
client = OpenAI(api_key=api_key)
logger = logging.getLogger(__name__)

# Tool definitions for the OpenAI Responses API
DIETARY_PREFERENCE_TOOLS = [
    {
        "type": "function",
        "name": "manage_dietary_preferences",
        "description": "Manage a user's dietary preferences",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["get", "add", "remove"],
                        "description": "Action to perform on dietary preferences"
                    },
                    "preference": {
                        "type": "string",
                        "description": "Dietary preference to add or remove (required for add/remove actions)"
                    },
                    "is_custom": {
                        "type": "boolean",
                        "description": "Whether this is a custom dietary preference (default is false)"
                    }
                },
                "required": ["user_id", "action"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "check_meal_compatibility",
        "description": "Check if a meal is compatible with a user's dietary preferences",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user"
                    },
                    "meal_id": {
                        "type": "integer",
                        "description": "The ID of the meal to check"
                    }
                },
                "required": ["user_id", "meal_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "suggest_alternatives",
        "description": "Suggest alternative meals that are compatible with a user's dietary preferences",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user"
                    },
                    "meal_id": {
                        "type": "integer",
                        "description": "The ID of the incompatible meal"
                    },
                    "meal_type": {
                        "type": "string",
                        "enum": ["Breakfast", "Lunch", "Dinner"],
                        "description": "The type of meal to suggest alternatives for"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of alternatives to suggest (default is 3)"
                    }
                },
                "required": ["user_id", "meal_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "check_allergy_alert",
        "description": "Check if the meal possibly contains any of the user's allergies",
        "parameters": {
            "type": "object",
            "properties": {
            "user_id": { "type": "integer", "description": "The ID of the user" },
            "description": { "type": "string", "description": "Detailed description of the meal" }
            },
            "required": ["user_id", "description"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "list_dietary_preferences",
        "description": "List all available dietary preferences in the system",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]

# Tool implementation functions

def manage_dietary_preferences(user_id: int, action: str, preference: str = None, is_custom: bool = False) -> Dict[str, Any]:
    """
    Manage a user's dietary preferences.
    
    Args:
        user_id: The ID of the user
        action: Action to perform on dietary preferences (get, add, remove)
        preference: Dietary preference to add or remove (required for add/remove actions)
        is_custom: Whether this is a custom dietary preference
        
    Returns:
        Dict containing the user's dietary preferences
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        if action == "get":
            # Get both standard and custom dietary preferences
            standard_preferences = user.dietary_preferences.all()
            custom_preferences = user.custom_dietary_preferences.all()
            
            # Format the preferences
            preferences = []
            
            # Add standard preferences
            for pref in standard_preferences:
                preferences.append({
                    "id": pref.id,
                    "name": pref.name,
                    "description": getattr(pref, 'description', ''),
                    "is_custom": False
                })
            
            # Add custom preferences
            for pref in custom_preferences:
                preferences.append({
                    "id": pref.id,
                    "name": pref.name,
                    "description": pref.description or '',
                    "is_custom": True,
                    "allowed": pref.allowed,
                    "excluded": pref.excluded
                })
                
            return {
                "status": "success",
                "preferences": preferences,
                "count": len(preferences)
            }
            
        elif action == "add":
            if not preference:
                return {
                    "status": "error",
                    "message": "Preference is required for add action"
                }
            
            if is_custom:
                # Handle custom dietary preference
                custom_preference = CustomDietaryPreference.objects.filter(
                    Q(name__iexact=preference) | Q(name__icontains=preference)
                ).first()
                
                if not custom_preference:
                    # Create a new custom dietary preference
                    custom_preference = CustomDietaryPreference.objects.create(
                        name=preference,
                        description=f"User-defined custom preference for {preference}"
                    )
                
                # Check if the user already has this custom preference
                if user.custom_dietary_preferences.filter(id=custom_preference.id).exists():
                    return {
                        "status": "success",
                        "message": f"User already has custom preference for {preference}",
                        "preference": {
                            "id": custom_preference.id,
                            "name": custom_preference.name,
                            "description": custom_preference.description or '',
                            "is_custom": True
                        }
                    }
                
                # Add the custom preference to the user
                user.custom_dietary_preferences.add(custom_preference)
                
                return {
                    "status": "success",
                    "message": f"Added custom preference for {preference}",
                    "preference": {
                        "id": custom_preference.id,
                        "name": custom_preference.name,
                        "description": custom_preference.description or '',
                        "is_custom": True
                    }
                }
            else:
                # Handle standard dietary preference
                dietary_preference = DietaryPreference.objects.filter(
                    Q(name__iexact=preference) | Q(name__icontains=preference)
                ).first()
                
                if not dietary_preference:
                    # Create a new dietary preference
                    clean_name = clean_preference_name(preference)
                    dietary_preference, _ = DietaryPreference.objects.get_or_create(
                        name__iexact=clean_name,   # exact, case-insensitive
                        defaults={"name": clean_name}
                    )
                    
                # Check if the user already has this preference
                if user.dietary_preferences.filter(id=dietary_preference.id).exists():
                    return {
                        "status": "success",
                        "message": f"User already has preference for {preference}",
                        "preference": {
                            "id": dietary_preference.id,
                            "name": dietary_preference.name,
                            "description": getattr(dietary_preference, 'description', ''),
                            "is_custom": False
                        }
                    }
                    
                # Add the preference to the user using the M2M relationship
                user.dietary_preferences.add(dietary_preference)
                
                return {
                    "status": "success",
                    "message": f"Added preference for {preference}",
                    "preference": {
                        "id": dietary_preference.id,
                        "name": dietary_preference.name,
                        "description": getattr(dietary_preference, 'description', ''),
                        "is_custom": False
                    }
                }
            
        elif action == "remove":
            if not preference:
                return {
                    "status": "error",
                    "message": "Preference is required for remove action"
                }
                
            if is_custom:
                # Find the custom dietary preference
                custom_preference = CustomDietaryPreference.objects.filter(
                    Q(name__iexact=preference) | Q(name__icontains=preference)
                ).first()
                
                if not custom_preference:
                    return {
                        "status": "error",
                        "message": f"Custom preference '{preference}' not found"
                    }
                    
                # Check if the user has this custom preference
                if not user.custom_dietary_preferences.filter(id=custom_preference.id).exists():
                    return {
                        "status": "error",
                        "message": f"User does not have custom preference for {preference}"
                    }
                    
                # Remove the custom preference from the user
                user.custom_dietary_preferences.remove(custom_preference)
                
                return {
                    "status": "success",
                    "message": f"Removed custom preference for {preference}"
                }
            else:
                # Find the standard dietary preference
                dietary_preference = DietaryPreference.objects.filter(
                    Q(name__iexact=preference) | Q(name__icontains=preference)
                ).first()
                
                if not dietary_preference:
                    return {
                        "status": "error",
                        "message": f"Preference '{preference}' not found"
                    }
                    
                # Check if the user has this preference
                if not user.dietary_preferences.filter(id=dietary_preference.id).exists():
                    return {
                        "status": "error",
                        "message": f"User does not have preference for {preference}"
                    }
                    
                # Remove the preference from the user using the M2M relationship
                user.dietary_preferences.remove(dietary_preference)
                
                return {
                    "status": "success",
                    "message": f"Removed preference for {preference}"
                }
            
        else:
            return {
                "status": "error",
                "message": f"Invalid action: {action}"
            }
            
    except Exception as e:
        logger.error(f"Error managing dietary preferences for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to manage dietary preferences: {str(e)}"
        }

def check_meal_compatibility(user_id: int, meal_id: int) -> dict:
    """
    Uses OpenAI Responses API + Structured Output to decide whether a meal
    meets a user's dietary preferences. Falls back to rule-based logic on error.
    """
    print(f'checking meal compatibility for user {user_id} and meal {meal_id}')
    try:
        # === 1. DB fetches (unchanged) =====================================
        user = get_object_or_404(CustomUser, id=user_id)
        meal = get_object_or_404(Meal, id=meal_id)

        standard = list(user.dietary_preferences.values_list("name", flat=True))
        custom   = list(user.custom_dietary_preferences.values_list("name", flat=True))

        meal_tags     = list(meal.dietary_preferences.values_list("name", flat=True))
        meal_custom   = list(meal.custom_dietary_preferences.values_list("name", flat=True))
        ingredients   = getattr(meal, "ingredients", [])  # if you store them
        description   = getattr(meal, "description", "")
        macros        = getattr(meal, "macro_info", {})    # optional

        # === 2. Build prompt ===============================================
        system_message = (
            """
            You are an assistant designed to check food compatibility against dietary preferences using a structured schema. The goal is to assess whether a meal aligns with specific user dietary preferences and provide a detailed report on any violations.

            # Instructions

            1. **Understand Meal Compatibility**: 
            - Analyze the meal's ingredients and preparation to determine compatibility with user dietary preferences.
            2. **Assess Violations**:
            - Identify and list any dietary violations present in the meal.
            3. **Calculate Confidence**:
            - Evaluate your confidence level in the compatibility assessment, ensuring it falls between 0 and 1.

            # Output Format

            Use the following structured JSON format to report the meal compatibility:

            ```json
            {
            "is_compatible": true or false,
            "violations": ["violation_1", "violation_2", ...],
            "confidence": 0.0 to 1.0
            }
            ```

            - `is_compatible`: Boolean indicating overall meal compatibility.
            - `violations`: List of human-readable strings detailing preference violations, if any.
            - `confidence`: A float indicating the confidence level in the assessment, ranging from 0 (no confidence) to 1 (complete confidence).

            # Notes

            - Ensure thorough analysis of ingredients and preparation methods against user dietary preferences.
            - Clearly and accurately report any violations to provide actionable feedback.
            - Maintain high accuracy to build user trust in assessment confidence levels.
            """
        )

        user_payload = {
            "standard_preferences": standard,
            "custom_preferences":   custom,
            "meal": {
                "name": meal.name,
                "tags": meal_tags,
                "custom_tags": meal_custom,
                "ingredients": ingredients,
                "description": description,
                "macros": macros,
            }
        }

        # === 3. Call Responses API with JSON-mode + schema =================
        response = client.responses.create(
            model="gpt-4.1-nano",
            input=[{"role": "developer", "content": system_message},
                   {"role": "user",   "content": json.dumps(user_payload)}],
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'meal_compatibility',
                    'schema': MealCompatibility.model_json_schema()
                }
            }
        )

        # Parse JSON then load into the Pydantic model so we can use attribute access
        result_data = json.loads(response.output_text)
        print(f'compatibility result: {result_data}')

        try:
            result = MealCompatibility(**result_data)
        except Exception:
            # If the model validation fails for any reason, fall back to a simple wrapper
            result = MealCompatibility(
                is_compatible=result_data.get("is_compatible", False),
                violations=result_data.get("violations", []),
                confidence=result_data.get("confidence", 0.0)
            )

        return {
            "status": "success",
            "meal_name": meal.name,
            "is_compatible": result.is_compatible,
            "incompatible_preferences": result.violations,
            "confidence": result.confidence
        }

    except (OpenAIError, BadRequestError) as oe:
        logging.error(f"OpenAI error: {oe}")
        # Fallback to the legacy rule-based check
        return legacy_rule_based_check(user, meal)

    except Exception as e:
        logger.error(f"Error checking compatibility: {e}")
        return { "status": "error", "message": str(e) }

def suggest_alternatives(user_id: int, meal_id: int, meal_type: str = None, count: int = 3) -> Dict[str, Any]:
    """
    Suggest alternative meals that are compatible with a user's dietary preferences.
    
    Args:
        user_id: The ID of the user
        meal_id: The ID of the incompatible meal
        meal_type: The type of meal to suggest alternatives for
        count: Number of alternatives to suggest (default is 3)
        
    Returns:
        Dict containing the suggested alternative meals
    """
    try:
        # Get the user and meal
        user = get_object_or_404(CustomUser, id=user_id)
        meal = get_object_or_404(Meal, id=meal_id)
        
        # Get the user's dietary preferences
        standard_preference_names = [pref.name.lower() for pref in user.dietary_preferences.all()]
        custom_preference_ids = [pref.id for pref in user.custom_dietary_preferences.all()]
        
        # Build the query for compatible meals
        query = Q()
        
        # Filter by meal type if provided
        if meal_type:
            query &= Q(meal_type=meal_type)
        else:
            query &= Q(meal_type=meal.meal_type)
            
        # Exclude the current meal
        query &= ~Q(id=meal_id)
        
        # Filter for meals that match the user's standard dietary preferences
        for pref_name in standard_preference_names:
            if pref_name in ["vegetarian", "vegan"]:
                query &= Q(dietary_preferences__name__icontains=pref_name)
            elif pref_name == "gluten-free":
                query &= Q(dietary_preferences__name__icontains="gluten-free")
            # Add more specific filters for other dietary preferences as needed
        
        # Get compatible meals with standard preferences
        compatible_meals = Meal.objects.filter(query).distinct()
        
        # Additional filter for custom preferences if any exist
        if custom_preference_ids:
            # Get meals that have at least one of the user's custom preferences
            compatible_meals = compatible_meals.filter(
                custom_dietary_preferences__id__in=custom_preference_ids
            ).distinct()
        
        # Limit to requested count
        compatible_meals = compatible_meals[:count]
        
        # Serialize the meals
        serializer = MealSerializer(compatible_meals, many=True)
        
        return {
            "status": "success",
            "original_meal": {
                "id": meal.id,
                "name": meal.name,
                "meal_type": meal.meal_type
            },
            "alternatives": serializer.data,
            "count": len(serializer.data)
        }
        
    except Exception as e:
        logger.error(f"Error suggesting alternatives for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to suggest alternatives: {str(e)}"
        }


# Legacy fallback compatibility checker
def legacy_rule_based_check(user_id: int, meal_id: int) -> Dict[str, Any]:
    """
    Legacy fallback compatibility checker that relies purely on the existing
    rule‑based logic.  
    Use this when the LLM‑powered compatibility check is unavailable or you
    want a deterministic result without additional API cost.

    Args:
        user_id: The ID of the user.
        meal_id: The ID of the meal to check.

    Returns:
        A dictionary mirroring the modern checker's contract:
        {
            "status": "success" | "error",
            "meal_name": str,
            "is_compatible": bool,
            "incompatible_preferences": list[str],
            "meal_preferences": list[str],
            "message": str  # only on error
        }
    """
    try:
        # Fetch user and meal objects
        user = get_object_or_404(CustomUser, id=user_id)
        meal = get_object_or_404(Meal, id=meal_id)

        # Gather user preferences
        standard_preferences = user.dietary_preferences.all()
        custom_preferences = user.custom_dietary_preferences.all()

        # Gather meal preferences
        meal_preferences = meal.dietary_preferences.all()
        meal_custom_preferences = meal.custom_dietary_preferences.all()

        # Determine incompatibilities
        incompatible_preferences: list[str] = []

        # Standard preference checks
        for user_pref in standard_preferences:
            pref_name = user_pref.name.lower()
            if pref_name in {"vegetarian", "vegan"}:
                if not any(mp.name.lower() in {"vegetarian", "vegan"} for mp in meal_preferences):
                    incompatible_preferences.append(user_pref.name)
            elif pref_name == "gluten-free":
                if not any(mp.name.lower() == "gluten-free" for mp in meal_preferences):
                    incompatible_preferences.append(user_pref.name)
            # TODO: extend with further standard rules (halal, kosher, etc.)

        # Custom preference checks
        for custom_pref in custom_preferences:
            if not meal_custom_preferences.filter(id=custom_pref.id).exists():
                incompatible_preferences.append(custom_pref.name)

        is_compatible = len(incompatible_preferences) == 0

        return {
            "status": "success",
            "meal_name": meal.name,
            "is_compatible": is_compatible,
            "incompatible_preferences": incompatible_preferences if not is_compatible else [],
            "meal_preferences": [mp.name for mp in meal_preferences] +
                                [mp.name for mp in meal_custom_preferences],
        }

    except Exception as e:
        logger.error(f"Legacy compatibility check error for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}


def check_allergy_alert(user_id: int, description: str = None) -> dict:
    """
    Return the user's recorded allergies.
    
    Args:
        user_id: The ID of the user
        
    Returns:
        Dict containing the user's allergies
    """
    try:
        req = HttpRequest()
        req.data = {"user_id": user_id}
        result = _util_check_allergy_alert(req, user_id)

        # Check the description of the meal and cross-reference it with the user's allergies
        if description:
            response = client.responses.create(
                model="gpt-4.1-nano",
                input= (
                """
                Expand the assistant's capabilities to check for allergens in meals and report them accordingly. Integrate allergy detection with the structured schema provided.

                # Instructions
                """
                "1. **Understand Meal Compatibility**: "
                f"- Analyze the meal's descrption of: {description} to determine compatibility with user dietary preferences and allergies of: {result['Allergens']}."
                "2. **Assess Violations**: "
                "- Identify and list any dietary violations and allergens present in the meal."
                "3. **Calculate Confidence**: "
                "- Evaluate your confidence level in the assessment, ensuring it ranges from 0 to 1."
                """
                # Output Format

                Use the following structured JSON format to report the meal compatibility and allergen detection:

                ```json
                {
                "is_compatible": true or false,
                "violations": ["violation_1", "violation_2", ...],
                "possible_allergens": ["allergen_1", "allergen_2", ...] or "No allergies detected but always be careful",
                "confidence": 0.0 to 1.0
                }
                ```

                - `is_compatible`: Boolean indicating overall meal compatibility.
                - `violations`: List of human-readable strings detailing preference violations, if any.
                - `possible_allergens`: List of allergens found in the meal; if none, a cautionary message.
                - `confidence`: A float indicating confidence in the assessment, ranging from 0 (no confidence) to 1 (complete confidence).

                # Examples

                <user_query>
                The user has the following allergies: shrimp, raw carrots, walnuts.
                The description of the meal is: a casserole with shrimp and walnuts inside
                </user_query>

                <assistant_response>
                ```json
                {
                "is_compatible": false,
                "violations": [],
                "possible_allergens": ["shrimp", "walnuts"],
                "confidence": 0.9
                }
                ```
                </assistant_response>

                <user_query>
                The user has the following allergies: gluten, soy.
                The description of the meal is: a salad with avocado and tomatoes
                </user_query>

                <assistant_response>
                ```json
                {
                "is_compatible": true,
                "violations": [],
                "possible_allergens": "No allergies detected but always be careful",
                "confidence": 0.9
                }
                ```
                </assistant_response>

                # Notes

                - Ensure thorough analysis of possibleingredients against user allergies.
                - Clearly and accurately report any detected allergens to provide actionable feedback.
                - Maintain high accuracy to build user trust in the assessment confidence levels.
                """
                )
            )
            check = response.output_text
            return {
                "status": "success",
                "message": check
            }
    except Exception as e:
        logger.error(f"check_allergy_alert error for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}

def list_dietary_preferences() -> Dict[str, Any]:
    """
    List all available dietary preferences in the system.
    
    Returns:
        Dict containing all standard dietary preferences
    """
    print('listing dietary preferences')
    try:
        # Get all standard dietary preferences
        preferences = DietaryPreference.objects.all()
        custom_preferences = CustomDietaryPreference.objects.all()
        # Format the preferences
        preference_list = []
        for pref in preferences:
            preference_list.append({
                "id": pref.id,
                "name": pref.name,
                "description": getattr(pref, 'description', ''),
            })
        for pref in custom_preferences:
            preference_list.append({
                "id": pref.id,
                "name": pref.name,
                "description": pref.description,
            })
        print(f'preference_list: {preference_list}')
        return {
            "status": "success",
            "preferences": preference_list,
            "count": len(preference_list)
        }
        
    except Exception as e:
        logger.error(f"Error listing dietary preferences: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Failed to list dietary preferences"
        }
    
# Function to get all dietary preference tools
def get_dietary_preference_tools() -> List[Dict[str, Any]]:
    """
    Get all dietary preference tools for the OpenAI Responses API.
    
    Returns:
        List of dietary preference tools in the format required by the OpenAI Responses API
    """
    return DIETARY_PREFERENCE_TOOLS

def clean_preference_name(preference):
    """Thoroughly clean a preference name by removing JSON artifacts"""
    # First strip whitespace and quotes
    clean = preference.strip().strip('"').strip("'")
    
    # Remove JSON patterns
    clean = re.sub(r'{"dietary_preferences":\s*\[', '', clean)
    clean = re.sub(r'\]\s*}', '', clean)
    clean = re.sub(r'[{}\[\]"\']', '', clean)
    
    # Remove any resulting double spaces
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    return clean
