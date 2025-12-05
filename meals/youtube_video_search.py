"""
Module for finding relevant YouTube cooking videos for meals.
Note: Web search functionality requires OpenAI API. This module generates search queries
which can be used with the YouTube Data API (see youtube_api_search.py).
"""
import json
import logging
import os
import traceback
from typing import Dict, List, Optional, Any

from django.conf import settings
try:
    from groq import Groq
except ImportError:
    Groq = None
from pydantic import ValidationError

from meals.pydantic_models import YouTubeVideoResults

logger = logging.getLogger(__name__)
GROQ_API_KEY = getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and Groq else None

def find_youtube_cooking_videos(meal_name: str, meal_description: str, limit: int = 3) -> Dict[str, Any]:
    """
    Generate a search query for YouTube cooking videos.
    Note: This uses Groq for query generation. For actual video search,
    use youtube_api_search.py which uses the YouTube Data API.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        limit: Maximum number of videos to return
        
    Returns:
        Dictionary containing search query and empty videos list
        (Use youtube_api_search.py for actual video results)
    """
    try:
        if not client:
            logger.warning("Groq client not available for YouTube search query generation")
            return {"videos": [], "search_query": f"{meal_name} recipe cooking tutorial"}
        
        # Generate an optimal search query using Groq
        query_response = client.chat.completions.create(
            model=getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile'),
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    Create the best YouTube search query to find a cooking tutorial for this meal:
                    
                    Meal: {meal_name}
                    Description: {meal_description}
                    
                    Return only the search query text, nothing else.
                    """
                }
            ],
            max_tokens=100
        )
        
        search_query = query_response.choices[0].message.content.strip()
        logger.info(f"Generated search query for '{meal_name}': {search_query}")
        
        # Note: Web search requires OpenAI API. Return search query for use with YouTube API
        # For actual video search, use youtube_api_search.find_youtube_cooking_videos()
        video_data = {"videos": []}
        
        # Handle null from LLM
        if video_data is None:
            logger.warning(f"LLM returned null for YouTube videos for '{meal_name}'")
            return {"videos": [], "search_query": f"{meal_name} recipe"}
        
        # Validate the data against our schema
        validated_data = YouTubeVideoResults.model_validate(video_data)
        
        # Add the search query to the result
        result = validated_data.model_dump()
        result["search_query"] = search_query
        
        logger.info(f"Successfully found {len(result['videos'])} YouTube videos for '{meal_name}'")
        return result
        
    except (OpenAIError, json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Error finding YouTube videos for '{meal_name}': {e}")
        logger.error(traceback.format_exc())
        # Return a minimal valid structure in case of error
        return {"videos": [], "search_query": f"{meal_name} recipe"}
