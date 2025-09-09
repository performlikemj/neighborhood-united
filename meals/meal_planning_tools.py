"""
Meal planning tools for the OpenAI Responses API integration.

This module implements the meal planning tools defined in the optimized tool structure,
connecting them to the existing meal planning functionality in the application.
"""

import json
import requests
import os
import logging
from datetime import date
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from django.http import HttpRequest
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal, Meal
from meals.meal_plan_service import create_meal_plan_for_user as service_create_meal_plan_for_user
from meals.meal_generation import generate_and_create_meal
from meals.meal_instructions import generate_instructions
from meals.serializers import MealPlanSerializer, MealPlanMealSerializer
from shared.utils import (
    get_user_info as _util_get_user_info,
    find_nearby_supermarkets as _util_find_nearby_supermarkets,
    list_upcoming_meals as _util_list_upcoming_meals,
    create_meal_plan as _util_create_meal_plan,
    # modify_meal_plan as _util_modify_meal_plan,
    auth_get_meal_plan as _util_get_meal_plan,
    # get_meal_details as _util_get_meal_details,
    # generate_meal_instructions as _util_generate_meal_instructions,
    list_upcoming_meals as _util_list_upcoming_meals,
    get_user_info as _util_get_user_info,
    update_user_info as _util_update_user_info
)
import uuid
from meals.streaming_instructions import generate_streaming_instructions
from meals.macro_info_retrieval import get_meal_macro_information
from meals.youtube_api_search import find_youtube_cooking_videos, format_for_structured_output
from meals.pydantic_models import MealMacroInfo, VideoRankings, YouTubeVideoResults  # schema validation
from pydantic import ValidationError
from django.conf import settings
from meals.instacart_service import generate_instacart_link as _util_generate_instacart_link
import traceback

logger = logging.getLogger(__name__)

# Tool definitions for the OpenAI Responses API
MEAL_PLANNING_TOOLS = [
    {
        "type": "function",
        "name": "create_meal_plan",
        "description": "Create a meal plan for a user. By default it covers Monday through Sunday, but callers may specify which days to include and the priority order of meals per day.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "ID of the user for whom the plan is being generated"
                },
                "days_to_plan": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    },
                    "description": "Optional list of weekday names to populate; defaults to the whole week"
                },
                "prioritized_meals": {
                    "type": "object",
                    "description": "Optional mapping of <weekday> → list of meal types in priority order",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Breakfast", "Lunch", "Dinner"]
                        }
                    }
                },
                "meal_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Breakfast", "Lunch", "Dinner"]
                    },
                    "description": "Optional list restricting what meal types can be planned; defaults to all."
                },
                "start_date": {
                    "type": "string",
                    "description": "The ISO date (YYYY‑MM‑DD). The week starting with this date will be used which is always a Monday."
                },
                "end_date": {
                    "type": "string",
                    "description": "The ISO date (YYYY-MM-DD). The week ending with this date will be used which is always a Sunday."
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Raw user prompt to feed downstream generation."
                },
                "number_of_days": {
                    "type": "integer",
                    "description": "Number of days to plan. Defaults to 7."
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "modify_meal_plan",
        "description": "Modify an existing meal plan. For a targeted single‑slot change, provide both `day` and `meal_type` — only that slot will be updated (no variety pass). If either is omitted, the assistant may apply broader changes across the plan.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user who owns the meal plan"
                },
                "meal_plan_id": {
                    "type": "integer",
                    "description": "The ID of the meal plan to modify"
                },
                "day": {
                    "type": "string",
                    "enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    "description": "Optional. When used together with `meal_type`, performs a targeted change for that slot only."
                },
                "meal_type": {
                    "type": "string",
                    "enum": ["Breakfast", "Lunch", "Dinner"],
                    "description": "Optional. When used together with `day`, performs a targeted change for that slot only."
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Natural language description of the requested change(s)."
                }
            },
            "required": ["user_id", "meal_plan_id", "user_prompt"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_meal_plan",
        "description": "Get details of a user's existing meal plan(s)",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user who owns the meal plan"
                    },
                    "meal_plan_id": {
                        "type": "integer",
                        "description": "The ID of the meal plan to retrieve (optional, defaults to most recent)"
                    }
                },
                "required": ["user_id"],
                "additionalProperties": False
            }
    },
    {
        "type": "function",
        "name": "get_meal_details",
        "description": "Get detailed information about a specific meal",
        "parameters": {
                "type": "object",
                "properties": {
                    "meal_id": {
                        "type": "integer",
                        "description": "The ID of the meal"
                    }
                },
                "required": ["meal_id"],
                "additionalProperties": False
            }
    },
    {
        "type": "function",
        "name": "get_meal_plan_meals_info",
        "description": "Get detailed information about all meals in a meal plan, including meal name, day, meal type, and related meal ID",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user who owns the meal plan"
                },
                "meal_plan_id": {
                    "type": "integer",
                    "description": "The ID of the meal plan"
                }
            },
            "required": ["user_id", "meal_plan_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "email_generate_meal_instructions",
        "description": "Generate cooking instructions for meal(s) in a meal plan and send via email",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user who owns the meal plan"
                    },
                    "meal_plan_id": {
                        "type": "integer",
                        "description": "The ID of the meal plan"
                    },
                    "day": {
                        "type": "string",
                        "description": "Optional specific day to generate instructions for"
                    },
                    "meal_type": {
                        "type": "string",
                        "enum": ["Breakfast", "Lunch", "Dinner"],
                        "description": "Optional specific meal type to generate instructions for"
                    }
                },
                "required": ["user_id", "meal_plan_id"],
                "additionalProperties": False
            }
    },
    {
        "type": "function",
        "name": "list_upcoming_meals",
        "description": "List all upcoming meals for a given user",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": { "type": "integer", "description": "The ID of the user" }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_user_info",
        "description": "Retrieve essential information about the user (preferences, postal code, allergies, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": { "type": "integer", "description": "The ID of the user" }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_current_date",
        "description": "Return the current date in YYYY-MM-DD format",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "find_nearby_supermarkets",
        "description": "Find nearby supermarkets by postal code via Google Places API. Only returns the first 10 results. And cannot give directions or other information.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "update_user_info",
        "description": "Update user profile information such as postal code, dietary preferences, allergies, week shift, and user goal.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user to update"
                },
                "postal_code": {
                    "type": "string",
                    "description": "New postal code for the user"
                },
                "dietary_preferences": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Updated list of dietary preferences"
                },
                "allergies": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Updated list of allergies"
                },
                "user_goal": {
                    "type": "string",
                    "description": "Updated user goal description"
                },
                "street": { "type": "string", "description": "User's street address" },
                "city": { "type": "string", "description": "User's city" },
                "state": { "type": "string", "description": "User's state, prefecture, or country equivalent" },
                "country": { "type": "string", "description": "User's country code (e.g., 'JP', 'US')" }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "stream_meal_instructions",
        "description": "Generate cooking instructions for meals in a meal plan. This function doesn't send emails and is designed for direct display in the UI.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user who owns the meal plan"
                },
                "meal_plan_id": {
                    "type": "integer",
                    "description": "The ID of the meal plan"
                },
                "meal_plan_meal_ids": {
                    "type": "array",
                    "items": {
                        "type": "integer"
                    },
                    "description": "List of specific MealPlanMeal IDs that are related to the meal plan, to generate instructions for (not Meal IDs)"
                }
            },
            "required": ["user_id", "meal_plan_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "stream_bulk_prep_instructions",
        "description": "Generate bulk meal prep instructions for a meal plan and stream them back for displaying to the user",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user who owns the meal plan"
                },
                "meal_plan_id": {
                    "type": "integer",
                    "description": "The ID of the meal plan"
                }
            },
            "required": ["user_id", "meal_plan_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_meal_macro_info",
        "description": "Return macro‑nutrient info (kcal, protein, fat, carbs, fiber, etc.) for a single meal. Tip: call `get_meal_plan_meals_info` first to discover a valid `meal_id` for the current plan.",
        "parameters": {
            "type": "object",
            "properties": {
                "meal_id": {
                    "type": "integer",
                    "description": "ID of the Meal model instance."
                }
            },
            "required": ["meal_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "find_related_youtube_videos",
        "description": "Find & rank relevant YouTube videos for a given meal. Tip: call `get_meal_plan_meals_info` first to discover a valid `meal_id` for the current plan.",
        "parameters": {
            "type": "object",
            "properties": {
                "meal_id": {
                    "type": "integer",
                    "description": "ID of the Meal model instance."
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many top videos to return (default 5, max 10).",
                    "minimum": 1,
                    "maximum": 10
                }
            },
            "required": ["meal_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "generate_instacart_link_tool",
        "description": "Generate an Instacart shopping list link from the user's meal plan to buy ingredients",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user"
                },
                "meal_plan_id": {
                    "type": "integer",
                    "description": "The ID of the meal plan to generate the shopping list for"
                },
                "postal_code": {
                    "type": "string",
                    "description": "Optional postal code for location-based store selection. If not provided, the user's saved postal code will be used."
                }
            },
            "required": ["user_id", "meal_plan_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "list_user_meal_plans",
        "description": "Get a summary list of all meal plans for a user, showing just the meal plan IDs, start/end dates, and basic info to help choose the correct meal plan for other operations",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose meal plans to list"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    # TODO: Add one for obtaining a meals macronutrient breakdown
    # TODO: Add one for finding youtube videos about a meal
]

# Tool implementation functions
def get_user_info(user_id: int) -> dict:
    """
    Retrieve essential information about the user (preferences, postal code, allergies, etc.).
    """
    try:
        # build a minimal request object
        req = HttpRequest()
        req.data = {"user_id": user_id}
        return _util_get_user_info(req)
    except Exception as e:
        logger.error(f"get_user_info error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_user_info", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}

def update_user_info(
    user_id: int,
    postal_code: Optional[str] = None,
    dietary_preferences: Optional[List[str]] = None,
    allergies: Optional[List[str]] = None,
    user_goal: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update user profile information such as postal code, dietary preferences, allergies, week shift, and user goal.
    """
    try:
        req = HttpRequest()
        # Prepare data as a dictionary
        data_dict = {"user_id": user_id}
        if postal_code is not None:
            data_dict["postal_code"] = postal_code
        if dietary_preferences is not None:
            data_dict["dietary_preferences"] = dietary_preferences
        if allergies is not None:
            data_dict["allergies"] = allergies
        if user_goal is not None:
            data_dict["user_goal"] = user_goal
        if street is not None:
            data_dict["street"] = street
        if city is not None:
            data_dict["city"] = city
        if state is not None:
            data_dict["state"] = state
        if country is not None:
            data_dict["country"] = country

        # Serialize the dictionary to a JSON string and assign to req._body
        req._body = json.dumps(data_dict).encode('utf-8')
        req.content_type = "application/json" # Set content type header

        return _util_update_user_info(req)
    except Exception as e:
        logger.error(f"update_user_info error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"update_user_info", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}

def create_meal_plan(
    user_id: int,
    days_to_plan: Optional[List[str]] = None,
    prioritized_meals: Optional[Dict[str, List[str]]] = None,
    meal_types: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_prompt: Optional[str] = None,
    number_of_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a meal plan by calling `meals.meal_plan_service.create_meal_plan_for_user`
    with the new flexible arguments (days_to_plan, prioritized_meals, user_prompt, etc.).
    The default behaviour still creates a full Monday–Sunday plan when no optional
    parameters are supplied.
    Callers may specify both `start_date` and `end_date` to target an arbitrary week span;
    otherwise, the week containing `start_date` (or the current week) is used.
    """
    try:
        with transaction.atomic():
            # Resolve the user instance
            user = get_object_or_404(CustomUser, id=user_id)

            # Determine the target week span
            if start_date and end_date:
                start_of_week = datetime.fromisoformat(start_date).date()
                end_of_week   = datetime.fromisoformat(end_date).date()
                # Ensure start_of_week is the Monday if desired; otherwise trust caller
            else:
                # compute this week's Monday and Sunday
                today = timezone.localdate()
                start_of_week = (datetime.fromisoformat(start_date).date()
                                 if start_date else today - timedelta(days=today.weekday()))
                end_of_week = (datetime.fromisoformat(end_date).date()
                               if end_date else start_of_week + timedelta(days=6))
            monday_date = start_of_week

            # Delegate to the service layer
            meal_plan_obj = service_create_meal_plan_for_user(
                user=user,
                start_of_week=start_of_week,
                end_of_week=end_of_week,
                monday_date=monday_date,
                days_to_plan=days_to_plan,
                prioritized_meals=prioritized_meals,
                user_prompt=user_prompt,
                number_of_days=number_of_days,
            )

            # Serialise result if it's a Django model instance
            if isinstance(meal_plan_obj, MealPlan):
                data = MealPlanSerializer(meal_plan_obj).data
            else:
                data = meal_plan_obj  # already a dict

            return {"status": "success", "meal_plan": data}
    except Exception as e:
        logger.error(f"create_meal_plan error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"create_meal_plan", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}

def modify_meal_plan(user_id: int, meal_plan_id: int, day: str = None, meal_type: str = None, 
                    user_prompt: str = None) -> Dict[str, Any]:
    """
    Modify an existing meal plan using free-form text prompt.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan to modify
        day: Optional day to focus changes on (e.g., 'Monday', 'Tuesday')
        meal_type: Optional meal type to focus changes on (e.g., 'Breakfast', 'Lunch', 'Dinner')
        user_prompt: Free-form text describing the desired changes
        
    Returns:
        Dict containing the modified meal plan details
    """
    try:
        # Debug prints removed
        
        # Get the user and meal plan
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        
        # Check if meal plan is from a previous week
        current_date = timezone.now().date()
        if meal_plan.week_end_date < current_date:
            return {
                "status": "error",
                "message": "Cannot modify a meal plan from a previous week. Only the current week's meal plan can be modified."
            }
        
        # Construct a more specific prompt if day and meal_type are provided
        prompt = user_prompt or ""
        
        # Only focus changes on specific day/meal if both are provided
        prioritized_meals = None
        days_to_modify = None
        
        if day and meal_type:
            # If day and meal_type are specified, focus the changes on that specific meal
            if not prompt.lower().startswith(f"change {day.lower()}") and not prompt.lower().startswith(f"modify {day.lower()}"):
                prompt = f"Change {day}'s {meal_type} to: {prompt}"
            
            # Create valid prioritized_meals dictionary
            prioritized_meals = {day: [meal_type]}
            days_to_modify = [day]
            # Debug prints removed
        
        
        # Use targeted modify when day + meal_type are specified; otherwise fall back to parser‑driven apply_modifications
        from meals.meal_plan_service import apply_modifications, modify_existing_meal_plan
        
        request_id = str(uuid.uuid4())
        
        try:
            if day and meal_type:
                # Debug prints removed
                updated_meal_plan = modify_existing_meal_plan(
                    user=user,
                    meal_plan_id=meal_plan.id,
                    user_prompt=prompt,
                    days_to_modify=[day],
                    prioritized_meals={day: [meal_type]},
                    request_id=request_id,
                    should_remove=False,
                    run_variety_analysis=False,
                )
            else:
                # Debug prints removed
                updated_meal_plan = apply_modifications(
                    user=user,
                    meal_plan=meal_plan,
                    raw_prompt=prompt,
                    request_id=request_id
                )
            
            if updated_meal_plan is None:
                return {
                    "status": "error",
                    "message": "Cannot modify a meal plan from a previous week. Only the current week's meal plan can be modified."
                }
                
        except Exception as e:
            import traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"modify_meal_plan", "traceback": traceback.format_exc()})
            return {
                "status": "error",
                "message": f"Failed to modify meal plan"
            }
        # Debug prints removed
        
        # Fetch the updated meal plan meals to return in the response
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=updated_meal_plan).select_related("meal")
        
        # Format response data (include both meal_plan_meal_id and meal_id so downstream tools have what they need)
        meals_data = []
        for mpm in meal_plan_meals:
            try:
                is_chef = mpm.meal.is_chef_created() if hasattr(mpm.meal, 'is_chef_created') else False
                meals_data.append({
                    "id": mpm.id,  # meal_plan_meal_id (legacy field)
                    "meal_plan_meal_id": mpm.id,
                    "meal_id": mpm.meal.id if mpm.meal else None,
                    "day": mpm.day,
                    "meal_type": mpm.meal_type,
                    "meal_name": mpm.meal.name,
                    "meal_description": mpm.meal.description,
                    "is_chef_meal": is_chef
                })
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"modify_meal_plan", "traceback": traceback.format_exc()})
        
        return {
            "status": "success",
            "message": "Meal plan modified successfully",
            "meal_plan_id": updated_meal_plan.id,
            "target_day": day,
            "target_meal_type": meal_type,
            "meals": meals_data
        }
        
    except Exception as e:
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"modify_meal_plan", "traceback": traceback.format_exc()})
        logger.error(f"Error modifying meal plan {meal_plan_id} for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to modify meal plan"
        }

def get_meal_details(meal_id: int) -> Dict[str, Any]:
    """
    Get detailed information about a specific meal.
    
    Args:
        meal_id: The ID of the meal
        
    Returns:
        Dictionary containing meal details
    """
    try:
        meal = Meal.objects.get(id=meal_id)
        
        # Convert meal to dictionary format
        meal_data = {
            "id": str(meal.id),
            "name": meal.name,
            "description": meal.description,
            "meal_type": meal.meal_type,
            "ingredients": [ingredient.to_dict() for ingredient in meal.ingredients.all()] if hasattr(meal, 'ingredients') else [],
            "nutrition": meal.nutrition.to_dict() if hasattr(meal, 'nutrition') else {}
        }
        
        return {
            "status": "success",
            "meal": meal_data
        }
    except Meal.DoesNotExist:
        return {
            "status": "error",
            "message": f"Meal with ID {meal_id} not found"
        }
    except Exception as e:
        logger.error(f"Error getting meal details: {str(e)}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_meal_details", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to get meal details"
        }

def get_meal_plan_meals_info(user_id: int, meal_plan_id: int) -> Dict[str, Any]:
    """
    Get detailed information about all MealPlanMeal entries for a given MealPlan.
    Includes meal name, day, meal type, and related meal ID.
    """
    try:
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user_id=user_id)
        meal_plan_meals = MealPlanMeal.objects.select_related('meal').filter(meal_plan=meal_plan)

        meal_plan_meals_info = []
        for mpm in meal_plan_meals:
            meal_info = {
                "meal_plan_meal_id": mpm.id,
                "meal_id": mpm.meal.id if mpm.meal else None,
                "meal_name": mpm.meal.name if mpm.meal else "Unknown Meal",
                "day": mpm.day,
                "meal_type": mpm.meal_type,
                "meal_date": mpm.meal_date.isoformat() if mpm.meal_date else None,
                "already_paid": mpm.already_paid,
            }
            meal_plan_meals_info.append(meal_info)

        return {
            "status": "success",
            "meal_plan_meals": meal_plan_meals_info
        }
    except Exception as e:
        logger.error(f"Error getting meal plan meals info: {str(e)}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_meal_plan_meals_info", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to get meal plan meals info"
        }

def get_meal_plan(user_id: int, meal_plan_id: int = None) -> Dict[str, Any]:
    """
    Get details of an existing meal plan.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan to retrieve (optional, defaults to most recent)
        
    Returns:
        Dict containing the meal plan details
    """
    try:
        req = HttpRequest()
        req.data = {"user_id": user_id}
        return _util_get_meal_plan(req)
    except Exception as e:
        logger.error(f"get_meal_plan error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_meal_plan", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to get meal plan"}

def list_user_meal_plans(user_id: int) -> Dict[str, Any]:
    """
    Get a summary list of all meal plans for a user, showing just the meal plan IDs, 
    start/end dates, and basic info to help choose the correct meal plan for other operations.
    
    Args:
        user_id: The ID of the user whose meal plans to list
        
    Returns:
        Dict containing a list of meal plan summaries
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plans = MealPlan.objects.filter(user=user).order_by('-week_start_date')
        
        meal_plans_summary = []
        for mp in meal_plans:
            meal_plans_summary.append({
                "meal_plan_id": mp.id,
                "week_start_date": mp.week_start_date.isoformat(),
                "week_end_date": mp.week_end_date.isoformat(),
                "created_date": mp.created_date.isoformat() if mp.created_date else None,
                "is_approved": mp.is_approved,
                "has_changes": mp.has_changes
            })
        
        return {
            "status": "success",
            "meal_plans": meal_plans_summary
        }
    except Exception as e:
        logger.error(f"list_user_meal_plans error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"list_user_meal_plans", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to list user meal plans"}

def email_generate_meal_instructions(user_id: int, meal_plan_id: int, day: str = None, 
                              meal_type: str = None) -> Dict[str, Any]:
    """
    Generate cooking instructions for meals in a meal plan and send via email.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan
        day: Optional specific day to generate instructions for
        meal_type: Optional specific meal type to generate instructions for
        
    Returns:
        Dict containing the generated instructions or confirmation of email delivery
    """
    try:
        # Get the user and meal plan
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        
        # Filter meal plan meals based on day and meal type
        query_filters = {'meal_plan': meal_plan}
        
        if day:
            query_filters['day'] = day
            
        if meal_type:
            query_filters['meal_type'] = meal_type
            
        meal_plan_meals = MealPlanMeal.objects.filter(**query_filters)
        
        if not meal_plan_meals.exists():
            return {
                "status": "error",
                "message": "No meals found with the specified criteria"
            }
            
        # Get the IDs of the meal plan meals
        meal_plan_meal_ids = list(meal_plan_meals.values_list('id', flat=True))
        
        # Generate instructions for the meals
        # Note: In a real implementation, you might want to handle this asynchronously
        # and return a task ID instead of waiting for the instructions to be generated
        instructions = generate_instructions(meal_plan_meal_ids)
        
        return {
            "status": "success",
            "message": "Instructions generated successfully",
            "instructions": instructions
        }
        
    except Exception as e:
        logger.error(f"Error generating instructions for meal plan {meal_plan_id}: {str(e)}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"email_generate_meal_instructions", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to generate instructions"
        }

def get_current_date() -> dict:
    """
    Return the current date in ISO format.
    """
    return {"date": date.today().isoformat()}

def list_upcoming_meals(user_id: int) -> dict:
    """
    List all meals scheduled for the current week for the given user.
    """
    try:
        req = HttpRequest()
        req.data = {"user_id": user_id}
        return _util_list_upcoming_meals(req)
    except Exception as e:
        logger.error(f"list_upcoming_meals error for user {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"list_upcoming_meals", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to list upcoming meals"}

def find_nearby_supermarkets(user_id: int) -> dict:
    """
    Find nearby supermarkets by postal code (via Google Places API).
    """
    try:
        # the shared util ignores request.data, but signature expects two args
        req = HttpRequest()
        req.data = {"user_id": user_id}
        return _util_find_nearby_supermarkets(req)
    except Exception as e:
        logger.error(f"find_nearby_supermarkets error for user_id {user_id}: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"find_nearby_supermarkets", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to find nearby supermarkets"}

def stream_meal_instructions(
    user_id: int,
    meal_plan_id: int,
    meal_plan_meal_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Generate cooking instructions for meals in a meal plan.
    This function doesn't send emails and is designed for direct display in the UI.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan
        meal_plan_meal_ids: Optional list of specific MealPlanMeal IDs to generate instructions for (not Meal IDs)
        
    Returns:
        Dict containing the generated instructions
    """
    try:
        # Use generate_streaming_instructions to create the instructions
        return generate_streaming_instructions(
            user_id=user_id,
            meal_plan_id=meal_plan_id,
            mode="daily",
            meal_plan_meal_ids=meal_plan_meal_ids
        )
    except Exception as e:
        logger.error(f"Error in stream_meal_instructions for meal plan {meal_plan_id}: {str(e)}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"stream_meal_instructions", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to generate streaming instructions"
        }

def stream_bulk_prep_instructions(
    user_id: int,
    meal_plan_id: int
) -> Dict[str, Any]:
    """Generate bulk meal prep instructions for a meal plan and stream them back for displaying to the user"""
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)

        # Generate streaming instructions
        instructions_stream = generate_streaming_instructions(
            user_id=user_id,
            meal_plan_id=meal_plan_id,
            mode="bulk"
        )

        # Return the stream response
        return {
            "status": "success",
            "instructions_stream": instructions_stream,
            "message": "Bulk preparation instructions generated successfully."
        }
    except Exception as e:
        logger.error(f"Error generating bulk prep instructions: {str(e)}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"stream_bulk_prep_instructions", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to generate bulk prep instructions"
        }

def get_meal_macro_info(meal_id: int) -> Dict[str, Any]:
    """
    Return macro-nutrient info for a single meal using LLM estimation.
    
    Args:
        meal_id: ID of the Meal model instance
        
    Returns:
        Dictionary containing the meal's macro-nutrient information
    """
    try:
        # Debug prints removed
        meal = Meal.objects.get(id=meal_id)
        
        # Check if we have cached macro info in the meal model
        if meal.macro_info:
            logger.info(f"Using cached macro information for meal {meal_id}")
            return {"status": "success", "macros": meal.macro_info}
        
        # If not cached, fetch from the API
        data = get_meal_macro_information(
            meal_name=meal.name,
            meal_description=meal.description,
            ingredients=[ing.name for ing in meal.ingredients.all()] if hasattr(meal, "ingredients") else None
        )
        
        if not data:
            return {"status": "error", "message": "Macro lookup failed."}
            
        # Validate & coerce into canonical schema
        validated = MealMacroInfo.model_validate(data)
        validated_data = validated.model_dump()
        
        # Cache the results in the meal model
        meal.macro_info = validated_data
        meal.save(update_fields=['macro_info'])
        
        return {"status": "success", "macros": validated_data}
    except Meal.DoesNotExist:
        return {"status": "error", "message": f"Meal {meal_id} not found."}
    except Exception as e:
        logger.error(f"get_meal_macro_info error: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_meal_macro_info", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to get meal macro info"}

def find_related_youtube_videos(meal_id: int, max_results: int = 5) -> Dict[str, Any]:
    """
    Find & rank relevant YouTube videos that teach how to cook the given meal.
    
    Args:
        meal_id: ID of the Meal model instance
        max_results: Maximum number of videos to return (default 5, max 10)
        
    Returns:
        Dictionary containing ranked YouTube video information
    """
    try:
        # Debug prints removed
        # Ensure max_results is within bounds
        max_results = min(max(1, max_results), 10)
        
        meal = Meal.objects.get(id=meal_id)
        
        # Check if we have cached video data in the meal model
        if meal.youtube_videos:
            logger.info(f"Using cached YouTube videos for meal {meal_id}")
            videos = meal.youtube_videos
            
            # If we have more videos than requested, truncate the list
            if "ranked_videos" in videos and len(videos["ranked_videos"]) > max_results:
                videos["ranked_videos"] = videos["ranked_videos"][:max_results]
                
            return {"status": "success", "videos": videos}
        
        # If not cached, fetch from the API
        raw = find_youtube_cooking_videos(
            meal_name=meal.name,
            meal_description=meal.description,
            limit=max_results
        )
        
        formatted = format_for_structured_output(raw)
        
        # Validate
        try:
            validated = YouTubeVideoResults.model_validate(formatted)
            validated_data = validated.model_dump()
        except ValidationError as e:
            logger.error(f"find_related_youtube_videos validation error: {e}")
            if settings.TEST_MODE:
                validated_data = formatted
            return {"status": "error", "message": str(e)}
        
        # Cache the results in the meal model
        meal.youtube_videos = validated_data
        meal.save(update_fields=['youtube_videos'])
        
        return {"status": "success", "videos": validated_data}
    except Meal.DoesNotExist:
        return {"status": "error", "message": f"Meal {meal_id} not found."}
    except Exception as e:
        logger.error(f"find_related_youtube_videos error: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"find_related_youtube_videos", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to find related youtube videos"}

def generate_instacart_link_tool(user_id: int, meal_plan_id: int, postal_code: str = None) -> Dict[str, Any]:
    """
    Generate an Instacart shopping list link from the user's meal plan to buy ingredients
    """
    try:
        logger.info(f"generate_instacart_link_tool called for user {user_id} and meal plan {meal_plan_id} with postal code {postal_code}")
        # Call the service function directly with proper parameters
        return _util_generate_instacart_link(user_id, meal_plan_id, postal_code)
    except Exception as e:
        logger.error(f"generate_instacart_link error: {e}")
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instacart_link_tool", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to generate instacart link"}

# Function to get all meal planning tools
def get_meal_planning_tools():
    """
    Get all meal planning tools for the OpenAI Responses API.
    
    Returns:
        List of meal planning tools in the format required by the OpenAI Responses API
    """
    return MEAL_PLANNING_TOOLS
