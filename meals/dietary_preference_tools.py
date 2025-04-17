"""
Dietary preference tools for the OpenAI Responses API integration.

This module implements the dietary preference tools defined in the optimized tool structure,
connecting them to the existing dietary preference functionality in the application.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union

from django.shortcuts import get_object_or_404
from django.db.models import Q

from custom_auth.models import CustomUser
from meals.models import DietaryPreference, Meal, CustomDietaryPreference
from meals.serializers import DietaryPreferenceSerializer, MealSerializer

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
                        "type": "string",
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
                        "type": "string",
                        "description": "The ID of the user"
                    },
                    "meal_id": {
                        "type": "string",
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
                        "type": "string",
                        "description": "The ID of the user"
                    },
                    "meal_id": {
                        "type": "string",
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
    }
]

# Tool implementation functions

def manage_dietary_preferences(user_id: str, action: str, preference: str = None, is_custom: bool = False) -> Dict[str, Any]:
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
                    dietary_preference = DietaryPreference.objects.create(
                        name=preference
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

def check_meal_compatibility(user_id: str, meal_id: str) -> Dict[str, Any]:
    """
    Check if a meal is compatible with a user's dietary preferences.
    
    Args:
        user_id: The ID of the user
        meal_id: The ID of the meal to check
        
    Returns:
        Dict containing the compatibility status
    """
    try:
        # Get the user and meal
        user = get_object_or_404(CustomUser, id=user_id)
        meal = get_object_or_404(Meal, id=meal_id)
        
        # Get the user's standard dietary preferences
        standard_preferences = user.dietary_preferences.all()
        # Get the user's custom dietary preferences
        custom_preferences = user.custom_dietary_preferences.all()
        
        # Get the meal's dietary preferences
        meal_preferences = meal.dietary_preferences.all()
        # Get the meal's custom dietary preferences
        meal_custom_preferences = meal.custom_dietary_preferences.all()
        
        # Check for incompatible preferences
        incompatible_preferences = []
        
        # Check standard preferences
        for user_pref in standard_preferences:
            # Check if the meal has any incompatible ingredients or preferences
            if user_pref.name.lower() in ["vegetarian", "vegan"]:
                if not any(mp.name.lower() in ["vegetarian", "vegan"] for mp in meal_preferences):
                    incompatible_preferences.append(user_pref.name)
            elif user_pref.name.lower() == "gluten-free":
                if not any(mp.name.lower() == "gluten-free" for mp in meal_preferences):
                    incompatible_preferences.append(user_pref.name)
            # Add more specific checks for other dietary preferences as needed
        
        # Check custom preferences (simplified approach)
        for custom_pref in custom_preferences:
            # Check if the meal has this custom preference
            if not meal_custom_preferences.filter(id=custom_pref.id).exists():
                incompatible_preferences.append(custom_pref.name)
        
        # Determine compatibility
        is_compatible = len(incompatible_preferences) == 0
        
        return {
            "status": "success",
            "meal_name": meal.name,
            "is_compatible": is_compatible,
            "incompatible_preferences": incompatible_preferences if not is_compatible else [],
            "meal_preferences": [mp.name for mp in meal_preferences] + [mp.name for mp in meal_custom_preferences]
        }
        
    except Exception as e:
        logger.error(f"Error checking meal compatibility for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to check meal compatibility: {str(e)}"
        }

def suggest_alternatives(user_id: str, meal_id: str, meal_type: str = None, count: int = 3) -> Dict[str, Any]:
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

# Function to get all dietary preference tools
def get_dietary_preference_tools():
    """
    Get all dietary preference tools for the OpenAI Responses API.
    
    Returns:
        List of dietary preference tools in the format required by the OpenAI Responses API
    """
    return DIETARY_PREFERENCE_TOOLS
