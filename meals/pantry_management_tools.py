"""
Pantry management tools for the OpenAI Responses API integration.

This module implements the pantry management tools defined in the optimized tool structure,
connecting them to the existing pantry management functionality in the application.
"""

import json
import logging
import os
import requests
import traceback
from datetime import datetime, timedelta, timezone as py_tz
from typing import Dict, List, Optional, Any, Union
from shared.utils import generate_user_context
from django.utils import timezone
import pytz
from django.shortcuts import get_object_or_404
from custom_auth.models import CustomUser
from meals.models import PantryItem, MealPlan
from meals.pydantic_models import ShoppingList as ShoppingListSchema, ShoppingCategory, ReplenishItemsSchema
from meals.pantry_management import (
    get_expiring_pantry_items,
    determine_items_to_replenish,
)
from shared.utils import get_openai_client
from meals.serializers import PantryItemSerializer

logger = logging.getLogger(__name__)
n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
# Tool definitions for the OpenAI Responses API
PANTRY_MANAGEMENT_TOOLS = [
    {
        "type": "function",
        "name": "check_pantry_items",
        "description": "Get a list of items in the user's pantry",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user whose pantry to check"
                },
                "item_type": {
                    "type": "string",
                    "description": "Optional filter for specific item types"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "add_pantry_item",
        "description": "Add a new item to the user's pantry",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user whose pantry to update"
                    },
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to add"
                    },
                    "item_type": {
                        "type": "string",
                        "description": "Type of the item being either 'Canned' or 'Dry Goods'"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Number of cans or bags of the item"
                    },
                    "weight": {
                        "type": "number",
                        "description": "Weight of the item per can or bag"
                    },
                    "weight_unit": {
                        "type": "string",
                        "description": "Unit of measurement (e.g., 'g', 'kg', 'oz', 'lb')"
                    },
                    "expiry_date": {
                        "type": "string",
                        "description": "Expiry date in YYYY-MM-DD format"
                    }
                },
                "required": ["user_id", "item_name", "quantity"],
                "additionalProperties": False
            }
    },
    {
        "type": "function",
        "name": "get_expiring_items",
        "description": "Get a list of pantry items that will expire soon",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user whose pantry to check"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default is 7)"
                    }
                },
                "required": ["user_id"]
            },
            "additionalProperties": False
    },
    {
        "type": "function",
        "name": "generate_shopping_list",
        "description": "Generate a shopping list based on a meal plan and pantry items",
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
                    }
                },
                "required": ["user_id", "meal_plan_id"],
                "additionalProperties": False
        }
    } ,
    {
        "type": "function",
        "name": "determine_items_to_replenish",
        "description": "Recommend dried or canned goods the user should replenish to meet their emergency supply goal.",
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
        "name": "set_emergency_supply_goal",
        "description": "Set (or update) the number of days the user wants to keep as an emergency food supply.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user"
                },
                "days": {
                    "type": "integer",
                    "description": "Desired emergency supply goal in days (1–365)"
                },
                "household_member_count": {
                    "type": "integer",
                    "description": "Number of household members the user wants emergency supplies scaled to."
                }
            },
            "required": ["user_id", "days", "household_member_count"],
            "additionalProperties": False
        }
    }
]

# Tool implementation functions

def check_pantry_items(user_id: int, item_type: str = None) -> Dict[str, Any]:
    """
    Get a list of items in the user's pantry.
    
    Args:
        user_id: The ID of the user whose pantry to check
        item_type: Optional filter for specific item types
        
    Returns:
        Dict containing the pantry items
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the pantry items
        query_filters = {'user': user}
        
        if item_type:
            query_filters['item_type'] = item_type
            
        pantry_items = PantryItem.objects.filter(**query_filters)
        # Serialize the pantry items
        serializer = PantryItemSerializer(pantry_items, many=True)
        return {
            "status": "success",
            "pantry_items": serializer.data,
            "count": len(serializer.data)
        }
        
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_pantry_items", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to check pantry items"
        }

def add_pantry_item(user_id: int, item_name: str, quantity: float, item_type: str = None, 
                   weight: float = None, weight_unit: str = None, expiry_date: str = None) -> Dict[str, Any]:
    """
    Add a new item to the user's pantry.
    
    Args:
        user_id: The ID of the user whose pantry to update
        item_name: Name of the item to add
        item_type: Type of the item (e.g., 'Vegetable', 'Meat', 'Grain')
        quantity: Quantity of the item
        weight_unit: Unit of measurement (e.g., 'g', 'kg', 'oz')
        expiry_date: Expiry date in YYYY-MM-DD format
        
    Returns:
        Dict containing the added pantry item
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Parse expiry date if provided
        parsed_expiry_date = None
        if expiry_date:
            parsed_expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
            
        # Check if the item already exists in the pantry
        existing_item = PantryItem.objects.filter(user=user, item_name=item_name).first()
        
        if existing_item:
            # Update the existing item
            existing_item.quantity += quantity
            if item_type:
                existing_item.item_type = item_type
            if weight_unit:
                existing_item.weight_unit = weight_unit
            if parsed_expiry_date:
                existing_item.expiry_date = parsed_expiry_date
                
            existing_item.save()
            
            # Serialize the updated item
            serializer = PantryItemSerializer(existing_item)
            
            return {
                "status": "success",
                "message": f"Updated quantity of {item_name} in pantry",
                "pantry_item": serializer.data
            }
        else:
            
            # Create a new pantry item
            new_item = PantryItem.objects.create(
                user=user,
                item_name=item_name,
                item_type=item_type or "Other",
                quantity=quantity,
                weight_per_unit=weight,
                weight_unit=weight_unit,
                expiration_date=parsed_expiry_date
            )
            
            # Serialize the new item
            serializer = PantryItemSerializer(new_item)
            
            return {
                "status": "success",
                "message": f"Added {item_name} to pantry",
                "pantry_item": serializer.data
            }
            
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"add_pantry_item", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to add pantry item"
        }

def get_expiring_items(user_id: int, days: int = 7) -> Dict[str, Any]:
    """
    Get a list of pantry items that will expire soon.
    
    Args:
        user_id: The ID of the user whose pantry to check
        days: Number of days to look ahead (default is 7)
        
    Returns:
        Dict containing the expiring pantry items
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the expiring pantry items
        expiring_items = get_expiring_pantry_items(user, days_ahead=days)
        
        # Format the response
        formatted_items = []
        for item in expiring_items:
            formatted_item = {
                "name": item.get("name", ""),
                "expiration_date": item.get("expiration_date", ""),
                "quantity": item.get("quantity", 0),
                "type": item.get("item_type", ""),
                "notes": item.get("notes", "")
            }
            formatted_items.append(formatted_item)
        
        return {
            "status": "success",
            "expiring_items": formatted_items,
            "count": len(formatted_items)
        }
        
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_expiring_items", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": f"Failed to get expiring items"
        }

def generate_shopping_list(user_id: int, meal_plan_id: int):
    """
    Lightweight helper that **only** builds (or retrieves) the shopping‑list JSON for
    a given `MealPlan`.

    • No email rendering / sending.  
    • Returns a Python `dict` that conforms to `meals.pydantic_models.ShoppingList`.  
    • Raises `ValueError` if the list cannot be generated or parsed.

    This is intended for direct use by the MealPlanningAssistant tool‑call so that the
    caller can decide what to do with the resulting data (display, further processing,
    etc.).
    """
    import json
    from collections import defaultdict
    from django.db.models import Sum
    from meals.models import (
        MealPlan,
        ShoppingList as ShoppingListModel,
        MealPlanMealPantryUsage,
        PantryItem,
        MealAllergenSafety,
    )
    from meals.serializers import MealPlanSerializer
    from meals.meal_plan_service import is_chef_meal
    from meals.pantry_management import (
        get_user_pantry_items,
        get_expiring_pantry_items,
        determine_items_to_replenish,
    )
    from meals.pydantic_models import ShoppingList as ShoppingListSchema, ShoppingCategory
    user = get_object_or_404(CustomUser, id=user_id)
    
    # --- 0. Fetch objects ----------------------------------------------------
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
    
    household_member_count = getattr(user, "household_member_count", 1) or 1

    # Shortcut: if a validated shopping list already exists → return it.
    existing = ShoppingListModel.objects.filter(meal_plan=meal_plan).first()
    if existing:
        try:
            return json.loads(existing.items)
        except Exception:
            # fall through to regeneration
            pass

    # --- 1. Gather prompt context -------------------------------------------
    meal_plan_data = MealPlanSerializer(meal_plan).data

    # Filter out past meals relative to the user's local date
    try:
        from zoneinfo import ZoneInfo
        user_tz = ZoneInfo(getattr(user, 'timezone', 'UTC'))
    except Exception:
        try:
            import pytz as _p
            user_tz = _p.timezone(getattr(user, 'timezone', 'UTC'))
        except Exception:
            user_tz = py_tz.utc
    today_local = timezone.now().astimezone(user_tz).date()

    from datetime import timedelta as _td
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    start_idx = meal_plan.week_start_date.weekday()
    ordered_names = [day_names[(start_idx + i) % 7] for i in range(7)]
    day_to_date = {ordered_names[i]: (meal_plan.week_start_date + _td(days=i)) for i in range(7)}

    original_meals = meal_plan_data.get('meals', []) or []
    filtered_meals = [m for m in original_meals if (day_to_date.get(m.get('day')) is None or day_to_date[m.get('day')] >= today_local)]

    if not filtered_meals:
        # nothing to generate
        return {"items": []}

    meal_plan_data['meals'] = filtered_meals
    user_context = generate_user_context(user) or "No additional user context."

    # Chef & substitution info
    substitution_info = []
    chef_meals_present = False
    for meal in meal_plan.meal.all():
        if is_chef_meal(meal):
            chef_meals_present = True
            continue
        qs = MealAllergenSafety.objects.filter(
            meal=meal, user=user, is_safe=False
        ).exclude(substitutions__isnull=True).exclude(substitutions={})
        for check in qs:
            for original, subs in (check.substitutions or {}).items():
                if subs:
                    substitution_info.append(
                        {
                            "meal_name": meal.name,
                            "original_ingredient": original,
                            "substitutes": subs,
                        }
                    )

    # Pantry & leftovers
    bridging_qs = (
        MealPlanMealPantryUsage.objects.filter(meal_plan_meal__meal_plan=meal_plan)
        .values("pantry_item")
        .annotate(total_used=Sum("quantity_used"))
    )
    bridging_usage = {row["pantry_item"]: float(row["total_used"] or 0.0) for row in bridging_qs}
    
    leftover_info = []
    for pid, used in bridging_usage.items():
        try:
            pi = PantryItem.objects.get(id=pid)
        except PantryItem.DoesNotExist:
            continue
        total = pi.quantity * float(pi.weight_per_unit or 1.0)
        leftover = max(total - used, 0.0)
        leftover_info.append(f"{pi.item_name} leftover: {leftover} {pi.weight_unit or ''}")
    bridging_leftover_str = "; ".join(leftover_info) if leftover_info else "No leftover data available"

    # Pantry and expiring items
    try:
        user_pantry_items = get_user_pantry_items(user)
    except Exception:
        user_pantry_items = []
        
    try:
        expiring_items = get_expiring_pantry_items(user)
        expiring_items_str = ", ".join(i["name"] for i in expiring_items) if expiring_items else "None"
    except Exception:
        expiring_items_str = "None"

    shopping_category_list = [c.value for c in ShoppingCategory]

    # Format substitution prompt segment
    substitution_str = ""
    if substitution_info:
        substitution_str = "Ingredient substitution information:\n" + "\n".join(
            f"- In {s['meal_name']}, replace {s['original_ingredient']} with {', '.join(s['substitutes'])}"
            for s in substitution_info
        )

    chef_note = (
        "IMPORTANT: Some meals are chef‑created and must be prepared exactly as specified. "
        "Include all ingredients for chef meals without alternatives."
        if chef_meals_present
        else ""
    )

    # --- 2. Call OpenAI -------------------------------------------------------
    try:
        response = get_openai_client().responses.create(
            model="gpt-5-mini",
            input=[
                {
                    "role": "developer",
                    "content": (
                        """
                        Generate a shopping list in JSON format according to the defined schema, factoring in a user's preferred serving size for each meal. Return one entry per unique ingredient and unit; if multiple meals require the same ingredient with the same unit, combine their quantities and list all meal names in `meal_names`. Follow the structure provided for the `ShoppingList` and include the required fields for each `ShoppingListItem`.

                        - **ShoppingList**: This is the main container that holds a list of `ShoppingListItem` objects.
                        - **ShoppingListItem**: Each item in the list should have the following attributes:
                        - **meal_names**: The names of the meals the ingredient is for.
                        - **ingredient**: The specific ingredient needed.
                        - **quantity**: Numeric-only amount required, adjusted for serving size. Use numbers only (e.g., 200, 1.5, 12). Do not include text or units here.
                        - **unit**: The unit of measurement for the quantity. Place all unit text here (e.g., "grams", "ml", "pieces").
                        - **notes**: Any special notes regarding the item (optional).
                        - **category**: The category to which the item belongs (such as 'vegetables', 'dairy', etc.).

                        # Output Format

                        The output should be a JSON object following the structure of the `ShoppingList`. Ensure that each `ShoppingListItem` contains all the required fields.

                        # Examples

                        **Input:**
                        Generate a shopping list for two meals with preferred serving sizes.

                        **Output (numeric-only quantities):**

                        ```json
                        {
                        "items": [
                            {
                            "meal_names": ["Spaghetti Bolognese"],
                            "ingredient": "Spaghetti",
                            "quantity": 300,
                            "unit": "grams",
                            "notes": null,
                            "category": "pasta"
                            },
                            {
                            "meal_names": ["Spaghetti Bolognese"],
                            "ingredient": "Ground Beef",
                            "quantity": 750,
                            "unit": "grams",
                            "notes": "Leaner cuts preferred",
                            "category": "meat"
                            },
                            {
                            "meal_names": ["Caesar Salad"],
                            "ingredient": "Romaine Lettuce",
                            "quantity": 2,
                            "unit": "heads",
                            "notes": "Fresh and crisp",
                            "category": "vegetables"
                            },
                            {
                            "meal_names": ["Caesar Salad"],
                            "ingredient": "Parmesan Cheese",
                            "quantity": 75,
                            "unit": "grams",
                            "notes": "Grated",
                            "category": "dairy"
                            }
                        ]
                        }
                        ```

                        # Notes

                        - Ensure to forbid any extra fields that are not specified in the schema.
                        - `notes` field is optional and can be `null` if no special notes are necessary.
                        - Adhere strictly to the schema provided for compatibility with `ShoppingList`.
                        """
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Answer in the user's preferred language: {user.preferred_language or 'English'}.\n"
                        f"Generate a shopping list based on the following meals: {json.dumps(meal_plan_data)}.\n"
                        f"User context: {user_context}.\n"
                        f"Bridging leftover info: {bridging_leftover_str}.\n"
                        f"The user has the following pantry items: {', '.join(user_pantry_items)}.\n"
                        f"Household member count: {household_member_count}.\n"
                        f"Expiring pantry items: {expiring_items_str}.\n"
                        f"Available shopping categories: {shopping_category_list}.\n"
                        f"{substitution_str}\n{chef_note}\n"
                        "IMPORTANT: For ingredients in non‑chef meals that have substitution options, include BOTH the "
                        "original ingredient AND its substitutes, clearly marking them as alternatives."
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "shopping_list",
                    "schema": ShoppingListSchema.model_json_schema(),
                }
            },
            temperature=0.4,
        )
        shopping_list_raw = response.output_text
    except Exception as e:
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_shopping_list", "traceback": traceback.format_exc()})
        raise ValueError("Failed to generate shopping list.") from e

    # --- 3. Validate & persist ----------------------------------------------
    try:
        shopping_list_dict = json.loads(shopping_list_raw)
        # validate with Pydantic (raises if invalid)
        ShoppingListSchema(**shopping_list_dict)
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_shopping_list", "traceback": traceback.format_exc()})
        raise ValueError("OpenAI returned invalid shopping list JSON.") from e

    # Store (creates or updates) but do *not* email
    ShoppingListModel.objects.update_or_create(
        meal_plan=meal_plan, defaults={"items": json.dumps(shopping_list_dict)}
    )

    return shopping_list_dict

def determine_items_to_replenish(user_id: int):
    """
    Recommend pantry items the user should replenish to satisfy their emergency
    supply goal. Returns a dict matching `ReplenishItemsSchema`.
    """
    import json
    from pydantic import ValidationError
    from django.shortcuts import get_object_or_404
    from custom_auth.models import CustomUser

    user = get_object_or_404(CustomUser, id=user_id)

    # Early exit if the user hasn't set a goal
    goal_days = user.emergency_supply_goal or 0
    
    # Fetch preferred servings (fallback to 1 if missing or mis‑spelled column)
    household_member_count = (
        getattr(user, "household_member_count", None)
        or 1
    )
    
    if goal_days <= 0:
        return {
            "status": "success",
            "items_to_replenish": [],
            "household_member_count": int(household_member_count),
            "message": "No emergency supply goal set."
        }

    # Current pantry snapshot
    pantry_items = user.pantry_items.all()
    pantry_summary = ", ".join(f"{pi.item_name} (x{pi.quantity})" for pi in pantry_items) or "None"

    # Prompts for OpenAI
    sys_prompt = (
        """
        Given the user's context, current pantry items, and emergency supply goal, recommend a JSON list of dried or canned goods the user should replenish. Ensure recommendations respect dietary restrictions, allergies, and are suitable for long-term storage.

        - **Contextual Understanding**: Take into account the user's dietary preferences, potential allergies, and the type of storage available.
        - **Inventory Assessment**: Analyze the current pantry items provided by the user to determine which essential dried or canned goods need replenishment.
        - **Supply Goals**: Align recommendations with the user's emergency supply goals to ensure there is adequate food available for a specified duration.
        - **Long-Term Storage Suitability**: Recommend items that are appropriate for long-term storage without significant risk of spoilage.
        - **Compliance with Schema**: Ensure the output follows the ReplenishItemsSchema provided.

        # Steps

        1. **Assess Current Stock**: Review the current items in the user's pantry and identify any gaps based on emergency supply goals.
        2. **Dietary Considerations**: Incorporate any dietary restrictions or allergies to ensure safe and suitable recommendations.
        3. **Item Selection**: Choose dried or canned goods that are suitable for prolonged storage, factoring in nutritional variety.
        4. **Quantitative Recommendations**: Calculate the quantity of each item needed to reach the emergency supply goal.
        5. **Schema Alignment**: Format the recommendations into a JSON structure that aligns with the ReplenishItemsSchema.

        # Output Format

        The response should be a JSON following the ReplenishItemsSchema structure, listing items to replenish, each with its name, quantity, and unit of measurement.

        # Examples

        **Input**: 
        - Current pantry: ["canned beans", "rice"]
        - Emergency supply goal: "sufficient food for 30 days"
        - Dietary restrictions: "vegetarian"
        - Allergies: "peanuts"

        **Output**:
        ```json
        {
        "items_to_replenish": [
            {"item_name": "canned lentils", "quantity": 10, "unit": "cans"},
            {"item_name": "dried pasta", "quantity": 5, "unit": "kilograms"},
            {"item_name": "canned tomatoes", "quantity": 8, "unit": "cans"}
        ]
        }
        ```

        # Notes

        - Verify that suggested items do not conflict with any of the user's allergies or dietary restrictions.
        - Include a variety of items to ensure nutritional balance in the recommendations.
        - Ensure long-lasting shelf life is a priority in item selection.
        """
    )
    usr_prompt = (
        f"The user has an emergency supply goal of {goal_days} days and needs to prepare meals for "
        f"{household_member_count} household members with individual dietary needs (see user context for details).\n"
        f"User Context:\n{generate_user_context(user)}\n"
        f"Current Pantry Items:\n{pantry_summary}\n"
        "When calculating quantities, multiply daily needs by the number of servings.\n"
        "Respond in JSON adhering to the schema `replenish_items`."
    )

    try:
        response = get_openai_client().responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "developer", "content": sys_prompt},
                {"role": "user", "content": usr_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "replenish_items",
                    "schema": ReplenishItemsSchema.model_json_schema(),
                }
            },
            temperature=0.3,
        )
        raw = response.output_text
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"determine_items_to_replenish", "traceback": traceback.format_exc()})
        return {"status": "error", "message": "Failed to generate recommendations."}

    # Validate
    try:
        parsed = json.loads(raw)
        validated = ReplenishItemsSchema.model_validate(parsed)
        return {
            "status": "success",
            "items_to_replenish": [item.model_dump() for item in validated.items_to_replenish],
            "household_member_count": int(household_member_count)
        }
    except (json.JSONDecodeError, ValidationError) as e:
        return {"status": "error", "message": "Assistant produced invalid JSON."}
    
def set_emergency_supply_goal(user_id: int, days: int, household_member_count: int) -> Dict[str, Any]:
    """
    Update the user's emergency supply goal (number of days of food to keep on hand) and household member count.

    Args:
        user_id: ID of the CustomUser.
        days: Goal in days (must be 1–365).
        household_member_count: Number of household members (must be 1–20).

    Returns:
        Dict with status and message.
    """
    from django.shortcuts import get_object_or_404
    from custom_auth.models import CustomUser

    # Validate `days`
    try:
        days_int = int(days)
        if days_int < 1 or days_int > 365:
            raise ValueError("days must be between 1 and 365.")
    except (ValueError, TypeError) as err:
        return {
            "status": "error",
            "message": f"Invalid 'days' value: {err}"
        }

    # Validate `household_member_count`
    try:
        servings_int = int(household_member_count)
        if servings_int < 1 or servings_int > 20:
            raise ValueError("household_member_count must be between 1 and 20.")
    except (ValueError, TypeError) as err:
        return {
            "status": "error",
            "message": f"Invalid 'household_member_count' value: {err}"
        }

    try:
        user = get_object_or_404(CustomUser, id=user_id)
        
        old_goal = user.emergency_supply_goal
        old_household_member_count = getattr(user, "household_member_count", None)
        
        user.emergency_supply_goal = days_int
        user.household_member_count = servings_int
        user.save(update_fields=["emergency_supply_goal", "household_member_count"])

        return {
            "status": "success",
            "message": (
                f"Emergency supply goal set to {days_int} day(s) "
                f"and household member count updated to {servings_int}."
            ),
            "emergency_supply_goal": days_int,
            "household_member_count": servings_int
        }
    except Exception as e:
        # Send traceback to N8N via webhook at N8N_TRACEBACK_URL 
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"set_emergency_supply_goal", "traceback": traceback.format_exc()})
        return {
            "status": "error",
            "message": "Failed to update emergency supply goal."
        }

# Function to get all pantry management tools
def get_pantry_management_tools():
    """
    Get all pantry management tools for the OpenAI Responses API.
    
    Returns:
        List of pantry management tools in the format required by the OpenAI Responses API
    """
    return PANTRY_MANAGEMENT_TOOLS
