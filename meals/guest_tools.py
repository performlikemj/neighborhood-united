"""
Guest tools for the OpenAI Responses API integration.

This module implements the tools available to guest users:
 - Search dishes
 - Search chefs
 - Get the current week's meal plan
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
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import Dish, MealPlan, MealPlanMeal, Ingredient, Meal
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
                "user": {"type": "object", "description": "Fields for the CustomUser model (username, email, password, etc.)"},
                "address": {"type": "object", "description": "Optional address fields such as street, city and postalcode"},
                "goal": {"type": "object", "description": "Optional goal information (goal_name and goal_description)"}
            },
            "required": ["guest_id", "user"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "onboarding_save_progress",
        "description": "Persist partial registration details during onboarding. Save only the specific data you just collected.",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_id": {"type": "string"},
                "username": {"type": "string", "description": "Username for the account"},
                "email": {"type": "string", "description": "Email address for the account"},
                "preferred_language": {"type": "string", "description": "User's preferred language (e.g., 'en', 'es', 'fr')"},
                "dietary_preferences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of standard dietary preferences (e.g., 'Vegan', 'Vegetarian', 'Gluten-Free', 'Keto', 'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein', 'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP', 'Diabetic-Friendly', 'Everything')"
                },
                "custom_dietary_preferences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of custom dietary preferences not in the standard list"
                },
                "allergies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of standard allergies (e.g., 'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', 'Soy', 'Fish', 'Shellfish', 'Sesame', 'Mustard', 'Celery', 'Lupin', 'Sulfites', 'Molluscs', 'Corn', 'Gluten', 'Kiwi', 'Latex', 'Pine Nuts', 'Sunflower Seeds', 'Poppy Seeds', 'Fennel', 'Peach', 'Banana', 'Avocado', 'Chocolate', 'Coffee', 'Cinnamon', 'Garlic', 'Chickpeas', 'Lentils', 'None')"
                },
                "custom_allergies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of custom allergies not in the standard list"
                },
                "household_members": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                            "dietary_preferences": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["guest_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "onboarding_request_password",
        "description": "Mark that the onboarding assistant is ready to request the user's password.",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_id": {"type": "string"}
            },
            "required": ["guest_id"],
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
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_dishes", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in guest_search_dishes: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_chefs", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in guest_search_chefs: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": f"Failed to search chefs"}


def guest_get_meal_plan(user_id: str) -> Dict[str, Any]:
    """
    Retrieve a sample meal plan for guest users.
    Guest users don't have database records, so we generate a sample meal plan.
    """
    try:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Start of the week is always Monday
        end_of_week = start_of_week + timedelta(days=6)

        # Define meal types
        meal_types = ['Breakfast', 'Lunch', 'Dinner']

        # Store guest meal plan details
        guest_meal_plan = []
        used_meals = set()

        # Fetch and limit meals for each type, randomizing the selection
        for meal_type in meal_types:
            # Get up to 33 meals of the current type, randomizing using `.order_by('?')`
            possible_meals = Meal.objects.filter(meal_type=meal_type, start_date__gte=today, start_date__lte=end_of_week).order_by('?')[:33]

            if not possible_meals.exists():
                # If no meals available for the specific type, provide a fallback
                fallback_meals = Meal.objects.filter(meal_type=meal_type).order_by('?')[:33]
                possible_meals = fallback_meals

            # Select a subset of meals for the week, ensuring no duplicates across meal types
            for chosen_meal in possible_meals:
                if chosen_meal.id not in used_meals:
                    used_meals.add(chosen_meal.id)

                    chef_username = chosen_meal.chef.user.username if chosen_meal.chef else 'User Created Meal'
                    meal_type = chosen_meal.mealplanmeal_set.first().meal_type if chosen_meal.mealplanmeal_set.exists() else meal_type
                    is_available_msg = "Available for exploration - orderable by registered users." if chosen_meal.can_be_ordered() else "Sample meal only."

                    # Construct meal details
                    meal_details = {
                        "meal_id": chosen_meal.id,
                        "name": chosen_meal.name,
                        "start_date": chosen_meal.start_date.strftime('%Y-%m-%d') if chosen_meal.start_date else "N/A",
                        "is_available": is_available_msg,
                        "dishes": [{"id": dish.id, "name": dish.name} for dish in chosen_meal.dishes.all()],
                        "meal_type": meal_type
                    }
                    guest_meal_plan.append(meal_details)

        return {
            "status": "success",
            "guest_meal_plan": guest_meal_plan,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_get_meal_plan", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in guest_get_meal_plan: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"guest_search_ingredients", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in guest_search_ingredients: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source": "guest_register_user", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in guest_register_user: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {"status": "error", "message": "Failed to register user"}


def onboarding_request_password(guest_id: str) -> Dict[str, Any]:
    """
    Mark that the onboarding assistant is ready to request the user's password.
    This is called when all other required data has been collected and the 
    assistant is ready to trigger the secure password modal.
    """
    logger.info(f"ONBOARDING_REQUEST_PASSWORD: Called for guest_id={guest_id}")
    print(f"ONBOARDING_REQUEST_PASSWORD: Called for guest_id={guest_id}")
    
    try:
        from custom_auth.models import OnboardingSession
        
        session, created = OnboardingSession.objects.get_or_create(guest_id=guest_id)
        
        # Mark that we're ready for password
        if not session.data:
            session.data = {}
        session.data['ready_for_password'] = True
        session.save()
        
        logger.info(f"ONBOARDING_REQUEST_PASSWORD: Marked session {session.id} as ready for password")
        print(f"ONBOARDING_REQUEST_PASSWORD: Marked session {session.id} as ready for password")
        
        return {
            "status": "success", 
            "message": "Ready for secure password collection",
            "ready_for_password": True
        }
    except Exception as e:
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source": "onboarding_request_password", "traceback": traceback.format_exc()})
            except Exception:
                pass
        
        logger.error(f"Error in onboarding_request_password: {str(e)}")
        print(f"ONBOARDING_REQUEST_PASSWORD ERROR: {str(e)}")
        return {"status": "error", "message": "Failed to mark ready for password"}


def onboarding_save_progress(
    guest_id: str, 
    username: str = None, 
    email: str = None, 
    preferred_language: str = None,
    dietary_preferences: List[str] = None,
    custom_dietary_preferences: List[str] = None,
    allergies: List[str] = None,
    custom_allergies: List[str] = None,
    household_members: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Save partial onboarding data for a guest."""
    # Create data dict from provided parameters
    data = {}
    if username is not None:
        data['username'] = username
    if email is not None:
        data['email'] = email
    if preferred_language is not None:
        data['preferred_language'] = preferred_language
    if dietary_preferences is not None:
        data['dietary_preferences'] = dietary_preferences
    if custom_dietary_preferences is not None:
        data['custom_dietary_preferences'] = custom_dietary_preferences
    if allergies is not None:
        data['allergies'] = allergies
    if custom_allergies is not None:
        data['custom_allergies'] = custom_allergies
    if household_members is not None:
        data['household_members'] = household_members
    
    logger.info(f"ONBOARDING_SAVE_PROGRESS: Starting with guest_id={guest_id}, data={data}")
    print(f"ONBOARDING_SAVE_PROGRESS: Starting with guest_id={guest_id}, data={data}")
    
    try:
        from custom_auth.models import OnboardingSession

        logger.info(f"ONBOARDING_SAVE_PROGRESS: Attempting to get or create OnboardingSession for guest_id={guest_id}")
        print(f"ONBOARDING_SAVE_PROGRESS: Attempting to get or create OnboardingSession for guest_id={guest_id}")
        
        session, created = OnboardingSession.objects.get_or_create(guest_id=guest_id)
        
        logger.info(f"ONBOARDING_SAVE_PROGRESS: Session {'created' if created else 'found'}: {session.id}")
        print(f"ONBOARDING_SAVE_PROGRESS: Session {'created' if created else 'found'}: {session.id}")
        
        if not session.data:
            session.data = {}
            
        logger.info(f"ONBOARDING_SAVE_PROGRESS: Existing session data: {session.data}")
        print(f"ONBOARDING_SAVE_PROGRESS: Existing session data: {session.data}")
        
        session.data.update(data)
        
        logger.info(f"ONBOARDING_SAVE_PROGRESS: Updated session data: {session.data}")
        print(f"ONBOARDING_SAVE_PROGRESS: Updated session data: {session.data}")
        
        session.save()
        
        logger.info(f"ONBOARDING_SAVE_PROGRESS: Session saved successfully")
        print(f"ONBOARDING_SAVE_PROGRESS: Session saved successfully")
        
        return {"status": "success", "data": session.data}
    except Exception as e:
        # Only send traceback if N8N_TRACEBACK_URL is configured
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={"error": str(e), "source": "onboarding_save_progress", "traceback": traceback.format_exc()})
            except Exception:
                pass  # Don't let N8N webhook errors break the main functionality
        
        logger.error(f"Error in onboarding_save_progress: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"ONBOARDING_SAVE_PROGRESS ERROR: {str(e)}")
        print(f"ONBOARDING_SAVE_PROGRESS TRACEBACK: {traceback.format_exc()}")
        return {"status": "error", "message": "Failed to save progress"}


# -----------------------------------------------------------------------------
# Helper to expose all guest tools
# -----------------------------------------------------------------------------
def get_guest_tools() -> List[Dict[str, Any]]:
    """
    Return the list of guest tool metadata for the OpenAI Responses API.
    """
    return GUEST_TOOLS
