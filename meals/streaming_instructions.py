"""
Instructions generator for meal plans.

This module provides support for generating meal instructions
(both daily and bulk prep) while maintaining security and ownership checks.
The instructions are generated directly without sending emails or creating
additional metadata like macros or YouTube information.
"""

from typing import Dict, List, Any, Optional
import json
import logging
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.conf import settings
from openai import OpenAI
from openai import BadRequestError
from pydantic import BaseModel, Field
from meals.models import MealPlan, MealPlanMeal, Meal
from meals.pydantic_models import Instructions as InstructionsSchema
from meals.pydantic_models import BulkPrepInstructions
from shared.utils import generate_user_context

logger = logging.getLogger(__name__)

# Set up OpenAI client
client = OpenAI(api_key=settings.OPENAI_KEY)


def generate_streaming_instructions(
    user_id: int, 
    meal_plan_id: int, 
    mode: str = "daily", 
    meal_plan_meal_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Generate instructions for meals in a unified way.
    Unlike the email-sending functions, this only generates the instructions
    without sending emails or creating additional metadata.
    
    Args:
        user_id: The ID of the authenticated user
        meal_plan_id: The ID of the meal plan
        mode: Either "daily" (per-meal instructions) or "bulk" (prep instructions for the whole plan)
        meal_plan_meal_ids: Optional list of IDs for which to generate instructions in daily mode.
            Accepts either MealPlanMeal IDs (preferred) or Meal IDs. If Meal IDs are provided,
            they will be mapped to the corresponding MealPlanMeal entries in the specified
            meal plan owned by the user.
        
    Returns:
        A dictionary containing the complete instructions
        
    Raises:
        PermissionDenied: If the meal plan doesn't belong to the specified user
    """
    # Security check: verify ownership by filtering on both ID and user_id
    if not MealPlan.objects.filter(id=meal_plan_id, user_id=user_id).exists():
        raise PermissionDenied("You don't have permission to access this meal plan")
    
    # Get the meal plan
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user_id=user_id)
    
    # Branch based on mode
    if mode.lower() == "bulk":
        # Generate bulk prep instructions for the whole plan
        instructions = _generate_bulk_prep_instructions(meal_plan)
        return {
            "type": "text", 
            "content": instructions,
            "instruction_type": "bulk",
            "status": "success"
        }
            
    else:  # Default to "daily" mode
        # If specific meal plan meal IDs are provided, resolve and use them
        if meal_plan_meal_ids:
            base_qs = MealPlanMeal.objects.filter(
                meal_plan_id=meal_plan_id,
                meal_plan__user_id=user_id
            )

            # Normalize and de-duplicate incoming IDs
            try:
                requested_ids = list({int(i) for i in meal_plan_meal_ids})
            except Exception:
                # Fall back without casting if inputs are already ints or non-castable
                requested_ids = list({i for i in meal_plan_meal_ids})

            # First, match as MealPlanMeal IDs
            direct_mpm_ids = list(
                base_qs.filter(id__in=requested_ids).values_list('id', flat=True)
            )

            # Remaining IDs which did not match as MealPlanMeal IDs are treated as Meal IDs
            remaining_ids = [i for i in requested_ids if i not in set(direct_mpm_ids)]

            mpm_ids_from_meal = []
            if remaining_ids:
                # Map Meal IDs -> MealPlanMeal IDs within this user's plan
                mpm_ids_from_meal = list(
                    base_qs.filter(meal_id__in=remaining_ids).values_list('id', flat=True)
                )

                # Determine which Meal IDs were actually present in the plan
                meals_found = set(
                    base_qs.filter(meal_id__in=remaining_ids).values_list('meal_id', flat=True)
                )
                invalid_ids = [i for i in remaining_ids if i not in meals_found]
            else:
                invalid_ids = []

            if invalid_ids:
                raise PermissionDenied(
                    f"You don't have permission to access meal(s) {', '.join(str(i) for i in invalid_ids)}"
                )

            resolved_mpm_ids = list({*direct_mpm_ids, *mpm_ids_from_meal})

            # Get the specified meal plan meals after resolution
            meal_plan_meals = base_qs.filter(id__in=resolved_mpm_ids)
            instructions = _generate_daily_instructions(meal_plan_meals)
            return {
                "type": "text",
                "content": instructions,
                "instruction_type": "daily",
                "status": "success"
            }
        else:
            # Generate instructions for all meals in the plan
            meal_plan_meals = MealPlanMeal.objects.filter(meal_plan_id=meal_plan_id)
            instructions = _generate_daily_instructions(meal_plan_meals)
            return {
                "type": "text", 
                "content": instructions,
                "instruction_type": "daily",
                "status": "success"
            }


def _generate_daily_instructions(meal_plan_meals) -> str:
    """
    Generate cooking instructions for individual meals using OpenAI.
    This is a simplified version that doesn't send emails or create additional metadata.
    
    Args:
        meal_plan_meals: QuerySet of MealPlanMeal objects
        
    Returns:
        String with formatted cooking instructions
    """
    # Get the first meal plan meal to access user information
    if not meal_plan_meals.exists():
        return "No meals found to generate instructions."
    
    first_meal = meal_plan_meals.first()
    user = first_meal.meal_plan.user
    user_preferred_language = user.preferred_language or 'English'
    
    # Get user context to personalize instructions
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = "No additional user context available."
    
    # Serialize meal data for the prompt
    meals_data = []
    for mpm in meal_plan_meals:
        meal = mpm.meal
        meal_data = {
            "id": str(mpm.id),
            "day": mpm.day,
            "meal_type": mpm.meal_type,
            "name": meal.name,
            "description": meal.description or "",
            "ingredients": []
        }
        
        # Add ingredients if available
        if hasattr(meal, 'ingredients') and meal.ingredients.exists():
            for ingredient in meal.ingredients.all():
                ing_data = {
                    "name": getattr(ingredient, 'name', ''),
                    "quantity": getattr(ingredient, 'quantity', ''),
                    "unit": getattr(ingredient, 'unit', '')
                }
                meal_data["ingredients"].append(ing_data)
        
        meals_data.append(meal_data)
    
    # Convert to JSON for the API call
    meals_json = json.dumps(meals_data)
    
    try:
        # Call OpenAI to generate instructions
        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {
                    "role": "developer",
                    "content": (
                        
                        f"Generate clear, step-by-step cooking instructions based on provided meal data and user context in the specified language of {user_preferred_language}. "
                        """
                        Use the following schema to structure the instructions.

                        # Steps

                        1. Analyze the meal data and user context to understand the recipe and any user-specific considerations.
                        2. Break down the recipe into clear, manageable steps to guide the user through the cooking process.
                        3. Assign a sequential step number to each instruction to maintain a logical order.
                        4. Provide a brief description for each step, ensuring it is easy to understand and implement.
                        5. Estimate the duration of each step and include it, or default to 'N/A' if it can't be determined.

                        # Output Format

                        ```JSON
                        {
                            "steps": [
                                {
                                    "step_number": int,
                                    "description": "string",
                                    "duration": "string or 'N/A'"
                                },
                                ...
                            ]
                        }
                        ```

                        # Examples

                        **Example 1:**
                        - *Input:* Data for making pasta and user prefers instructions in Spanish.
                        - *Output:*
                        ```JSON
                        {
                            "steps": [
                                {
                                    "step_number": 1,
                                    "description": "Hierva agua en una olla grande.",
                                    "duration": "10 minutos"
                                },
                                {
                                    "step_number": 2,
                                    "description": "Añada la pasta y cocine según las instrucciones del paquete.",
                                    "duration": "10-12 minutos"
                                },
                                ...
                            ]
                        }
                        ```

                        **Example 2:**
                        - *Input:* Data for making pancakes and user prefers instructions in English.
                        - *Output:*
                        ```JSON
                        {
                            "steps": [
                                {
                                    "step_number": 1,
                                    "description": "Mix flour, sugar, and baking powder in a bowl.",
                                    "duration": "5 minutes"
                                },
                                {
                                    "step_number": 2,
                                    "description": "Pour milk and melted butter into the mixture.",
                                    "duration": "2 minutes"
                                },
                                ...
                            ]
                        }
                        ```

                        # Notes

                        - Duration is important to manage user's time expectations. Provide your best estimate or use 'N/A' if it can't be determined.
                        - Ensure instructions are concise to maintain user engagement.
                        - Translate the instructions accurately into the user's preferred language.
                        """
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate cooking instructions in {user_preferred_language} for these meals: {meals_json}. "
                        f"User context: {user_context}. "
                        f"Provide clear, step-by-step instructions with timing information for each meal. "
                        f"Focus only on practical cooking steps. Format the output as clean markdown with headings "
                        f"for each meal organized by day and meal type. Do not include any other information beyond "
                        f"the cooking instructions. Keep it concise and to the point."
                    )
                }
            ],
            text={
                "format": {
                'type': 'json_schema',
                'name': 'get_instructions',
                'schema': InstructionsSchema.model_json_schema()
                }
            }
        )
        
        instructions = response.output_text
        return instructions
        
    except BadRequestError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return f"Error generating instructions: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return f"An unexpected error occurred while generating instructions: {str(e)}"


def _generate_bulk_prep_instructions(meal_plan) -> str:
    """
    Generate bulk preparation instructions for multiple meals in a plan using OpenAI.
    This is a simplified version that doesn't send emails or create additional metadata.
    
    Args:
        meal_plan: A MealPlan object
        
    Returns:
        String with formatted bulk preparation instructions
    """
    # Get all meals in the plan
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan)
    
    if not meal_plan_meals.exists():
        return "No meals found in the meal plan."
    
    user = meal_plan.user
    user_preferred_language = user.preferred_language or 'English'
    
    # Get user context to personalize instructions
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = "No additional user context available."
    
    # Serialize meal data for the prompt
    meals_data = []
    for mpm in meal_plan_meals:
        meal = mpm.meal
        meal_data = {
            "id": str(mpm.id),
            "day": mpm.day,
            "meal_type": mpm.meal_type,
            "name": meal.name,
            "description": meal.description or "",
            "ingredients": []
        }
        
        # Add ingredients if available
        if hasattr(meal, 'ingredients') and meal.ingredients.exists():
            for ingredient in meal.ingredients.all():
                ing_data = {
                    "name": getattr(ingredient, 'name', ''),
                    "quantity": getattr(ingredient, 'quantity', ''),
                    "unit": getattr(ingredient, 'unit', '')
                }
                meal_data["ingredients"].append(ing_data)
        
        meals_data.append(meal_data)
    
    # Convert to JSON for the API call
    meals_json = json.dumps(meals_data)
    
    try:
        # Call OpenAI to generate instructions
        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {
                    "role": "developer",
                    "content": (
                        f"You are a helpful assistant that generates bulk meal preparation instructions in {user_preferred_language} based on the provided meal data and user context. Create practical, efficient instructions for preparing multiple meals at once."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate bulk meal preparation instructions in {user_preferred_language} for these meals: {meals_json}. "
                        f"User context: {user_context}. "
                        f"The goal is to efficiently prepare components for all meals in one session. Include: "
                        f"Step-by-step bulk prep instructions that minimize time and effort, but maximize quality. "
                        f"Storage instructions for prepared items "
                        f"Brief daily instructions for final assembly/heating "
                        f"Format the output as clean markdown with clear sections. Focus on practical efficiency and keep it concise."
                    )
                }
            ],
            text={
                "format": {
                'type': 'json_schema',
                'name': 'get_instructions',
                'schema': InstructionsSchema.model_json_schema()
                }
            }
        )
        
        instructions = response.output_text
        return instructions
        
    except BadRequestError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return f"Error generating bulk prep instructions: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return f"An unexpected error occurred while generating bulk prep instructions: {str(e)}" 