"""
Guest tools for the OpenAI Responses API integration.

This module implements the tools available to guest users:
 - Search dishes
 - Search chefs
 - Get the current week’s meal plan
 - Search ingredients
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from django.shortcuts import get_object_or_404

from custom_auth.models import CustomUser
from meals.models import Dish, MealPlan, MealPlanMeal, Ingredient
from chefs.models import Chef

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tool metadata definitions (as required by the OpenAI Responses API)
# -----------------------------------------------------------------------------
GUEST_TOOLS = [
    {
        "type": "function",
        "name": "guest_search_dishes",
        "description": "Search dishes in the database by name",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to match against dish names"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "guest_search_chefs",
        "description": "Search chefs in the database by username",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to match against chef usernames"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "guest_get_meal_plan",
        "description": "Get the guest user's meal plan for the current week",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "ID of the guest user"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "guest_search_ingredients",
        "description": "Search ingredients in the database by name",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to match against ingredient names"
                }
            },
            "required": ["query"],
            "additionalProperties": False
        }
    }
]


# -----------------------------------------------------------------------------
# Tool implementations
# -----------------------------------------------------------------------------
def guest_search_dishes(query: str) -> Dict[str, Any]:
    """
    Search dishes by name.
    """
    try:
        matches = Dish.objects.filter(name__icontains=query)
        results = [
            {"id": d.id, "name": d.name, "description": d.description}
            for d in matches
        ]
        return {"status": "success", "query": query, "dishes": results}
    except Exception as e:
        logger.error(f"guest_search_dishes error: {e}")
        return {"status": "error", "message": str(e)}


def guest_search_chefs(query: str) -> Dict[str, Any]:
    """
    Search chefs by their username.
    """
    try:
        matches = Chef.objects.filter(user__username__icontains=query)
        results = [
            {"id": c.id, "username": c.user.username}
            for c in matches
        ]
        return {"status": "success", "query": query, "chefs": results}
    except Exception as e:
        logger.error(f"guest_search_chefs error: {e}")
        return {"status": "error", "message": str(e)}


def guest_get_meal_plan(user_id: int) -> Dict[str, Any]:
    """
    Retrieve the guest user's current-week meal plan.
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        plan = MealPlan.objects.filter(
            user=user,
            week_start_date=start_of_week,
            week_end_date=end_of_week
        ).first()

        if not plan:
            return {
                "status": "info",
                "message": "No meal plan found for the current week."
            }

        items = MealPlanMeal.objects.filter(meal_plan=plan)
        plan_items = [
            {
                "day": item.day,
                "meal_type": item.meal_type,
                "meal": {
                    "id": item.meal.id,
                    "name": item.meal.name
                }
            }
            for item in items
        ]

        return {
            "status": "success",
            "meal_plan": {
                "id": plan.id,
                "week_start_date": str(plan.week_start_date),
                "week_end_date": str(plan.week_end_date),
                "items": plan_items
            }
        }
    except Exception as e:
        logger.error(f"guest_get_meal_plan error: {e}")
        return {"status": "error", "message": str(e)}


def guest_search_ingredients(query: str) -> Dict[str, Any]:
    """
    Search ingredients by name.
    """
    try:
        matches = Ingredient.objects.filter(name__icontains=query)
        results = [
            {"id": ingr.id, "name": ingr.name}
            for ingr in matches
        ]
        return {"status": "success", "query": query, "ingredients": results}
    except Exception as e:
        logger.error(f"guest_search_ingredients error: {e}")
        return {"status": "error", "message": str(e)}


# -----------------------------------------------------------------------------
# Helper to expose all guest tools
# -----------------------------------------------------------------------------
def get_guest_tools() -> List[Dict[str, Any]]:
    """
    Return the list of guest tool metadata for the OpenAI Responses API.
    """
    return GUEST_TOOLS