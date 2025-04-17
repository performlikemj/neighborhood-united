"""
Pantry management tools for the OpenAI Responses API integration.

This module implements the pantry management tools defined in the optimized tool structure,
connecting them to the existing pantry management functionality in the application.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from django.utils import timezone
from django.shortcuts import get_object_or_404

from custom_auth.models import CustomUser
from meals.models import PantryItem, MealPlan
from meals.pantry_management import (
    get_user_pantry_items,
    get_expiring_pantry_items,
    determine_items_to_replenish,
)
from meals.email_service import generate_shopping_list as service_generate_shopping_list
from meals.serializers import PantryItemSerializer

logger = logging.getLogger(__name__)

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
                    "type": "string",
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
                        "type": "string",
                        "description": "The ID of the user whose pantry to update"
                    },
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to add"
                    },
                    "item_type": {
                        "type": "string",
                        "description": "Type of the item (e.g., 'Vegetable', 'Meat', 'Grain')"
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Quantity of the item"
                    },
                    "weight_unit": {
                        "type": "string",
                        "description": "Unit of measurement (e.g., 'g', 'kg', 'oz')"
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
                        "type": "string",
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
                        "type": "string",
                        "description": "The ID of the user"
                    },
                    "meal_plan_id": {
                        "type": "string",
                        "description": "The ID of the meal plan to generate the shopping list for"
                    },
                    "include_emergency_supplies": {
                        "type": "boolean",
                        "description": "Whether to include emergency supplies in the shopping list"
                    }
                },
                "required": ["user_id", "meal_plan_id"],
                "additionalProperties": False
        }
    }
]

# Tool implementation functions

def check_pantry_items(user_id: str, item_type: str = None) -> Dict[str, Any]:
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
        logger.error(f"Error checking pantry items for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to check pantry items: {str(e)}"
        }

def add_pantry_item(user_id: str, item_name: str, quantity: float, item_type: str = None, 
                   weight_unit: str = None, expiry_date: str = None) -> Dict[str, Any]:
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
                weight_unit=weight_unit,
                expiry_date=parsed_expiry_date
            )
            
            # Serialize the new item
            serializer = PantryItemSerializer(new_item)
            
            return {
                "status": "success",
                "message": f"Added {item_name} to pantry",
                "pantry_item": serializer.data
            }
            
    except Exception as e:
        logger.error(f"Error adding pantry item for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to add pantry item: {str(e)}"
        }

def get_expiring_items(user_id: str, days: int = 7) -> Dict[str, Any]:
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
            formatted_items.append({
                "name": item.get("name", ""),
                "expiry_date": item.get("expiry_date", ""),
                "days_until_expiry": item.get("days_until_expiry", 0),
                "quantity": item.get("quantity", 0),
                "unit": item.get("unit", "")
            })
        
        return {
            "status": "success",
            "expiring_items": formatted_items,
            "count": len(formatted_items)
        }
        
    except Exception as e:
        logger.error(f"Error getting expiring items for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to get expiring items: {str(e)}"
        }

def generate_shopping_list(user_id: str, meal_plan_id: str, 
                          include_emergency_supplies: bool = False) -> Dict[str, Any]:
    """
    Generate a shopping list based on a meal plan and pantry items.
    
    Args:
        user_id: The ID of the user
        meal_plan_id: The ID of the meal plan to generate the shopping list for
        include_emergency_supplies: Whether to include emergency supplies in the shopping list
        
    Returns:
        Dict containing the generated shopping list
    """
    try:
        # Get the user and meal plan
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        
        # Generate the shopping list
        shopping_list = service_generate_shopping_list(meal_plan.id)
        
        # If include_emergency_supplies is True, add emergency supplies to the shopping list
        if include_emergency_supplies:
            # Get items to replenish for emergency supplies
            emergency_items = determine_items_to_replenish(user)
            
            # Add emergency items to the shopping list
            if "items" not in shopping_list:
                shopping_list["items"] = []
                
            for item in emergency_items:
                shopping_list["items"].append({
                    "name": item.get("name", ""),
                    "quantity": item.get("quantity_needed", 0),
                    "unit": item.get("unit", ""),
                    "category": "Emergency Supplies",
                    "is_emergency_item": True
                })
        
        return {
            "status": "success",
            "shopping_list": shopping_list
        }
        
    except Exception as e:
        logger.error(f"Error generating shopping list for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to generate shopping list: {str(e)}"
        }

# Function to get all pantry management tools
def get_pantry_management_tools():
    """
    Get all pantry management tools for the OpenAI Responses API.
    
    Returns:
        List of pantry management tools in the format required by the OpenAI Responses API
    """
    return PANTRY_MANAGEMENT_TOOLS
