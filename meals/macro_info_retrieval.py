"""
Module for retrieving macro nutritional information for meals using OpenAI Responses API.
"""
import json
import logging
import traceback
from typing import Dict, List, Optional, Any, ClassVar
from django.conf import settings
try:
    from groq import Groq  # Groq client for inference
except Exception:
    Groq = None
import os
from pydantic import ValidationError
from shared.utils import get_groq_client
from meals.pydantic_models import MealMacroInfo

logger = logging.getLogger(__name__)

def _get_groq_client():
    try:
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key and Groq is not None:
            return Groq(api_key=api_key)
    except Exception:
        pass
    return None

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
        # Prefer Groq structured output if available
        groq_client = _get_groq_client()
        user_text = f"""
            Analyze the following meal and provide detailed macro nutritional information:
            
            Meal: {meal_name}
            Description: {meal_description}
            {ingredients_text}
            
            Provide accurate nutritional estimates based on standard serving sizes.
        """
        groq_resp = groq_client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
            messages=[
                {"role": "system", "content": "Return only JSON matching the provided schema."},
                {"role": "user", "content": user_text},
            ],
            temperature=0.2,
            top_p=1,
            stream=False,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "meal_macros",
                    "schema": MealMacroInfo.model_json_schema(),
                },
            },
        )
        macro_data = json.loads(groq_resp.choices[0].message.content or "{}")
        # Handle null from LLM
        if macro_data is None:
            logger.warning(f"LLM returned null for macro info for '{meal_name}'")
            return None
        
        # Validate the data against our schema
        validated_data = MealMacroInfo.model_validate(macro_data)
        
        logger.info(f"Successfully generated macro information for '{meal_name}'")
        return validated_data.model_dump()
        
    except (OpenAIError, json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Error generating macro information for '{meal_name}': {e}")
        logger.error(traceback.format_exc())
        return None
