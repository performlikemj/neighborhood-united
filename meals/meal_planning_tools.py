"""
Meal planning tools for the OpenAI Responses API integration.

This module implements the meal planning tools defined in the optimized tool structure,
connecting them to the existing meal planning functionality in the application.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from django.utils import timezone
from django.shortcuts import get_object_or_404

from custom_auth.models import CustomUser
from meals.models import MealPlan, MealPlanMeal, Meal
from meals.meal_plan_service import create_meal_plan_for_user as service_create_meal_plan_for_user
from meals.meal_generation import generate_and_create_meal
from meals.meal_instructions import generate_instructions
from meals.serializers import MealPlanSerializer, MealPlanMealSerializer

logger = logging.getLogger(__name__)

# Tool definitions for the OpenAI Responses API
MEAL_PLANNING_TOOLS = [
    {
        "type": "function",
        "name": "create_meal_plan",
        "description": "Create a new meal plan for a user based on their preferences",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user to create the meal plan for"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to plan for (default is 7)"
                },
                "meal_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["Breakfast", "Lunch", "Dinner"]
                    },
                    "description": "Types of meals to include in the plan"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date for the meal plan in YYYY-MM-DD format"
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Optional user prompt to guide meal generation"
                }
            },
            "required": ["user_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "modify_meal_plan",
        "description": "Modify an existing meal plan by replacing specific meals",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The ID of the user who owns the meal plan"
                },
                "meal_plan_id": {
                    "type": "string",
                    "description": "The ID of the meal plan to modify"
                },
                "day": {
                    "type": "string",
                    "description": "The day to modify (e.g., 'Monday', 'Tuesday')"
                },
                "meal_type": {
                    "type": "string",
                    "enum": ["Breakfast", "Lunch", "Dinner"],
                    "description": "The type of meal to replace"
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Optional user prompt to guide meal generation for the replacement"
                }
            },
            "required": ["user_id", "meal_plan_id", "day", "meal_type"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "get_meal_plan",
        "description": "Get details of an existing meal plan",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user who owns the meal plan"
                    },
                    "meal_plan_id": {
                        "type": "string",
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
                        "type": "string",
                        "description": "The ID of the meal"
                    }
                },
                "required": ["meal_id"],
                "additionalProperties": False
            }
    },
    {
        "type": "function",
        "name": "generate_meal_instructions",
        "description": "Generate cooking instructions for meals in a meal plan",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user who owns the meal plan"
                    },
                    "meal_plan_id": {
                        "type": "string",
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
    }
]

# Tool implementation functions

def create_meal_plan(user_id: str, days: int = 7, meal_types: List[str] = None, 
                    start_date: str = None, user_prompt: str = None) -> Dict[str, Any]:
    """
    Create a new meal plan for a user based on their preferences.
    
    Args:
        user_id: The ID of the user to create the meal plan for
        days: Number of days to plan for (default is 7)
        meal_types: Types of meals to include in the plan (default is ["Breakfast", "Lunch", "Dinner"])
        start_date: Start date for the meal plan in YYYY-MM-DD format (default is today)
        user_prompt: Optional user prompt to guide meal generation
        
    Returns:
        Dict containing the created meal plan details
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Set default meal types if not provided
        if not meal_types:
            meal_types = ["Breakfast", "Lunch", "Dinner"]
            
        # Set default start date if not provided
        if not start_date:
            start_date = timezone.now().date()
        else:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            
        # Calculate end date
        end_date = start_date + timedelta(days=days-1)
        
        # Create the meal plan using the service function
        meal_plan = service_create_meal_plan_for_user(
            user=user,
            start_of_week=start_date,
            end_of_week=end_date,
        )
        
        # Serialize the meal plan for the response
        serializer = MealPlanSerializer(meal_plan)
        
        return {
            "status": "success",
            "message": f"Meal plan created successfully for {days} days starting {start_date}",
            "meal_plan": serializer.data
        }
        
    except Exception as e:
        logger.error(f"Error creating meal plan for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create meal plan: {str(e)}"
        }

def modify_meal_plan(user_id: str, meal_plan_id: str, day: str, meal_type: str, 
                    user_prompt: str = None) -> Dict[str, Any]:
    """
    Modify an existing meal plan by replacing specific meals.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan to modify
        day: The day to modify (e.g., 'Monday', 'Tuesday')
        meal_type: The type of meal to replace
        user_prompt: Optional user prompt to guide meal generation for the replacement
        
    Returns:
        Dict containing the modified meal plan details
    """
    try:
        # Get the user and meal plan
        user = get_object_or_404(CustomUser, id=user_id)
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        
        # Find the meal plan meal to replace
        meal_plan_meal = MealPlanMeal.objects.filter(
            meal_plan=meal_plan,
            day=day,
            meal_type=meal_type
        ).first()
        
        if not meal_plan_meal:
            return {
                "status": "error",
                "message": f"No {meal_type} found for {day} in the meal plan"
            }
            
        # Get existing meal names and embeddings for context
        existing_meal_names = set()
        existing_meal_embeddings = []
        
        for mpm in MealPlanMeal.objects.filter(meal_plan=meal_plan):
            if mpm.meal:
                existing_meal_names.add(mpm.meal.name)
                if mpm.meal.meal_embedding:
                    existing_meal_embeddings.append(mpm.meal.meal_embedding)
        
        # Generate a new meal
        result = generate_and_create_meal(
            user=user,
            meal_plan=meal_plan,
            meal_type=meal_type,
            existing_meal_names=existing_meal_names,
            existing_meal_embeddings=existing_meal_embeddings,
            user_id=user_id,
            day_name=day,
            user_prompt=user_prompt
        )
        
        if result.get('status') != 'success':
            return {
                "status": "error",
                "message": result.get('message', 'Failed to generate replacement meal')
            }
            
        # Get the updated meal plan meal
        updated_meal_plan_meal = MealPlanMeal.objects.filter(
            meal_plan=meal_plan,
            day=day,
            meal_type=meal_type
        ).first()
        
        # Serialize the updated meal plan meal
        serializer = MealPlanMealSerializer(updated_meal_plan_meal)
        
        return {
            "status": "success",
            "message": f"Successfully replaced {meal_type} for {day}",
            "meal_plan_meal": serializer.data
        }
        
    except Exception as e:
        logger.error(f"Error modifying meal plan {meal_plan_id} for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to modify meal plan: {str(e)}"
        }

def get_meal_details(meal_id: str) -> Dict[str, Any]:
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
        return {
            "status": "error",
            "message": f"Failed to get meal details: {str(e)}"
        }

def get_meal_plan(user_id: str, meal_plan_id: str = None) -> Dict[str, Any]:
    """
    Get details of an existing meal plan.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan to retrieve (optional, defaults to most recent)
        
    Returns:
        Dict containing the meal plan details
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the meal plan
        if meal_plan_id:
            meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=user)
        else:
            # Get the most recent meal plan
            meal_plan = MealPlan.objects.filter(user=user).order_by('-created_at').first()
            
            if not meal_plan:
                return {
                    "status": "error",
                    "message": "No meal plans found for this user"
                }
        
        # Serialize the meal plan
        serializer = MealPlanSerializer(meal_plan)
        
        return {
            "status": "success",
            "meal_plan": serializer.data
        }
        
    except Exception as e:
        logger.error(f"Error retrieving meal plan for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to retrieve meal plan: {str(e)}"
        }

def generate_meal_instructions(user_id: str, meal_plan_id: str, day: str = None, 
                              meal_type: str = None) -> Dict[str, Any]:
    """
    Generate cooking instructions for meals in a meal plan.
    
    Args:
        user_id: The ID of the user who owns the meal plan
        meal_plan_id: The ID of the meal plan
        day: Optional specific day to generate instructions for
        meal_type: Optional specific meal type to generate instructions for
        
    Returns:
        Dict containing the generated instructions
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
        return {
            "status": "error",
            "message": f"Failed to generate instructions: {str(e)}"
        }

# Function to get all meal planning tools
def get_meal_planning_tools():
    """
    Get all meal planning tools for the OpenAI Responses API.
    
    Returns:
        List of meal planning tools in the format required by the OpenAI Responses API
    """
    return MEAL_PLANNING_TOOLS
