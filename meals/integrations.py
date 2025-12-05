"""
Utility module for enhancing meals with nutritional information and relevant cooking videos.
This module provides functions to fetch macro information and find YouTube cooking videos for meals.
"""
import json
import logging
import traceback
from typing import List, Dict, Any
from shared.utils import get_groq_client
import os
import requests
logger = logging.getLogger(__name__)

def get_macro_info(meal_name: str, meal_description: str, ingredients: List[str]) -> Dict[str, Any]:
    """
    Get nutritional information for a meal using OpenAI.
    
    Args:
        meal_name: The name of the meal
        meal_description: The description of the meal
        ingredients: List of ingredients in the meal
        
    Returns:
        Dictionary containing macro information (calories, protein, carbs, fat, serving_size)
    """
    logger.info(f"Getting macro info for meal: {meal_name}")
    try:
        # Create a prompt for the OpenAI model
        prompt = f"""
        Based on the following meal information, estimate its nutritional content per serving:
        
        Meal Name: {meal_name}
        Description: {meal_description}
        Ingredients: {', '.join(ingredients) if ingredients else 'Not specified'}
        
        Please provide a JSON response with these fields:
        - calories (number, kcal per serving)
        - protein (number, grams per serving)
        - carbohydrates (number, grams per serving)
        - fat (number, grams per serving)
        - serving_size (string, description of one serving)
        
        Use reasonable estimates based on similar recipes. If information is insufficient, make educated guesses.
        """
        
        # Call OpenAI API
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a nutritionist who provides accurate macro information for meals."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response (robust to array- or string-wrapped JSON)
        result = json.loads(response.choices[0].message.content)
        if isinstance(result, list):
            candidate = next((item for item in result if isinstance(item, dict)), None)
            if candidate is None and result:
                first = result[0]
                if isinstance(first, str):
                    try:
                        inner = json.loads(first)
                        if isinstance(inner, dict):
                            candidate = inner
                    except Exception:
                        pass
            result = candidate or {}
        logger.info(f"Received macro info for meal '{meal_name}': {result}")
        
        # Validate the result
        required_fields = ['calories', 'protein', 'carbohydrates', 'fat', 'serving_size']
        for field in required_fields:
            if field not in result:
                logger.warning(f"Missing field '{field}' in macro information for meal '{meal_name}'")
                result[field] = "Unknown" if field == 'serving_size' else 0
        
        return result
    except Exception as e:
        logger.error(f"Error getting macro information for meal '{meal_name}': {e}")
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_macro_info", "traceback": traceback.format_exc()})
        return {
            'calories': 0,
            'protein': 0,
            'carbohydrates': 0,
            'fat': 0,
            'serving_size': 'Unknown'
        }

def find_youtube_videos(meal_name: str, meal_description: str) -> Dict[str, Any]:
    """
    Search for relevant YouTube cooking videos for a meal.
    
    Args:
        meal_name: The name of the meal
        meal_description: The description of the meal
        
    Returns:
        Dictionary containing video information (videos list with title, url, channel)
    """
    logger.info(f"Finding YouTube videos for meal: {meal_name}")
    try:
        # In a real implementation, you would use the YouTube API
        # For this example, we'll simulate results using OpenAI
        
        prompt = f"""
        Generate 3 hypothetical YouTube cooking videos for this meal:
        
        Meal Name: {meal_name}
        Description: {meal_description}
        
        Please provide a JSON response with:
        {{
            "videos": [
                {{
                    "title": "Video title",
                    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
                    "channel": "Channel name"
                }},
                ...
            ]
        }}
        
        Make the URLs and channels realistic but fictional.
        """
        
        # Call OpenAI API
        response = get_groq_client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that finds cooking videos."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the response (robust to array- or string-wrapped JSON)
        result = json.loads(response.choices[0].message.content)
        if isinstance(result, list):
            candidate = next((item for item in result if isinstance(item, dict)), None)
            if candidate is None and result:
                first = result[0]
                if isinstance(first, str):
                    try:
                        inner = json.loads(first)
                        if isinstance(inner, dict):
                            candidate = inner
                    except Exception:
                        pass
            result = candidate or {}
        logger.info(f"Received YouTube video info for meal '{meal_name}': {result}")
        
        # Ensure 'videos' key exists
        if 'videos' not in result:
            logger.warning(f"Missing 'videos' key in YouTube search result for meal '{meal_name}'")
            result['videos'] = []
        
        return result
    except Exception as e:
        logger.error(f"Error finding YouTube videos for meal '{meal_name}': {e}")
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"find_youtube_videos", "traceback": traceback.format_exc()})
        return {
            'videos': []
        }
