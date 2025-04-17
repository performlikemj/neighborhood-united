"""
Chef connection tools for the OpenAI Responses API integration.

This module implements the chef connection tools defined in the optimized tool structure,
connecting them to the existing chef connection functionality in the application.
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.forms.models import model_to_dict

from custom_auth.models import CustomUser
from chefs.models import Chef
from meals.models import Meal, Order, OrderMeal

logger = logging.getLogger(__name__)

# Tool definitions for the OpenAI Responses API
CHEF_CONNECTION_TOOLS = [
    {
        "type": "function",
        "name": "find_local_chefs",
        "description": "Find chefs that serve the user's area",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user"
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional location to search in (defaults to user's saved location)"
                    },
                    "cuisine_type": {
                        "type": "string",
                        "description": "Optional cuisine type to filter by"
                    },
                    "max_distance": {
                        "type": "number",
                        "description": "Maximum distance in miles (default is 10)"
                    }
                },
                "required": ["user_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_chef_details",
        "description": "Get detailed information about a chef",
        "parameters": {
                "type": "object",
                "properties": {
                    "chef_id": {
                        "type": "string",
                        "description": "The ID of the chef"
                    }
                },
                "required": ["chef_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "view_chef_meals",
        "description": "View meals offered by a specific chef",
        "parameters": {
                "type": "object",
                "properties": {
                    "chef_id": {
                        "type": "string",
                        "description": "The ID of the chef"
                    },
                    "meal_type": {
                        "type": "string",
                        "description": "Optional meal type to filter by (e.g., Breakfast, Lunch, Dinner)"
                    },
                    "dietary_preference": {
                        "type": "string",
                        "description": "Optional dietary preference to filter by"
                    }
                },
                "required": ["chef_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "place_chef_meal_order",
        "description": "Place an order for a chef meal",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user placing the order"
                    },
                    "chef_id": {
                        "type": "string",
                        "description": "The ID of the chef"
                    },
                    "meal_id": {
                        "type": "string",
                        "description": "The ID of the meal to order"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of servings to order"
                    },
                    "delivery_date": {
                        "type": "string",
                        "description": "Requested delivery date in YYYY-MM-DD format"
                    },
                    "special_instructions": {
                        "type": "string",
                        "description": "Optional special instructions for the order"
                    }
                },
                "required": ["user_id", "chef_id", "meal_id", "quantity", "delivery_date"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_order_details",
        "description": "Get details of a chef meal order",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user who placed the order"
                },
                "order_id": {
                    "type": "string",
                    "description": "The ID of the order to retrieve"
                }
            },
            "required": ["user_id", "order_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "cancel_order",
        "description": "Cancel a chef meal order",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user who placed the order"
                },
                "order_id": {
                    "type": "string",
                    "description": "The ID of the order to cancel"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation"
                }
            },
            "required": ["user_id", "order_id"],
            "additionalProperties": False
        }
    }
]

# Tool implementation functions

def find_local_chefs(user_id: str, location: str = None, cuisine_type: str = None, 
                    max_distance: float = 10.0) -> Dict[str, Any]:
    """
    Find chefs that serve the user's area.
    
    Args:
        user_id: The ID of the user
        location: Optional location to search in (defaults to user's saved location)
        cuisine_type: Optional cuisine type to filter by
        max_distance: Maximum distance in miles (default is 10)
        
    Returns:
        Dict containing the found chefs
    """
    from chefs.serializers import ChefSerializer

    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the location to search in
        search_location = location or user.location
        
        if not search_location:
            return {
                "status": "error",
                "message": "No location provided and user has no saved location"
            }
            
        # Build the query
        query = Q(is_active=True)
        query &= Q(service_radius__gte=max_distance)
        
        if cuisine_type:
            query &= Q(cuisine_types__name__icontains=cuisine_type)
            
        # Find chefs that serve the area
        # Note: In a real implementation, you would use geospatial queries
        # to find chefs within the specified distance of the location
        chefs = Chef.objects.filter(query)
        
        # Serialize the chefs
        serializer = ChefSerializer(chefs, many=True)
        
        return {
            "status": "success",
            "chefs": serializer.data,
            "count": len(serializer.data),
            "location": search_location,
            "max_distance": max_distance
        }
        
    except Exception as e:
        logger.error(f"Error finding local chefs for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to find local chefs: {str(e)}"
        }

def get_chef_details(chef_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a chef.
    
    Args:
        chef_id: The ID of the chef
        
    Returns:
        Dict containing the chef details
    """
    from chefs.serializers import ChefSerializer

    try:
        # Get the chef
        chef = get_object_or_404(Chef, id=chef_id)
        
        # Serialize the chef
        serializer = ChefSerializer(chef, context={'detailed': True})
        
        # Get the chef's rating
        rating = None
        
        # Get the chef's specialties
        specialties = []
        
        # Get the chef's availability
        availability = {}
        
        return {
            "status": "success",
            "chef": serializer.data,
            "rating": rating,
            "specialties": specialties,
            "availability": availability
        }
        
    except Exception as e:
        logger.error(f"Error getting chef details for chef {chef_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to get chef details: {str(e)}"
        }

def view_chef_meals(chef_id: str, meal_type: str = None, 
                   dietary_preference: str = None) -> Dict[str, Any]:
    """
    View meals offered by a specific chef.
    
    Args:
        chef_id: The ID of the chef
        meal_type: Optional meal type to filter by
        dietary_preference: Optional dietary preference to filter by
        
    Returns:
        Dict containing the chef's meals
    """
    try:
        # Get the chef
        chef = get_object_or_404(Chef, id=chef_id)
        
        # Build the query for Meal model
        query = Q(chef=chef, is_active=True)
        
        if meal_type:
            query &= Q(meal_type=meal_type)
            
        if dietary_preference:
            query &= Q(dietary_preferences__name__icontains=dietary_preference) | \
                    Q(custom_dietary_preferences__name__icontains=dietary_preference)
            
        # Get the chef's meals (using Meal model)
        meals = Meal.objects.filter(query)
        
        # Serialize the meals using model_to_dict
        serialized_meals = [model_to_dict(meal, fields=['id', 'name', 'description', 'price', 'meal_type', 'image']) for meal in meals]
        # Add related fields manually if needed (e.g., dietary preference names)
        for i, meal in enumerate(meals):
            serialized_meals[i]['dietary_preferences'] = list(meal.dietary_preferences.values_list('name', flat=True))
            serialized_meals[i]['custom_dietary_preferences'] = list(meal.custom_dietary_preferences.values_list('name', flat=True))
        
        return {
            "status": "success",
            "chef_name": chef.user.username,
            "meals": serialized_meals,
            "count": len(serialized_meals)
        }
        
    except Exception as e:
        logger.error(f"Error viewing meals for chef {chef_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to view chef meals: {str(e)}"
        }

def place_chef_meal_order(user_id: str, chef_id: str, meal_id: str, quantity: int, 
                         delivery_date: str, special_instructions: str = None) -> Dict[str, Any]:
    """
    Place an order for a chef meal.
    
    Args:
        user_id: The ID of the user placing the order
        chef_id: The ID of the chef
        meal_id: The ID of the meal to order
        quantity: Number of servings to order
        delivery_date: Requested delivery date in YYYY-MM-DD format
        special_instructions: Optional special instructions for the order
        
    Returns:
        Dict containing the order details
    """
    try:
        # Get the user, chef, and meal
        user = get_object_or_404(CustomUser, id=user_id)
        chef = get_object_or_404(Chef, id=chef_id)
        meal = get_object_or_404(Meal, id=meal_id, chef=chef)
        
        # Parse the delivery date
        try:
            parsed_delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "message": "Invalid delivery date format. Please use YYYY-MM-DD."
            }
        
        # Check if the delivery date is valid
        if parsed_delivery_date <= timezone.now().date():
            return {
                "status": "error",
                "message": "Delivery date must be in the future."
            }
        
        # Validate quantity
        if quantity <= 0:
            return {
                "status": "error",
                "message": "Quantity must be greater than zero."
            }
        
        # Calculate the total price
        if meal.price is None:
            return {
                "status": "error",
                "message": f"Meal '{meal.name}' does not have a price set."
            }
        total_price = meal.price * Decimal(quantity)
        
        # Create the Order
        user_address = user.addresses.first()
        if not user_address:
            return {
                "status": "error",
                "message": "User does not have a saved address for the order."
            }
        
        order = Order.objects.create(
            customer=user,
            address=user_address,
            status='Placed',
            special_requests=special_instructions,
        )
        
        # Create the OrderMeal link
        order_meal = OrderMeal.objects.create(
            order=order,
            meal=meal,
            quantity=quantity,
            price_at_order=meal.price,
        )
        
        # Serialize the order using model_to_dict
        order_dict = model_to_dict(order, exclude=['customer', 'address', 'meal', 'meal_plan'])
        order_dict['id'] = str(order.id)
        order_dict['order_date'] = order.order_date.isoformat()
        order_dict['updated_at'] = order.updated_at.isoformat()
        order_dict['total_price'] = str(total_price)
        
        return {
            "status": "success",
            "message": "Order placed successfully",
            "order": order_dict,
            "payment_required": not order.is_paid
        }
        
    except Meal.DoesNotExist:
        return { "status": "error", "message": f"Meal with ID {meal_id} not found for chef {chef_id}."}
    except Exception as e:
        logger.error(f"Error placing order for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to place order: {str(e)}"
        }

def get_order_details(user_id: str, order_id: str) -> Dict[str, Any]:
    """
    Get details of a chef meal order.
    
    Args:
        user_id: The ID of the user who placed the order
        order_id: The ID of the order to retrieve
        
    Returns:
        Dict containing the order details
    """
    try:
        # Get the user and order
        user = get_object_or_404(CustomUser, id=user_id)
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Serialize the order using model_to_dict
        order_dict = model_to_dict(order, exclude=['customer', 'address', 'meal', 'meal_plan'])
        order_dict['id'] = str(order.id)
        order_dict['order_date'] = order.order_date.isoformat()
        order_dict['updated_at'] = order.updated_at.isoformat()
        
        # Add related meal details if needed
        order_meals_data = []
        for om in order.ordermeal_set.select_related('meal').all():
            meal_data = model_to_dict(om.meal, fields=['id', 'name', 'price']) if om.meal else None
            order_meals_data.append({
                'meal': meal_data,
                'quantity': om.quantity,
                'price_at_order': str(om.price_at_order) if om.price_at_order else None
            })
        order_dict['meals'] = order_meals_data
        order_dict['total_price'] = str(order.total_price())
        
        return {
            "status": "success",
            "order": order_dict
        }
        
    except Order.DoesNotExist:
        return { "status": "error", "message": f"Order with ID {order_id} not found for user {user_id}."}
    except Exception as e:
        logger.error(f"Error getting order details for user {user_id}, order {order_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to get order details: {str(e)}"
        }

def cancel_order(user_id: str, order_id: str, reason: str = None) -> Dict[str, Any]:
    """
    Cancel a chef meal order.
    
    Args:
        user_id: The ID of the user who placed the order
        order_id: The ID of the order to cancel
        reason: Reason for cancellation
        
    Returns:
        Dict containing the cancellation status
    """
    try:
        # Get the user and order
        user = get_object_or_404(CustomUser, id=user_id)
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Check if the order can be cancelled based on Order status choices
        allowed_cancel_statuses = ['Placed', 'In Progress']
        if order.status not in allowed_cancel_statuses:
            return {
                "status": "error",
                "message": f"Cannot cancel order with status '{order.status}'"
            }
        
        # Cancel the order
        order.status = "Cancelled"
        order.save()
        
        # Determine refund status based on payment status
        refund_status = "processing" if order.is_paid else "not_applicable"
        
        return {
            "status": "success",
            "message": "Order cancelled successfully",
            "refund_status": refund_status
        }
        
    except Order.DoesNotExist:
        return { "status": "error", "message": f"Order with ID {order_id} not found for user {user_id}."}
    except Exception as e:
        logger.error(f"Error cancelling order for user {user_id}, order {order_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to cancel order: {str(e)}"
        }

# Function to get all chef connection tools
def get_chef_connection_tools():
    """
    Get all chef connection tools for the OpenAI Responses API.
    
    Returns:
        List of chef connection tools in the format required by the OpenAI Responses API
    """
    return CHEF_CONNECTION_TOOLS
