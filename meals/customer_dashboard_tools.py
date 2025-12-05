"""
Customer‐Dashboard tools for the OpenAI Responses API integration.

This module implements the tools available to authenticated customer users:
 - adjust_week_shift        : Increment or decrement the user's week shift
 - reset_current_week       : Reset the user's week shift to the current week
 - update_goal              : Create or update the user's goal tracking entry
 - get_goal                 : Retrieve the user's current goal tracking entry
 - get_user_info            : Return the user's profile plus postal code
 - access_past_orders       : Retrieve all past orders linked to the user's meal plans
"""

import logging
import requests
import traceback
import os
from typing import Any, Dict, List
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Min
from datetime import timedelta
from custom_auth.models import CustomUser, UserRole, Address
from custom_auth.serializers import CustomUserSerializer, AddressSerializer
from meals.models import MealPlan, Order
from meals.models import DietaryPreference, CustomDietaryPreference
from meals.serializers import OrderSerializer
from customer_dashboard.models import UserSummary
# Goal tracking removed - health tracking feature deprecated

logger = logging.getLogger(__name__)

n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")

# -----------------------------------------------------------------------------
# Tool metadata definitions (as required by the OpenAI Responses API)
# -----------------------------------------------------------------------------
CUSTOMER_DASHBOARD_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "name": "adjust_week_shift",
        "description": (
            "Increment or decrement the user's week_shift by week_shift_increment, "
            "used to shift the user's view of past and future plans and orders, "
            "under the constraint that only present and future plans can be edited."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose week shift to adjust"
                },
                "week_shift_increment": {
                    "type": "integer",
                    "description": "Number of weeks to shift (positive or negative)"
                }
            },
            "required": ["user_id", "week_shift_increment"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "reset_current_week",
        "description": (
            "Reset the user's week_shift back to zero, "
            "used to reset the user's view of past and future plans and orders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose week shift to reset"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "update_goal",
        "description": (
            "Create or update the user's goal and description of the goal. "
            "Fields not provided will be left unchanged. "
            "The goal is used to track the user's progress towards their goal."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose goal to update"
                },
                "goal_name": {
                    "type": "string",
                    "description": "Optional new name for the goal"
                },
                "goal_description": {
                    "type": "string",
                    "description": "Optional new description for the goal"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_goal",
        "description": (
            "Retrieve the user's current goal tracking entry. "
            "The goal is used to track the user's progress towards their goal. "
            "Their goal is used in all decisions and recommendations made by the AI assistant."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose goal to retrieve"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "access_past_orders",
        "description": (
            "Retrieve all past orders (Completed, Cancelled, Refunded) linked to the user's meal plans. "
            "This is used to give context to the AI assistant about the user's past orders, "
            "and to help the AI assistant make recommendations for the user's next orders."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose past orders to fetch"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    }
    ,
    {
        "type": "function",
        "name": "update_user_settings",
        "description": (
            "Create or update the user's profile‑level settings such as dietary preferences, "
            "allergies, email‑notification choices, and general options.  "
            "Fields omitted from the call remain unchanged."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": { "type": "integer" },
                "dietary_preferences": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": (
                        # Start of Selection  
                        "List of standard/common dietary-preference names (e.g. 'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium', 'High-Protein', 'Dairy-Free', 'Nut-Free', 'Raw Food', 'Whole 30', 'Low-FODMAP', 'Diabetic-Friendly', 'Everything'). "  
                        "The user can also specify custom dietary-preference names that are not already in the dietary-preference list."  
                    )
                },
                "custom_dietary_preferences": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "List of custom dietary‑preference names that are not already in the dietary‑preference list"
                },
                "allergies": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": (
                        "List of standard allergy names (e.g. 'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', "
                        "'Soy', 'Fish', 'Shellfish', 'Sesame', 'Mustard', 'Celery', 'Lupin', 'Sulfites', "
                        "'Molluscs', 'Corn', 'Gluten', 'Kiwi', 'Latex', 'Pine Nuts', 'Sunflower Seeds', "
                        "'Poppy Seeds', 'Fennel', 'Peach', 'Banana', 'Avocado', 'Chocolate', 'Coffee', "
                        "'Cinnamon', 'Garlic', 'Chickpeas', 'Lentils', 'None'). "
                        "The user can also specify custom allergy names that are not already in the allergy list."
                    )
                },
                "custom_allergies": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "List of user‑defined allergy names"
                },
                "preferred_language": {
                    "type": "string",
                    "description": "Change the language the assistant will use to communicate with the user. "
                        "The backend will use the language code such as 'en', 'ja', 'es', etc."
                },
                "unsubscribed_from_emails": { 
                    "type": "boolean",
                    "description": "Set to true to unsubscribe from all emails, false to receive emails"
                },
                "household_member_count":  {
                    "type": "integer",
                    "description": "Default number of household members the user wants meals scaled to"
                },
                "emergency_supply_goal": {
                    "type": "integer",
                    "description": "Desired number of emergency‑supply days the user wants to have on hand."
                },
                "phone_number": { 
                    "type": "string",
                    "description": "The user's phone number. This is used to send text messages to the user or contact them in case of emergency."
                },
                "user_timezone":     { 
                    "type": "string",
                    "description": "The user's timezone. This is used to better understand the user's current time and to provide more accurate recommendations."
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_user_settings",
        "description": "Retrieve the user's current profile settings.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": { "type": "integer" }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
]

# -----------------------------------------------------------------------------
# Tool implementations
# -----------------------------------------------------------------------------
def adjust_week_shift(user_id: int, week_shift_increment: int) -> Dict[str, Any]:
    """
    Increment or decrement the user's week_shift by week_shift_increment,
    but never below zero.
    """
    try:
        user  = get_object_or_404(CustomUser, id=user_id)
        role  = get_object_or_404(UserRole,   user=user)
        if role.current_role == "chef":
            return {"status": "error", "message": "Chefs may not use this tool."}

        # ------------------------------------------------------------------
        # Determine the earliest MealPlan week available for this user
        # This becomes the *lower* bound for week_shift (negative or zero).
        # ------------------------------------------------------------------
        today           = timezone.now().date()
        current_monday  = today - timedelta(days=today.weekday())  # start of this week

        earliest_plan   = (
            MealPlan.objects
            .filter(user=user)
            .aggregate(Min("week_start_date"))
            .get("week_start_date__min")
        )

        if earliest_plan:
            # Number of weeks (≥ 0) between the earliest plan and the current week
            weeks_back = (current_monday - earliest_plan).days // 7
            min_shift_allowed = -weeks_back     # negative value or 0
        else:
            # No plans yet → don't allow negative shifts
            min_shift_allowed = 0


        # Optional upper bound (e.g., 52 weeks into the future)
        MAX_FUTURE_WEEKS = 52
        max_shift_allowed = MAX_FUTURE_WEEKS

        # ------------------------------------------------------------------
        # Apply the increment, then clamp between min and max
        # ------------------------------------------------------------------
        raw_shift = user.week_shift + week_shift_increment
        new_shift = max(min(raw_shift, max_shift_allowed), min_shift_allowed)

        # Persist if anything changed
        if new_shift != user.week_shift:
            user.week_shift = new_shift
            user.save()


        return {
            "status"      : "success",
            "message"     : f"Week shift adjusted to {new_shift} (min {min_shift_allowed}, max {max_shift_allowed}) in order to review meals in the past or future.",
            "current_time": f"Understand the current time is {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"adjust_week_shift", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}


def reset_current_week(user_id: int) -> Dict[str, Any]:
    """
    Reset the user's week_shift back to zero.
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        role = get_object_or_404(UserRole, user=user)
        if role.current_role == 'chef':
            return {"status": "error", "message": "Chefs may not use this tool."}

        user.week_shift = 0
        user.save()
        return {
            "status": "success",
            "message": "Week shift reset to the current week.",
            "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"reset_current_week", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}


def update_goal(user_id: int, goal_name: str = None, goal_description: str = None) -> Dict[str, Any]:
    """
    Legacy function - goal tracking has been removed.
    """
    return {
        "status": "error",
        "message": "Goal tracking has been removed from this application.",
        "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_goal(user_id: int) -> Dict[str, Any]:
    """
    Legacy function - goal tracking has been removed.
    """
    return {
        "status": "error",
        "message": "Goal tracking has been removed from this application.",
        "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def access_past_orders(user_id: int) -> Dict[str, Any]:
    """
    Retrieve all past orders (Completed, Cancelled, Refunded) linked to the user's meal plans.
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        role = get_object_or_404(UserRole, user=user)
        if role.current_role == 'chef':
            return {"status": "error", "message": "Chefs may not use this tool."}

        plans = MealPlan.objects.filter(
            user=user,
            order__status__in=["Completed", "Cancelled", "Refunded"]
        ).distinct()

        if not plans.exists():
            return {
                "status": "info",
                "message": "No past orders found.",
                "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        orders = Order.objects.filter(meal_plan__in=plans)
        serialized = OrderSerializer(orders, many=True).data

        return {
            "status": "success",
            "orders": serialized,
            "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"access_past_orders", "traceback": traceback.format_exc()})
        return {"status": "error", "message": str(e)}


# --------------------------------------------------------------------------
#  User‑settings tools
# --------------------------------------------------------------------------
def update_user_settings(
    user_id: int,
    dietary_preferences: List[str] = None,
    custom_dietary_preferences: List[str] = None,
    allergies: List[str] = None,
    custom_allergies: List[str] = None,
    preferred_language: str = None,
    unsubscribed_from_emails: bool = None,
    household_member_count: int = None,
    emergency_supply_goal: int = None,
    phone_number: str = None,
    user_timezone: str = None
) -> Dict[str, Any]:
    """
    Create or update the user's high‑level profile settings.
    Only fields supplied in the call are changed.
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        summary = get_object_or_404(UserSummary, user=user)
        role = get_object_or_404(UserRole, user=user)
        if role.current_role == "chef":
            return {"status": "error", "message": "Chefs may not use this tool."}

        # ───────────────────────────────────────────────────────────
        # Validate incoming option lists to avoid silent failures
        # ───────────────────────────────────────────────────────────
        # 1) Allergies must match one of the predefined choices
        if allergies is not None:
            valid_allergy_set = {opt[0].lower() for opt in CustomUser.ALLERGY_CHOICES}
            invalid_allergies  = [item for item in allergies if item.lower() not in valid_allergy_set]
            if invalid_allergies:
                return {
                    "status": "error",
                    "message": f"Unknown allergy values: {', '.join(invalid_allergies)}"
                }

        # 2) Dietary preferences must correspond to existing DietaryPreference rows
        if dietary_preferences is not None:
            # Create a case‑insensitive map of existing names
            existing_names_qs = DietaryPreference.objects.values_list("name", flat=True)
            name_lookup = {name.lower(): name for name in existing_names_qs}
            unknown_prefs = [p for p in dietary_preferences if p.lower() not in name_lookup]
            if unknown_prefs:
                return {
                    "status": "error",
                    "message": f"Unknown dietary preference values: {', '.join(unknown_prefs)}"
                }
            # Replace requested names with canonical DB casing
            dietary_preferences = [name_lookup[p.lower()] for p in dietary_preferences]

        updated: Dict[str, Any] = {}

        # ---- Many‑to‑many dietary preferences --------------------------------
        if dietary_preferences is not None:
            prefs_qs = DietaryPreference.objects.filter(name__in=dietary_preferences)
            user.dietary_preferences.set(prefs_qs)
            updated["dietary_preferences"] = list(prefs_qs.values_list("name", flat=True))

        if custom_dietary_preferences is not None:
            custom_objs = []
            for name in custom_dietary_preferences:
                obj, _ = CustomDietaryPreference.objects.get_or_create(name=name)
                custom_objs.append(obj)
            user.custom_dietary_preferences.set(custom_objs)
            updated["custom_dietary_preferences"] = [o.name for o in custom_objs]

        # ---- Array‑based allergy fields --------------------------------------
        if allergies is not None:
            # Preserve original casing from the predefined list
            canonical_map = {opt[0].lower(): opt[0] for opt in CustomUser.ALLERGY_CHOICES}
            user.allergies = [canonical_map[a.lower()] for a in allergies]
            updated["allergies"] = user.allergies

        if custom_allergies is not None:
            user.custom_allergies = custom_allergies
            updated["custom_allergies"] = custom_allergies

        # ---- Simple scalar fields --------------------------------------------
        scalar_map = {
            "preferred_language": preferred_language,
            "unsubscribed_from_emails": unsubscribed_from_emails,
            "household_member_count": household_member_count,
            "emergency_supply_goal": emergency_supply_goal,
            "phone_number": phone_number,
            "timezone": user_timezone,
        }
        for field, value in scalar_map.items():
            if value is not None:
                setattr(user, field, value)
                updated[field] = value

        if updated:
            user.save()
            # Reset the user summary by setting it to pending
            summary.summary = "No summary available"
            summary.status = "pending"
            summary.save(update_fields=["summary", "status"])
            
            # Log the status change for debugging
            logger.info(f"UserSummary reset for user {user_id}: status={summary.status}, summary={summary.summary[:20]}...")
        
        return {
            "status": "success",
            "message": "User settings updated.",
            "updated_fields": updated,
            "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"update_user_settings", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to update user settings"}


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """
    Retrieve the user's current profile settings.
    """
    try:
        user = get_object_or_404(CustomUser, id=user_id)
        role = get_object_or_404(UserRole, user=user)
        if role.current_role == "chef":
            return {"status": "error", "message": "Chefs may not use this tool."}

        serializer = CustomUserSerializer(user)
        return {
            "status": "success",
            "user_settings": serializer.data,
            "current_time": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_user_settings", "traceback": traceback.format_exc()})
        return {"status": "error", "message": f"Failed to get user settings"}


# -----------------------------------------------------------------------------
# Helper to expose all customer‐dashboard tools
# -----------------------------------------------------------------------------
def get_customer_dashboard_tools() -> List[Dict[str, Any]]:
    """
    Return the list of customer‐dashboard tool metadata for the OpenAI Responses API.
    """
    return CUSTOMER_DASHBOARD_TOOLS