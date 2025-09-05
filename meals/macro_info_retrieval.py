"""
Module for retrieving macro nutritional information for meals using OpenAI Responses API.
"""
import json
import logging
import traceback
from typing import Dict, List, Optional, Any, ClassVar
from django.conf import settings
from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from shared.utils import get_openai_client
from meals.pydantic_models import MealMacroInfo

logger = logging.getLogger(__name__)

def get_meal_macro_information(meal_name: str, meal_description: str, ingredients: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Use OpenAI Responses API to generate macro nutritional information for a meal.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        ingredients: Optional list of ingredients
        
    Returns:
        Dictionary containing macro nutritional information or None if an error occurs
    """
    ingredients_text = ""
    if ingredients:
        ingredients_text = "Ingredients:\n" + "\n".join([f"- {ingredient}" for ingredient in ingredients])
    
    try:
        response = get_openai_client().responses.create(
            model="gpt-5-mini",
            input=f"""
            Analyze the following meal and provide detailed macro nutritional information:
            
            Meal: {meal_name}
            Description: {meal_description}
            {ingredients_text}
            
            Provide accurate nutritional estimates based on standard serving sizes.
            """,
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'meal_macros',
                    'schema': MealMacroInfo.model_json_schema()
                }
            }
        )
        
        # Parse the structured output
        macro_data = json.loads(response.output_text)
        print(f"Macro data: {macro_data}")
        # Validate the data against our schema
        validated_data = MealMacroInfo.model_validate(macro_data)
        
        logger.info(f"Successfully generated macro information for '{meal_name}'")
        return validated_data.model_dump()
        
    except (OpenAIError, json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Error generating macro information for '{meal_name}': {e}")
        logger.error(traceback.format_exc())
        return None
