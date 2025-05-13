"""
Module for finding and ranking relevant YouTube cooking videos for meals using the YouTube Data API
and OpenAI Responses API for intelligent filtering.
"""
import json
import logging
import traceback
from typing import Dict, List, Optional, Any

from django.conf import settings
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI
from django.conf import settings
import os
from meals.pydantic_models import VideoRankings

logger = logging.getLogger(__name__)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = settings.OPENAI_KEY

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def find_youtube_cooking_videos(meal_name: str, meal_description: str, limit: int = 5) -> Dict[str, Any]:
    """
    Use YouTube Data API to find relevant cooking videos and OpenAI to rank them.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        limit: Maximum number of videos to return in final results
        
    Returns:
        Dictionary containing YouTube video information, ranked by relevance
    """
    try:
        # In test mode, return a mock response
        if settings.TEST_MODE:
            return {'status': 'success', 'videos': ['https://youtu.be/dQw4w9WgXcQ']}
        
        # Step 1: Retrieve videos using the YouTube API
        youtube_results = _fetch_videos_from_youtube(meal_name, meal_description, limit * 2)
        
        if not youtube_results.get("videos"):
            logger.warning(f"No YouTube videos found for '{meal_name}'")
            return {"videos": [], "search_query": f"{meal_name} recipe"}
        
        # Step 2: Use OpenAI to analyze and rank the videos
        ranked_videos = _rank_videos_with_openai(meal_name, meal_description, youtube_results["videos"])
        
        # Step 3: Return the top videos based on ranking
        result = {
            "videos": ranked_videos[:limit],
            "search_query": youtube_results["search_query"]
        }
        
        logger.info(f"Successfully found and ranked {len(result['videos'])} YouTube videos for '{meal_name}'")
        return result
        
    except Exception as e:
        logger.error(f"Error finding YouTube videos for '{meal_name}': {e}")
        logger.error(traceback.format_exc())
        return {"videos": [], "search_query": f"{meal_name} recipe"}

def _fetch_videos_from_youtube(meal_name: str, meal_description: str, limit: int = 10) -> Dict[str, Any]:
    """
    Fetch videos from YouTube API.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        limit: Maximum number of videos to fetch
        
    Returns:
        Dictionary containing YouTube video information
    """
    try:
        # Create a search query based on the meal name
        search_query = f"{meal_name} recipe cooking tutorial"
        
        # Initialize the YouTube API client
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Call the search.list method to search for videos
        search_response = youtube.search().list(
            part="snippet",
            q=search_query,
            type="video",
            maxResults=limit,
            order="relevance",
            safeSearch="strict"
        ).execute()
        
        video_ids = [item["id"]["videoId"] for item in search_response.get("items", []) if item.get("id", {}).get("videoId")]
        video_durations = {}
        
        # Batch fetch video details (like duration)
        if video_ids:
            try:
                video_details_response = youtube.videos().list(
                    part="contentDetails",
                    id=",".join(video_ids) # Fetch details for multiple videos at once
                ).execute()
                
                for item in video_details_response.get("items", []):
                    video_durations[item["id"]] = item.get("contentDetails", {}).get("duration")
            except HttpError as e:
                logger.warning(f"Error getting batch video details: {e}")

        # Process the response to extract relevant information
        videos = []
        for search_result in search_response.get("items", []):
            video_id = search_result.get("id", {}).get("videoId")
            if not video_id:
                continue # Skip if videoId is missing
                
            video_info = {
                "video_id": video_id,
                "title": search_result["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": search_result["snippet"]["channelTitle"],
                "description": search_result["snippet"]["description"],
                "thumbnail": search_result["snippet"]["thumbnails"]["high"]["url"],
                "duration": video_durations.get(video_id) # Get duration from the batch result
            }
            
            videos.append(video_info)
        
        result = {
            "videos": videos,
            "search_query": search_query
        }
        
        return result
        
    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        logger.error(traceback.format_exc())
        return {"videos": [], "search_query": f"{meal_name} recipe"}

def _rank_videos_with_openai(meal_name: str, meal_description: str, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Use OpenAI Responses API to analyze and rank videos based on relevance to the meal.
    
    Args:
        meal_name: Name of the meal
        meal_description: Description of the meal
        videos: List of video information dictionaries
        
    Returns:
        List of video dictionaries, ranked by relevance and with additional relevance information
    """
    if not videos:
        return []
    
    try:
        # Prepare video information for OpenAI
        video_info_for_analysis = []
        for video in videos:
            video_info_for_analysis.append({
                "video_id": video["video_id"],
                "title": video["title"],
                "description": video["description"],
                "channel": video["channel"]
            })
        
        # Get the schema for the VideoRankings model
        schema = VideoRankings.model_json_schema()
        
        # Call OpenAI Responses API to analyze and rank videos
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=f"""
            Analyze these YouTube cooking videos and rank them based on relevance to this meal:
            
            Meal: {meal_name}
            Description: {meal_description}
            
            Videos:
            {json.dumps(video_info_for_analysis, indent=2)}
            
            Provide relevance scores (0-10) for each video, explain why, and indicate if it's recommended.
            Identify matching ingredients and cooking techniques when possible.
            """,
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'video_rankings',
                    'schema': schema
                }
            }
        )
        
        # Parse the structured output
        ranking_data = json.loads(response.output_text)
        
        # Merge ranking information with original video data
        ranked_video_ids = [v["video_id"] for v in ranking_data["ranked_videos"]]
        video_id_to_rank_info = {v["video_id"]: v for v in ranking_data["ranked_videos"]}
        
        # Create enhanced video objects with ranking information
        enhanced_videos = []
        
        # First add videos that were ranked, in order of their ranking
        for video_id in ranked_video_ids:
            for video in videos:
                if video["video_id"] == video_id:
                    rank_info = video_id_to_rank_info[video_id]
                    enhanced_video = video.copy()
                    enhanced_video.update({
                        "relevance_score": rank_info["relevance_score"],
                        "relevance_explanation": rank_info["relevance_explanation"],
                        "recommended": rank_info["recommended"],
                        "matching_ingredients": rank_info.get("matching_ingredients", []),
                        "matching_techniques": rank_info.get("matching_techniques", [])
                    })
                    enhanced_videos.append(enhanced_video)
                    break
        
        # Sort by relevance score (highest first)
        enhanced_videos.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return enhanced_videos
        
    except Exception as e:
        logger.error(f"Error ranking videos with OpenAI: {e}")
        logger.error(traceback.format_exc())
        # Return the original videos without ranking if OpenAI analysis fails
        return videos

def format_for_structured_output(youtube_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format YouTube API results to match the expected structured output format.
    
    Args:
        youtube_results: Results from the YouTube API search with OpenAI ranking
        
    Returns:
        Dictionary formatted for structured output
    """
    formatted_videos = []
    
    for video in youtube_results.get("videos", []):
        formatted_video = {
            "title": video["title"],
            "url": video["url"],
            "channel": video["channel"],
            "description": video.get("description", ""),
            "duration": video.get("duration", ""),
            "relevance_score": video.get("relevance_score", 0),
            "relevance_explanation": video.get("relevance_explanation", ""),
            "recommended": video.get("recommended", False),
            "matching_ingredients": video.get("matching_ingredients", []),
            "matching_techniques": video.get("matching_techniques", [])
        }
        formatted_videos.append(formatted_video)
    
    return {
        "videos": formatted_videos,
        "search_query": youtube_results.get("search_query", "")
    }
