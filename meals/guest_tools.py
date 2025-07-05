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
import requests
import traceback
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from django.shortcuts import get_object_or_404

from custom_auth.models import CustomUser
from meals.models import Dish, MealPlan, MealPlanMeal, Ingredient
from chefs.models import Chef

logger = logging.getLogger(__name__)

n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")

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
    },
    {
        "type": "function",
        "name": "guest_register_user",
        "description": "Register a new user account using the provided data and return authentication tokens.",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_id": {"type": "string", "description": "Guest session identifier"},
                "user": {"type": "object", "description": "Fields for the CustomUser model (username, email, password, etc.)", "properties": {}, "additionalProperties": true},
                "address": {"type": "object", "description": "Optional address fields such as street, city and postalcode", "properties": {}, "additionalProperties": true},
                "goal": {"type": "object", "description": "Optional goal information (goal_name and goal_description)", "properties": {}, "additionalProperties": true}
            },
            "required": ["guest_id", "user"],
            "additionalProperties": false
        }
    },
    {
        "type": "function",
        "name": "onboarding_save_progress",
        "description": "Persist partial registration details during onboarding.",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_id": {"type": "string"},
                "data": {"type": "object", "additionalProperties": true}
            },
            "required": ["guest_id", "data"],
            "additionalProperties": false
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
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_dishes", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to search dishes"}


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
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_chefs", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to search chefs"}


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
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_get_meal_plan", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to get meal plan"}


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
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_ingredients", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to search ingredients"}


def guest_register_user(guest_id: str, user: Dict[str, Any], address: Optional[Dict[str, Any]] = None, goal: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Register a new user account through the chatbot."""
    from rest_framework.test import APIRequestFactory
    from custom_auth.views import register_api_view

    try:
        payload = {"user": user}
        if address:
            payload["address"] = address
        if goal:
            payload["goal"] = goal

        factory = APIRequestFactory()
        request = factory.post("/api/register/", data=payload, format="json")
        response = register_api_view(request)
        if hasattr(response, "data"):
            result = response.data
        else:
            result = json.loads(response.content)

        # Mark onboarding session as completed
        try:
            from custom_auth.models import OnboardingSession
            session, _ = OnboardingSession.objects.get_or_create(guest_id=guest_id)
            session.data = payload
            session.completed = True
            session.save()
        except Exception:
            pass

        return result
    except Exception as e:
        requests.post(n8n_traceback_url, json={"error": str(e), "source": "guest_register_user", "traceback": traceback.format_exc()})
        return {"status": "error", "message": "Failed to register user"}


def onboarding_save_progress(guest_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Save partial onboarding data for a guest."""
    try:
        from custom_auth.models import OnboardingSession

        session, _ = OnboardingSession.objects.get_or_create(guest_id=guest_id)
        if not session.data:
            session.data = {}
        session.data.update(data)
        session.save()
        return {"status": "success", "data": session.data}
    except Exception as e:
        requests.post(n8n_traceback_url, json={"error": str(e), "source": "onboarding_save_progress", "traceback": traceback.format_exc()})
        return {"status": "error", "message": "Failed to save progress"}


# -----------------------------------------------------------------------------
# Helper to expose all guest tools
# -----------------------------------------------------------------------------
def get_guest_tools() -> List[Dict[str, Any]]:
    """
    Return the list of guest tool metadata for the OpenAI Responses API.
    """
    return GUEST_TOOLS
