"""
Module for finding relevant YouTube cooking videos for meals using OpenAI Responses API.
"""
import json
import logging
import traceback
from typing import Dict, List, Optional, Any

from django.conf import settings
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from meals.pydantic_models import YouTubeVideoResults

logger = logging.getLogger(__name__)
OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)

def find_youtube_cooking_videos(meal_name: str, meal_description: str, limit: int = 3) -> Dict[str, Any]:
    """
    Use OpenAI Responses API with web search tool to find relevant YouTube cooking videos.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        limit: Maximum number of videos to return
        
    Returns:
        Dictionary containing YouTube video information
    """
    try:
        # First, generate an optimal search query using OpenAI
        query_response = client.responses.create(
            model="gpt-5-mini",
            input=f"""
            Create the best YouTube search query to find a cooking tutorial for this meal:
            
            Meal: {meal_name}
            Description: {meal_description}
            
            Return only the search query text, nothing else.
            """,
            max_output_tokens=100
        )
        
        search_query = query_response.output_text.strip()
        logger.info(f"Generated search query for '{meal_name}': {search_query}")
        
        # Now use the web search tool to find YouTube videos
        video_response = client.responses.create(
            model="gpt-5-mini",
            tools=[{"type": "web_search_preview"}],
            input=f"Find {limit} YouTube cooking videos for: {search_query} site:youtube.com",
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'youtube_videos',
                    'schema': YouTubeVideoResults.model_json_schema()
                }
            }
        )
        
        # Parse the structured output
        video_data = json.loads(video_response.output_text)
        
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
