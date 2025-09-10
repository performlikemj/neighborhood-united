"""
Focus: High-level orchestration of meal plan creation, scheduling, and integrating other modules.
"""
import json
import logging
import os
import random
import requests
import pytz
from zoneinfo import ZoneInfo
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from types import SimpleNamespace
from random import shuffle
from typing import List, Set, Optional, Tuple, Dict
from celery import shared_task
from meals.celery_utils import handle_task_failure
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from openai import OpenAI, OpenAIError
try:
    from groq import Groq  # optional Groq client for inference
except Exception:
    Groq = None
from custom_auth.models import CustomUser
from meals.meal_generation import generate_and_create_meal, perform_openai_sanity_check
from meals.models import Meal, MealPlan, MealPlanMeal, MealPlanInstruction, ChefMealEvent, Dish, Ingredient
from meals.tasks import MAX_ATTEMPTS
from meals.pydantic_models import (MealsToReplaceSchema, BulkPrepInstructions,
                                  MealPlanModificationRequest, PromptMealMap, ModifiedMealSchema)
from meals.meal_modification_parser import parse_modification_request
from shared.utils import (generate_user_context, get_embedding, cosine_similarity, replace_meal_in_plan,
                          remove_meal_from_plan, get_openai_client)
from django.db import transaction
from pydantic import BaseModel, Field, ConfigDict
from utils.groq_rate_limit import groq_call_with_retry

logger = logging.getLogger(__name__)

# Lazy Groq client factory
def _get_groq_client():
    try:
        api_key = getattr(settings, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
        if api_key and Groq is not None:
            return Groq(api_key=api_key)
    except Exception:
        pass
    return None

class DietaryCompatibilityResponse(BaseModel):
    """Schema for OpenAI's response on dietary compatibility"""
    model_config = ConfigDict(extra="forbid")

    is_compatible: bool = Field(..., description="Whether the meal is compatible with the dietary preference")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Brief explanation for the compatibility assessment")

def is_saturday_in_timezone(user_timezone_str):
    """
    Check if it's Saturday in the user's timezone
    
    Args:
        user_timezone_str: String representing the user's timezone (e.g., 'America/New_York')
        
    Returns:
        Boolean indicating if it's Saturday in the user's timezone
    """
    try:
        # Get the timezone object
        user_tz = ZoneInfo(user_timezone_str)
        
        # Get current time in user's timezone
        user_local_time = timezone.now().astimezone(user_tz)
        
        # Check if it's Saturday (weekday 5)
        return user_local_time.weekday() == 5
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"is_saturday_in_timezone", "traceback": traceback.format_exc()})
        # Default to server's timezone if there's an error
        return timezone.now().weekday() == 5

# TODO: Add parameter to include ingredients from the gpt generated check
def analyze_meal_compatibility(meal, dietary_preference):
    """
    Use OpenAI to analyze if a meal is compatible with a dietary preference
    
    Args:
        meal: The Meal object to analyze
        dietary_preference: Name of the dietary preference
        
    Returns:
        Dict containing compatibility assessment with keys:
        - is_compatible (bool)
        - confidence (float)
        - reasoning (str)
    """
    try:
        # Get all ingredients and relevant meal details
        ingredients = []
        for dish in meal.dishes.all():
            ingredients.extend([ingredient.name for ingredient in dish.ingredients.all()])
        
        # Prepare the prompt
        input = [
            {"role": "developer", 
             "content": (
                    """
                    Analyze a list of meal ingredients and preparation methods to determine their compatibility with specific dietary preferences. Consider both explicit ingredients and common preparation methods.

                    Use the following criteria for your analysis:
                    - Evaluate each ingredient and preparation method in the context of the given dietary preference.
                    - Consider common allergens or restricted ingredients associated with the preference.
                    - Assess how preparation methods might alter ingredient compatibility.
                    - Provide a confidence score to reflect the certainty of your assessment.
                    - Explain your reasoning with a brief yet clear description for your compatibility assessment.

                    # Steps

                    1. **Identify Ingredients**: List out all explicit ingredients from the meal.
                    2. **Evaluate Preparation Methods**: Identify and consider any typical preparation methods that might affect dietary compatibility.
                    3. **Compatibility Assessment**: Determine if the meal aligns with the specified dietary preference.
                    4. **Confidence Scoring**: Assign a confidence score between 0.0 and 1.0 based on the certainty of the compatibility analysis.
                    5. **Reasoning**: Provide a brief explanation detailing why the meal is deemed compatible or incompatible.

                    # Output Format

                    Return a JSON object using the following schema:

                    ```json
                    {
                    "is_compatible": boolean,  // Indicates if the meal aligns with the dietary preference
                    "confidence": float,       // A score between 0.0 and 1.0 reflecting the analysis confidence
                    "reasoning": "string"      // A brief explanation for the assessment
                    }
                    ```

                    # Examples

                    **Input**: 
                    - Meal: "Caesar Salad with Croutons"
                    - Dietary Preference: "Gluten-Free"

                    **Output**:
                    ```json
                    {
                    "is_compatible": false,
                    "confidence": 0.9,
                    "reasoning": "The salad contains croutons, which are typically made from wheat bread, incompatible with a gluten-free diet."
                    }
                    ```

                    **Input**: 
                    - Meal: "Grilled Chicken with Steamed Vegetables"
                    - Dietary Preference: "Paleo"

                    **Output**:
                    ```json
                    {
                    "is_compatible": true,
                    "confidence": 0.95,
                    "reasoning": "Grilled chicken and steamed vegetables are generally considered paleo-friendly, as they consist of whole, unprocessed foods."
                    }
                    ```

                    # Notes

                    - Be aware of cross-contamination possibilities which might affect compatibility.
                    - Consider any additional nuances in preparation methods that might introduce non-compliant elements (e.g., sauces, dressings, or marination).
                    """
                )
            },
            {"role": "user", 
             "content": (
                    f"Meal Name: {meal.name}\n"
                    f"Description: {meal.description}\n"
                    f"Ingredients: {', '.join(ingredients)}\n\n"
                    f"Is this meal compatible with a {dietary_preference} diet? "
                    f"Even if it's not explicitly labeled as {dietary_preference}, "
                    f"determine if its ingredients and preparation would satisfy that dietary requirement."
                )
            }
        ]

        # Make API call (prefer Groq structured JSON)
        groq_client = _get_groq_client()
        if groq_client:
            groq_messages = [
                {"role": ("system" if m.get("role") == "developer" else m.get("role")), "content": m.get("content")}
                for m in input
            ]
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.analyze_meal_compatibility',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=groq_messages,
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "dietary_compatibility",
                        "schema": DietaryCompatibilityResponse.model_json_schema(),
                    },
                },
            )
            raw_json = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=input,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "dietary_compatibility",
                        "schema": DietaryCompatibilityResponse.model_json_schema(),
                        "strict": True
                    }
                }
            )
            raw_json = response.output_text

        # Parse response
        result = json.loads(raw_json)
        return {
            "is_compatible": result.get("is_compatible", False),
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", "No explanation provided")
        }
        
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"analyze_meal_compatibility", "traceback": traceback.format_exc()})
        return {
            "is_compatible": False, 
            "confidence": 0.0,
            "reasoning": f"Error during analysis: {str(e)}"
        }

def get_compatible_meals_for_user(user, meal_pool=None):
    """
    Find meals compatible with user's dietary preferences using AI analysis
    """
    # Get both regular and custom dietary preferences
    regular_preferences = user.profile.dietary_preferences.all()
    custom_preferences = user.profile.custom_dietary_preferences.all()
    
    # Skip analysis if user has no preferences at all
    if not regular_preferences.exists() and not custom_preferences.exists():
        # If no preferences at all, all meals are compatible
        return meal_pool or Meal.objects.filter(is_active=True)
    
    # Check if user has "Everything" in their regular preferences
    has_everything_pref = regular_preferences.filter(name="Everything").exists()
    
    # Determine if "Everything" is the ONLY preference (both regular and custom)
    has_only_everything_pref = (
        has_everything_pref and 
        regular_preferences.count() == 1 and 
        not custom_preferences.exists()
    )
    
    # Only if "Everything" is the ONLY preference (regular or custom), all meals are compatible
    if has_only_everything_pref:
        # For users with ONLY the "Everything" preference and no custom preferences,
        # all meals are compatible
        meals = meal_pool or Meal.objects.filter(is_active=True)
        for meal in meals:
            meal.compatibility_analyses.reasoning = ["Compatible with 'Everything' preference"]
            meal.compatibility_analyses.is_compatible = True
            meal.compatibility_analyses.confidence = 1.0
            meal.compatibility_analyses.save()
        return meals
    
    # Combine all preferences for analysis
    all_preferences = list(regular_preferences)
    if has_everything_pref and (regular_preferences.count() > 1 or custom_preferences.exists()):
        # If user has "Everything" but also has other preferences, ignore "Everything"
        all_preferences = [pref for pref in all_preferences if pref.name != "Everything"]
    
    # Add custom preferences to the list
    all_preferences.extend(list(custom_preferences))
    
    # Start with all available meals or the provided pool
    available_meals = meal_pool or Meal.objects.filter(is_active=True)
    compatible_meals = []
    
    for meal in available_meals:
        # Check compatibility with all user preferences
        is_compatible = True
        compatibility_reasons = []
        
        for preference in all_preferences:
            # First check if explicitly tagged (faster than API call)
            if hasattr(preference, 'name') and meal.dietary_preferences.filter(name=preference.name).exists():
                compatibility_reasons.append(f"Explicitly tagged as {preference.name}")
                continue
            
            # For custom preferences, check custom dietary preferences
            if hasattr(preference, 'custom_name') and meal.custom_dietary_preferences.filter(custom_name=preference.custom_name).exists():
                compatibility_reasons.append(f"Explicitly tagged as {preference.custom_name}")
                continue
                
            # Get the preference name (handle both regular and custom)
            pref_name = preference.name if hasattr(preference, 'name') else preference.custom_name
            
            # Check if we have a cached compatibility analysis for this meal and preference
            from meals.models import MealCompatibility
            cached_analysis = MealCompatibility.objects.filter(
                meal=meal,
                preference_name=pref_name
            ).first()
            
            if cached_analysis:
                # Use the cached result
                if not cached_analysis.is_compatible or cached_analysis.confidence < 0.7:
                    is_compatible = False
                    break
                compatibility_reasons.append(cached_analysis.reasoning)
            else:
                # If not cached, perform new analysis
                result = analyze_meal_compatibility(meal, pref_name)
                
                # Cache the result for future use
                try:
                    MealCompatibility.objects.create(
                        meal=meal,
                        preference_name=pref_name,
                        is_compatible=result.get("is_compatible", False),
                        confidence=result.get("confidence", 0.0),
                        reasoning=result.get("reasoning", "")
                    )
                except Exception as e:
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_compatible_meals_for_user", "traceback": traceback.format_exc()})
                
                if not result["is_compatible"] or result["confidence"] < 0.7:
                    is_compatible = False
                    break
                
                compatibility_reasons.append(result["reasoning"])
        
        if is_compatible:
            # Add compatibility reasons to the meal for explanation
            meal.compatibility_analyses.reasoning = compatibility_reasons
            meal.compatibility_analyses.is_compatible = True
            meal.compatibility_analyses.confidence = 1.0
            meal.compatibility_analyses.save()
            compatible_meals.append(meal)
    
    return compatible_meals

@shared_task
@handle_task_failure
def create_meal_plan_for_new_user(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        today = timezone.now().date()
        # 1) The actual sign-up day:
        start_of_week = today
        # 2) "end_of_week" is "through Sunday" or user-specific logic:
        end_of_week = today + timedelta(days=(6 - today.weekday()))

        # 3) Also compute the canonical Monday for that same calendar week
        #    If you want a "strict Monday," do:
        monday_of_week = today - timedelta(days=today.weekday())  # always a Monday

        # Pass all three to create_meal_plan_for_user
        meal_plan = create_meal_plan_for_user(
            user=user,
            start_of_week=start_of_week,  # e.g. actual sign-up day
            end_of_week=end_of_week,
            monday_date=monday_of_week,   # canonical Monday for reference
        )
        # Auto‑approval handled inside create_meal_plan_for_user
            
    except CustomUser.DoesNotExist:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": "User with id {user_id} does not exist.", "source":"create_meal_plan_for_new_user", "traceback": traceback.format_exc()})

@shared_task
@handle_task_failure
def create_meal_plan_for_all_users():
    """
    Create meal plans for all users, respecting their local timezones.
    Only creates and sends meal plans on Saturday in the user's local timezone.
    """
    server_today = timezone.now().date()
    
    # Fetch all users with confirmed emails and auto-plans enabled
    users = CustomUser.objects.filter(email_confirmed=True, auto_meal_plans_enabled=True)
    
    for user in users:
        # Check if it's Saturday in the user's timezone
        if is_saturday_in_timezone(user.timezone):
            logger.info(f"It's Saturday in {user.timezone} for user {user.username}. Creating meal plan.")
            
            # Calculate start and end dates for the upcoming week
            user_tz = ZoneInfo(user.timezone)
            user_local_time = timezone.now().astimezone(user_tz)
            user_local_date = user_local_time.date()
            
            # Calculate days until next Monday (weekday 0)
            days_until_monday = (7 - user_local_date.weekday()) % 7
            if days_until_monday == 0:  # If today is Monday
                days_until_monday = 7  # Use next Monday
                
            # Calculate start and end dates for the meal plan
            start_of_week = user_local_date + timedelta(days=days_until_monday)  # Next Monday
            end_of_week = start_of_week + timedelta(days=6)  # Sunday after next Monday
            
            # Create meal plan for the user
            meal_plan = create_meal_plan_for_user(user=user, start_of_week=start_of_week, end_of_week=end_of_week)
            # Auto‑approval handled inside create_meal_plan_for_user


def day_to_offset(day_name: str) -> int:
    """Convert 'Monday' -> 0, 'Tuesday' -> 1, etc."""
    mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    return mapping.get(day_name, 0)

@shared_task(ignore_result=True)
@handle_task_failure
def create_meal_plan_for_user(
    user=None,
    user_id=None,
    start_of_week: Optional[datetime.date] = None,
    end_of_week: Optional[datetime.date] = None,
    monday_date: Optional[datetime.date] = None,
    request_id: Optional[str] = None,
    *,
    days_to_plan: Optional[List[str]] = None,
    prioritized_meals: Optional[Dict[str, List[str]]] = None,
    user_prompt: Optional[str] = None,
    number_of_days: Optional[int] = None,
):
    """
    Create a meal plan for a user for a specific week, allowing for flexibility.
    
    If start_of_week and end_of_week are not provided, they must be calculable.
    
    Parameters:
    - user: The user object to create the meal plan for (for direct calls).
    - user_id: The user ID to create the meal plan for (for Celery task calls).
    - start_of_week: The start date of the week.
    - end_of_week: The end date of the week.
    - monday_date: The Monday date of the week (optional, used for plan identification).
    - request_id: Optional request ID for logging correlation.
    - days_to_plan (keyword-only): Optional list of weekday names (e.g., ['Monday', 'Wednesday']) to populate. Defaults to the entire week between start_of_week and end_of_week if None.
    - prioritized_meals (keyword-only): Optional dict mapping day names to lists of meal types to prioritize (e.g., {'Friday': ['Dinner', 'Lunch']}). Meals not listed are added after prioritized ones. Defaults to ['Breakfast', 'Lunch', 'Dinner'] order if None or day not specified.
    - user_prompt (keyword-only): Optional free-text user request that triggered this plan (e.g., "Lunches for cutting phase"). Passed down for better meal generation context.
    
    Returns:
    - The created MealPlan object or None if creation failed.
    
    Note:
    - This function is backward-compatible. Existing calls without the new keyword-only arguments will continue to work using the default behavior (full week, standard meal order).
    """
    from meals.pantry_management import get_expiring_pantry_items
    from meals.models import (STATUS_SCHEDULED, STATUS_OPEN)
    from custom_auth.models import CustomUser

    # Handle both user object and user_id parameters
    if user is not None and user_id is not None:
        raise ValueError("Cannot provide both 'user' and 'user_id' parameters")
    elif user is None and user_id is None:
        raise ValueError("Must provide either 'user' or 'user_id' parameter")
    elif user_id is not None:
        # Fetch user object from user_id (for Celery task calls)
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            logger.error(f"[{request_id}] User with ID {user_id} not found")
            return None
    # If user object was provided directly, continue using it

    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    logger.info(f"[{request_id}] Creating meal plan for user {user.username} from {start_of_week} to {end_of_week}")
    # Capture user's stored goal description, if available
    user_goal_description = getattr(getattr(user, "goals", None), "goal_description", "")
    if user_prompt is None:
        user_prompt = user_goal_description
    today = timezone.localdate()
    if start_of_week is None or end_of_week is None:
        # Calculate Monday and Sunday around today
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week   = start_of_week + timedelta(days=6)    
    # Use a transaction to prevent race conditions
    with transaction.atomic():
        logger.info(f"[{request_id}] Starting transaction for meal plan creation")
        
        # Use get_or_create to atomically handle the meal plan creation/retrieval
        # This prevents race conditions where two processes try to create the same meal plan
        # IMPORTANT: Do not change this back to separate existence check + create()
        # as it will reintroduce race conditions in concurrent environments (Celery tasks, etc.)
        try:
            meal_plan, created = MealPlan.objects.get_or_create(
                user=user,
                week_start_date=start_of_week if monday_date is None else monday_date,
                week_end_date=end_of_week,
                defaults={}  # No additional defaults needed since we're only setting the required fields
            )
            
            if created:
                logger.info(f"[{request_id}] Created new meal plan (ID: {meal_plan.id}) for user {user.username}")
            else:
                logger.info(f"[{request_id}] Found existing meal plan (ID: {meal_plan.id}) for user {user.username}")
                
                # Check if the existing plan has meals
                existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan)
                
                if existing_meals.exists():
                    logger.info(f"[{request_id}] User {user.username} already has meals for the week. Returning existing plan.")
                    return meal_plan
                else:
                    # Empty meal plan - we can proceed to add meals to it
                    logger.info(f"[{request_id}] Found empty meal plan (ID: {meal_plan.id}) for user {user.username}. Will populate with meals.")
                    
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"create_meal_plan_for_user", "traceback": traceback.format_exc()})
            logger.error(f"[{request_id}] Exception during meal plan creation/retrieval: {e}")
            return None

        user_id = user.id
        
        # These operations need to be inside the same transaction to prevent race conditions
        meal_types = ['Breakfast', 'Lunch', 'Dinner']

        # parse prompt into structured map 
        allowed_map = None
        if user_prompt:
            input = [
                {
                    "role": "developer",
                    "content": (
                        "You are responsible for understanding a user's request and turning it into a mapped list of meal day and meal type where applicable. Do not include meal days or types where the user did not specify. "
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Please use my prompt to create a list of meal days and meal types that I should plan for the week. "
                        f"Prompt: {user_prompt} and days to plan: {days_to_plan if days_to_plan else 'None'} and number of days: {number_of_days if number_of_days else 'None'}"
                    )
                }
            ]
            groq_client = _get_groq_client()
            if groq_client:
                groq_messages = [
                    {"role": ("system" if m.get("role") == "developer" else m.get("role")), "content": m.get("content")}
                    for m in input
                ]
                raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
                if raw_create:
                    raw_create = groq_client.chat.completions.with_raw_response.create
                groq_resp = groq_call_with_retry(
                    raw_create_fn=raw_create,
                    create_fn=groq_client.chat.completions.create,
                    desc='meal_plan_service.parse_prompt',
                    model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                    messages=groq_messages,
                    temperature=0.2,
                    top_p=1,
                    stream=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "meal_map",
                            "schema": PromptMealMap.model_json_schema(),
                        },
                    },
                )
                raw_json = groq_resp.choices[0].message.content or "{}"
            else:
                call = get_openai_client().responses.create(
                    model="gpt-5-mini",
                    input=input,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "meal_map",
                            "schema": PromptMealMap.model_json_schema(),
                            "strict": True
                        }
                    }
                )
                raw_json = call.output_text
            parsed = PromptMealMap.model_validate_json(raw_json)
            allowed_map = {(s.day, s.meal_type.value): True for s in parsed.slots}
                
        existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
        existing_meal_names = set(existing_meals.values_list('meal__name', flat=True))
        existing_meal_embeddings = list(existing_meals.values_list('meal__meal_embedding', flat=True))

        skipped_meal_ids = set()
        used_pantry_item = False  # ADDED

        # Determine and normalize the valid days to plan for
        if start_of_week and end_of_week:
            # 1) Build the set of actual weekdays in the span
            valid_week_days = {
                (start_of_week + timedelta(days=i)).strftime("%A")
                for i in range((end_of_week - start_of_week).days + 1)
            }
        else:
            logger.error(f"[{request_id}] Cannot determine planning days. Need start/end dates or explicit days_to_plan.")
            meal_plan.delete()
            return None

        # 2) Select source days based on prompt, UI, or default
        if allowed_map:
            candidate_days = sorted({d for d, _ in allowed_map})
        elif days_to_plan:
            candidate_days = [d.capitalize() for d in days_to_plan]
        else:
            candidate_days = sorted(valid_week_days)

        # 3) Filter to only days that actually fall within this week
        planning_days = [day for day in candidate_days if day in valid_week_days]

        # 4) Fallback to full week if none matched
        if not planning_days:
            logger.warning(
                f"[{request_id}] No valid planning days found from candidate_days {candidate_days} "
                f"in the week {start_of_week} to {end_of_week}. Falling back to full week."
            )
            planning_days = sorted(valid_week_days)

        logger.info(f"[{request_id}] Planning meals for days: {', '.join(planning_days)}")

        # Map planning days to their offset from the start_of_week for date calculation
        day_offset_map = {
            day: offset
            for offset, day in enumerate(
                (start_of_week + timedelta(days=i)).strftime("%A")
                for i in range((end_of_week - start_of_week).days + 1)
            ) if day in planning_days
        }
        
        # Initialize progress tracking in Redis for SSE
        try:
            from utils.redis_client import set as redis_set
            total_slots = len(planning_days) * len(meal_types)
            progress_key = f"meal_plan_job:{user_id}:{start_of_week.strftime('%Y_%m_%d')}"
            ok = redis_set(progress_key, {"total": total_slots, "added": 0}, 3600)
            print(f"[SSE-PROG] init job_key={progress_key} total={total_slots} set_ok={ok}", flush=True)
        except Exception as e:
            print(f"[SSE-PROG] init progress set failed: {e}", flush=True)
            progress_key = None
        added_count = 0

        # Preload previous 3 weeks' meals to avoid reusing them
        try:
            ranges = [
                (
                    start_of_week - timedelta(days=7*i),
                    end_of_week - timedelta(days=7*i)
                ) for i in range(1, 4)
            ]
            from django.db.models import Q
            week_q = Q()
            for ws, we in ranges:
                week_q |= Q(meal_plan__week_start_date=ws, meal_plan__week_end_date=we)
            prev_meal_ids = set(
                MealPlanMeal.objects.filter(
                    Q(meal_plan__user=user) & week_q
                ).values_list('meal_id', flat=True)
            )
            if prev_meal_ids:
                skipped_meal_ids.update(prev_meal_ids)
                logger.info(f"[{request_id}] Preloaded {len(prev_meal_ids)} prior-3-week meal IDs to skip.")
        except Exception:
            pass

        for day_name in planning_days:
            day_offset = day_offset_map[day_name]
            meal_date = start_of_week + timedelta(days=day_offset)
    
            # Determine meal type order for the current day
            day_meal_types = meal_types.copy()  # Default order
            if prioritized_meals:
                day_priorities = prioritized_meals.get(day_name)
                if day_priorities:
                    # Filter priorities to valid meal types and create sorted list
                    prios = [m for m in day_priorities if m in meal_types]
                    # Append remaining meal types in their original order
                    day_meal_types = prios + [m for m in meal_types if m not in prios]
    
            # If user_prompt produced an allowed_map, restrict meal_types to only requested ones for this day
            if allowed_map:
                # Collect the meal types requested by the user for this day
                requested_meals = [mt for (d, mt) in allowed_map.keys() if d == day_name]
                # Filter the default/prioritized list to only those requested
                day_meal_types = [mt for mt in day_meal_types if mt in requested_meals]
                if not day_meal_types:
                    logger.info(f"[{request_id}] No meal types requested for {day_name}. Skipping day.")
                    continue

            for meal_type in day_meal_types:
                # Check if a meal already exists for this day and meal type
                if MealPlanMeal.objects.filter(
                    meal_plan=meal_plan,
                    meal_date=meal_date,
                    day=day_name,
                    meal_type=meal_type
                ).exists():
                    continue
    
                attempt = 0
                meal_added = False
    
                while attempt < MAX_ATTEMPTS and not meal_added:
                    attempt += 1
    
                    # If we have soon-to-expire items, prefer generating new meal 
                    # rather than reusing an existing one
                    expiring_items = get_expiring_pantry_items(user, days_threshold=7)
                    if expiring_items:
                        logger.info(f"[{request_id}] Found {len(expiring_items)} expiring pantry items. Will generate new meal.")
                        meal_found = None
                    else:
                        meal_found = find_existing_meal(
                            user,
                            meal_type,
                            existing_meal_embeddings,
                            existing_meal_names,
                            skipped_meal_ids
                        )
    
                    if meal_found is None:
                        # Create new meal
                        logger.info(f"[{request_id}] No suitable existing meal found. Generating new meal for {day_name} {meal_type}.")
                        if user_prompt is None:
                            result = generate_and_create_meal(
                                user=user,
                                meal_plan=meal_plan,
                                meal_type=meal_type,
                                existing_meal_names=existing_meal_names,
                                existing_meal_embeddings=existing_meal_embeddings,
                                user_id=user_id,
                                day_name=day_name,
                                request_id=request_id,
                                user_goal_description=user_goal_description,
                            )
                        else:
                            result = generate_and_create_meal(
                                user=user,
                                meal_plan=meal_plan,
                                meal_type=meal_type,
                                existing_meal_names=existing_meal_names,
                                existing_meal_embeddings=existing_meal_embeddings,
                                user_id=user_id,
                                day_name=day_name,
                                request_id=request_id,
                                user_goal_description=user_goal_description,
                                user_prompt=user_prompt
                            )
                        if result['status'] == 'success':
                            meal = result['meal']
                            
                            # Check if the generated meal is allergen-safe
                            is_safe, flagged_ingredients, substitutions = check_meal_for_allergens_gpt(meal, user)
                            
                            if not is_safe:
                                logger.warning(f"[{request_id}] Generated meal '{meal.name}' contains potential allergens: {', '.join(flagged_ingredients)}.")
                                
                                # If we have substitutions, try to create a modified version
                                if substitutions and len(substitutions) > 0:
                                    logger.info(f"[{request_id}] Found substitutions for {len(substitutions)} ingredients. Attempting to create a modified version.")
                                    modified_meal = apply_substitutions_to_meal(meal, substitutions, user)
                                    
                                    if modified_meal:
                                        # Successfully created a modified version, use it instead
                                        logger.info(f"[{request_id}] Successfully created modified meal '{modified_meal.name}'. Using it instead.")
                                        meal = modified_meal
                                        meal_added = True
                                    else:
                                        # Failed to create a modified version, skip this meal
                                        logger.warning(f"[{request_id}] Failed to create a modified version of meal '{meal.name}'. Skipping.")
                                        skipped_meal_ids.add(meal.id)
                                        continue
                                else:
                                    # No substitutions available, skip this meal
                                    logger.warning(f"[{request_id}] No substitutions available for meal '{meal.name}'. Skipping.")
                                    skipped_meal_ids.add(meal.id)
                                    continue
                            else:
                                # Meal is safe, add it
                                meal_added = True
                                
                            logger.info(f"[{request_id}] Successfully added meal '{meal.name}' for {day_name} {meal_type}")
                            # Publish SSE event for new meal
                            try:
                                from utils.redis_client import get_redis_connection, get as redis_get, set as redis_set
                                from meals.serializers import MealPlanMealSerializer
                                conn = get_redis_connection()
                                if conn is not None:
                                    channel = f"meal_plan_stream:{user.id}:{start_of_week.strftime('%Y_%m_%d')}"
                                    # Retrieve the created plan meal
                                    offset = day_to_offset(day_name)
                                    meal_date = meal_plan.week_start_date + timedelta(days=offset)
                                    mpm = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day_name, meal_type=meal_type, meal=meal, meal_date=meal_date).first()
                                    if mpm:
                                        payload = {
                                            "event": "meal_added",
                                            "data": {"meal_plan_meal": MealPlanMealSerializer(mpm).data}
                                        }
                                        r_pub = conn.publish(channel, json.dumps(payload))
                                        print(f"[SSE-PUB] meal_added -> channel={channel} pub_res={r_pub}", flush=True)
                                        # Update and publish progress
                                        added_count += 1
                                        if progress_key:
                                            job_info = redis_get(progress_key) or {"total": total_slots, "added": 0}
                                            job_info["added"] = added_count
                                            ok = redis_set(progress_key, job_info, 3600)
                                            pct = int((added_count / max(total_slots, 1)) * 100)
                                            r_prog = conn.publish(channel, json.dumps({"event": "progress", "data": {"pct": pct}}))
                                            print(f"[SSE-PROG] job_key={progress_key} added={job_info['added']} total={job_info.get('total')} set_ok={ok}; [SSE-PUB] progress pct={pct} pub_res={r_prog}", flush=True)
                            except Exception as e:
                                print(f"[SSE-PUB] publish meal_added/progress failed: {e}", flush=True)
                            
                            # If that meal used pantry items, keep track of it
                            if result.get('used_pantry_item'):
                                used_pantry_item = True
                                logger.info(f"[{request_id}] Meal '{meal.name}' used pantry items")
                        else:
                            logger.warning(f"[{request_id}] Attempt {attempt}: {result['message']}")
                            continue
                    else:
                        # existing meal found, do a sanity check
                        logger.info(f"[{request_id}] Found existing meal '{meal_found.name}' for {day_name} {meal_type}. Performing sanity check.")
                        
                        # Check if the found meal is allergen-safe
                        is_safe, flagged_ingredients, substitutions = check_meal_for_allergens_gpt(meal_found, user)
                        
                        if not is_safe:
                            logger.warning(f"[{request_id}] Existing meal '{meal_found.name}' contains potential allergens: {', '.join(flagged_ingredients)}.")
                            
                            # If we have substitutions, try to create a modified version
                            if substitutions and len(substitutions) > 0:
                                logger.info(f"[{request_id}] Found substitutions for {len(substitutions)} ingredients. Attempting to create a modified version.")
                                modified_meal = apply_substitutions_to_meal(meal_found, substitutions, user)
                                
                                if modified_meal:
                                    # Successfully created a modified version, use it instead
                                    logger.info(f"[{request_id}] Successfully created modified meal '{modified_meal.name}'. Using it instead.")
                                    meal_found = modified_meal
                                else:
                                    # Failed to create a modified version, skip this meal
                                    logger.warning(f"[{request_id}] Failed to create a modified version of meal '{meal_found.name}'. Skipping.")
                                    skipped_meal_ids.add(meal_found.id)
                                    continue
                            else:
                                # No substitutions available, skip this meal
                                logger.warning(f"[{request_id}] No substitutions available for meal '{meal_found.name}'. Skipping.")
                                skipped_meal_ids.add(meal_found.id)
                                continue
                        
                        # Calculate the target date for this meal slot
                        offset = day_to_offset(day_name)
                        target_meal_date = meal_plan.week_start_date + timedelta(days=offset)
                        
                        # If it's a chef meal, verify event availability for this specific date
                        is_valid_chef_meal_for_date = True # Assume valid unless proven otherwise
                        if meal_found.chef is not None:
                            event_exists = ChefMealEvent.objects.filter(
                                meal=meal_found,
                                chef=meal_found.chef,
                                event_date=target_meal_date, 
                                status__in=[STATUS_SCHEDULED, STATUS_OPEN],
                                order_cutoff_time__gt=timezone.now()
                            ).exists()
                            
                            if not event_exists:
                                logger.warning(f"[{request_id}] No active ChefMealEvent found for meal '{meal_found.name}' on {target_meal_date}. Skipping for this day/type.")
                                is_valid_chef_meal_for_date = False
                                skipped_meal_ids.add(meal_found.id) # Add to skipped so we don't keep finding it for wrong dates
                        # Proceed only if basic sanity check passes AND (it's not a chef meal OR it's a chef meal with a valid event for the date)
                        if perform_comprehensive_sanity_check(meal_found, user, request_id) and is_valid_chef_meal_for_date:
                            try:
                                # Use get_or_create to handle potential race conditions atomically
                                meal_plan_meal, created = MealPlanMeal.objects.get_or_create(
                                    meal_plan=meal_plan,
                                    day=day_name,
                                    meal_type=meal_type,
                                    defaults={
                                        'meal': meal_found,
                                        'meal_date': target_meal_date,
                                    }
                                )
                                
                                if created:
                                    logger.info(f"[{request_id}] Added new meal '{meal_found.name}' for {day_name} {meal_type} on {target_meal_date}.")
                                else:
                                    # Update the existing meal
                                    logger.warning(f"[{request_id}] Meal already exists for {day_name} {meal_type}. Updating existing meal.")
                                    meal_plan_meal.meal = meal_found
                                    meal_plan_meal.meal_date = target_meal_date
                                    meal_plan_meal.save()
                                    logger.info(f"[{request_id}] Updated existing meal for {day_name} {meal_type} with '{meal_found.name}'.")
                                
                                existing_meal_names.add(meal_found.name)
                                existing_meal_embeddings.append(meal_found.meal_embedding)
                                meal_added = True
                                # Publish SSE event for new meal
                                try:
                                    from utils.redis_client import get_redis_connection, get as redis_get, set as redis_set
                                    from meals.serializers import MealPlanMealSerializer
                                    conn = get_redis_connection()
                                    if conn is not None:
                                        channel = f"meal_plan_stream:{user.id}:{start_of_week.strftime('%Y_%m_%d')}"
                                        mpm = meal_plan_meal
                                        payload = {
                                            "event": "meal_added",
                                            "data": {"meal_plan_meal": MealPlanMealSerializer(mpm).data}
                                        }
                                        r_pub = conn.publish(channel, json.dumps(payload))
                                        print(f"[SSE-PUB] meal_added -> channel={channel} pub_res={r_pub}", flush=True)
                                        # Update and publish progress
                                        added_count += 1
                                        if progress_key:
                                            job_info = redis_get(progress_key) or {"total": total_slots, "added": 0}
                                            job_info["added"] = added_count
                                            ok = redis_set(progress_key, job_info, 3600)
                                            pct = int((added_count / max(total_slots, 1)) * 100)
                                            r_prog = conn.publish(channel, json.dumps({"event": "progress", "data": {"pct": pct}}))
                                            print(f"[SSE-PROG] job_key={progress_key} added={job_info['added']} total={job_info.get('total')} set_ok={ok}; [SSE-PUB] progress pct={pct} pub_res={r_prog}", flush=True)
                                except Exception as e:
                                    print(f"[SSE-PUB] publish meal_added/progress failed: {e}", flush=True)
                            except Exception as e:
                                # n8n traceback
                                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                                requests.post(n8n_traceback_url, json={"error": str(e), "source":"create_meal_plan_for_user", "traceback": traceback.format_exc()})
                                skipped_meal_ids.add(meal_found.id)
                        else:
                             # Log reason for skipping
                            if not is_valid_chef_meal_for_date:
                                # Already logged the event missing warning
                                pass # No need to log again
                            else: # Must have failed sanity check
                                 logger.warning(f"[{request_id}] Meal '{meal_found.name}' failed comprehensive sanity check. Skipping.")
                                 skipped_meal_ids.add(meal_found.id)
                            meal_found = None  # Force retry finding/generating a different meal

                    if attempt >= MAX_ATTEMPTS and not meal_added:
                        logger.error(f"[{request_id}] Failed to add meal for {day_name} {meal_type} after {MAX_ATTEMPTS} attempts.")

        # Check if we added any meals - still inside the transaction
        meal_count = MealPlanMeal.objects.filter(meal_plan=meal_plan).count()
        if meal_count == 0:
            logger.error(f"[{request_id}] No meals were added to meal plan (ID: {meal_plan.id}). Deleting it.")
            meal_plan.delete()
            return None

        logger.info(f"[{request_id}] Meal plan created successfully for {user.username} with {meal_count} meals across {len(planning_days)} day(s)")

    # These operations can be outside the transaction since we now have a validated meal plan with meals
    # Always analyze and replace for variety to prevent repeated plans week-to-week
    logger.info(f"[{request_id}] Running variety analysis and replacements (if needed).")
    analyze_and_replace_meals(user, meal_plan, meal_types, request_id)

    # Auto‑approve newly created meal plans and clear change flags
    meal_plan.is_approved = True
    meal_plan.has_changes = False
    meal_plan.save()

    # No approval email — plan is considered approved immediately

    # # Generate emergency supply list if user has enabled this
    # if user.emergency_supply_goal and user.emergency_supply_goal > 0:
    #     logger.info(f"[{request_id}] User has emergency supply goal of {user.emergency_supply_goal} days. Generating supply list.")
    #     generate_emergency_supply_list(user.id)

    # Clean up Redis lock if this task was called with lock management
    try:
        from utils.redis_client import delete
        # Try to determine the lock key from the task context
        # This is a bit tricky since we don't have direct access to the task ID here
        # We'll use the user_id and start_of_week to construct the lock key
        lock_key = f"meal_plan_generation_lock_{user_id}_{start_of_week.strftime('%Y_%m_%d')}"
        deleted = delete(lock_key)
        if deleted:
            logger.info(f"[{request_id}] Successfully cleaned up Redis lock {lock_key} on successful completion")
        else:
            logger.debug(f"[{request_id}] Redis lock {lock_key} was not found or already expired")
    except Exception as e:
        logger.warning(f"[{request_id}] Error cleaning up Redis lock: {str(e)}")

    # Publish done event
    try:
        from utils.redis_client import get_redis_connection
        conn = get_redis_connection()
        if conn is not None:
            channel = f"meal_plan_stream:{user.id}:{start_of_week.strftime('%Y_%m_%d')}"
            r1 = conn.publish(channel, json.dumps({"event": "progress", "data": {"pct": 100}}))
            r2 = conn.publish(channel, json.dumps({"event": "done", "data": {}}))
            print(f"[SSE-PUB] final progress=100 pub_res={r1}; done pub_res={r2} channel={channel}", flush=True)
    except Exception as e:
        print(f"[SSE-PUB] final publish failed: {e}", flush=True)

    return meal_plan


# -----------------------------------------------
# New function: modify_existing_meal_plan
# -----------------------------------------------
def modify_existing_meal_plan(
    user,
    meal_plan_id: int,
    user_prompt: Optional[str] = None,
    *,
    days_to_modify: Optional[List[str]] = None,
    prioritized_meals: Optional[Dict[str, List[str]]] = None,
    request_id: Optional[str] = None,
    should_remove: bool = False,
    run_variety_analysis: bool = True,
):
    """
    Modify an existing meal plan for a user in‑place.

    This mirrors the behaviour of `create_meal_plan_for_user` but operates
    on an already‑created `MealPlan` identified by `meal_plan_id`.

    Parameters
    ----------
    user : CustomUser
        The owner of the meal plan.
    meal_plan_id : int
        ID of the `MealPlan` to modify.
    user_prompt : str, optional
        Free‑text prompt that triggered the modification.
    days_to_modify : list[str], keyword‑only, optional
        Weekday names (e.g. ['Tuesday', 'Thursday']) whose meals should be
        regenerated.  If `None`, the entire week is considered.
    prioritized_meals : dict[str, list[str]], keyword‑only, optional
        Same semantics as in `create_meal_plan_for_user`.
    request_id : str, optional
        An externally‑supplied request ID for log correlation.
    should_remove : bool, optional
        If True, the meal will be removed without being replaced. Default is False.

    Returns
    -------
    MealPlan | None
        The modified `MealPlan` object on success, otherwise `None`.
    """
    from meals.models import MealPlanMeal
    from django.db import transaction
    from django.utils import timezone

    if request_id is None:
        request_id = str(uuid.uuid4())

    log_prefix = f"[{request_id}]"
    logger.info(f"{log_prefix} Modifying meal_plan {meal_plan_id} for {user.username}")
    # 1. Fetch & sanity‑check the meal plan
    try:
        with transaction.atomic():
            meal_plan = MealPlan.objects.select_for_update().get(id=meal_plan_id, user=user)
            
            # Check if meal plan is from a previous week (end date is before today)
            current_date = timezone.now().date()
            if meal_plan.week_end_date < current_date:
                logger.warning(f"{log_prefix} Attempted to modify a meal plan from a previous week (ID: {meal_plan_id})")
                return None
            
            start_of_week = meal_plan.week_start_date
            end_of_week   = meal_plan.week_end_date
            meal_types    = ['Breakfast', 'Lunch', 'Dinner']

            # 2. Determine which days to touchRight
            if days_to_modify:
                planning_days = [d.capitalize() for d in days_to_modify]
            else:
                planning_days = [
                    (start_of_week + timedelta(days=i)).strftime("%A")
                    for i in range((end_of_week - start_of_week).days + 1)
                ]

            day_offset_map = {
                day: offset
                for offset, day in enumerate(
                    (start_of_week + timedelta(days=i)).strftime("%A")
                    for i in range((end_of_week - start_of_week).days + 1)
                ) if day in planning_days
            }

            # 3. Gather context from existing plan
            existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan)
            existing_meal_names = set(existing_meals.values_list("meal__name", flat=True))
            existing_meal_embeddings = list(existing_meals.values_list("meal__meal_embedding", flat=True))

            skipped_meal_ids: Set[int] = set()

            # 4. Iterate through selected days/types
            for day_name in planning_days:
                day_offset = day_offset_map[day_name]
                meal_date  = start_of_week + timedelta(days=day_offset)

                # Establish meal order for this day
                # FIXED: Only regenerate meal types the caller explicitly asked for
                if prioritized_meals and prioritized_meals.get(day_name):
                    day_meal_types = [m for m in prioritized_meals[day_name] if m in meal_types]
                else:
                    day_meal_types = meal_types.copy()  # fallback for "touch whole day"
                
                # Add safety check to avoid processing days with no meal types to modify
                if not day_meal_types:
                    continue

                for meal_type in day_meal_types:
                    log_ctx = f"{log_prefix} {day_name} {meal_type}"

                    # Remove current MealPlanMeal (if any) – we regenerate from scratch
                    mpm_to_delete = MealPlanMeal.objects.filter(
                        meal_plan=meal_plan,
                        meal_date=meal_date,
                        day=day_name,
                        meal_type=meal_type
                    )
                    for mpm in mpm_to_delete:
                        mpm.delete()

                    # If meal should be removed, skip generation
                    if should_remove:
                        logger.info(f"{log_ctx} Meal removed as requested and will not be replaced")
                        continue

                    attempt     = 0
                    meal_added  = False
                    MAX_ATTEMPTS = 3  # keep it light for modifications

                    while attempt < MAX_ATTEMPTS and not meal_added:
                        attempt += 1

                        # Re‑use the existing helper that prefers pantry items / uniqueness
                        result = generate_and_create_meal(
                            user=user,
                            meal_plan=meal_plan,
                            meal_type=meal_type,
                            existing_meal_names=existing_meal_names,
                            existing_meal_embeddings=existing_meal_embeddings,
                            user_id=user.id,
                            day_name=day_name,
                            request_id=request_id,
                            user_prompt=user_prompt
                        )

                        if result["status"] == "success":
                            new_meal = result["meal"]
                            existing_meal_names.add(new_meal.name)
                            existing_meal_embeddings.append(new_meal.meal_embedding)
                            meal_added = True
                            logger.info(f"{log_ctx} added '{new_meal.name}'")

                        else:
                            logger.warning(f"{log_ctx} {result['message']}")


                    if not meal_added:
                        logger.error(f"{log_ctx} failed after {MAX_ATTEMPTS} attempts")
    except MealPlan.DoesNotExist:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": "MealPlan does not exist or is not owned by user.", "source":"modify_existing_meal_plan", "traceback": traceback.format_exc()})
        logger.error(f"{log_prefix} MealPlan {meal_plan_id} does not exist or is not owned by user.")
        return None

    # 5. Re‑analyse plan for similarity after changes (optional)
    if run_variety_analysis:
        analyze_and_replace_meals(user, meal_plan, meal_types, request_id)

    # 6. Persist & flag: require manual approval after modifications
    meal_plan.is_approved = False
    meal_plan.has_changes = True
    meal_plan.save()

    logger.info(f"{log_prefix} Meal plan modification complete.")
    return meal_plan

def analyze_and_replace_meals(user, meal_plan, meal_types, request_id=None):
    """
    Analyze the meal plan and replace meals that are too similar to previous weeks.
    
    Parameters:
    - user: The user whose meal plan is being analyzed
    - meal_plan: The MealPlan object to analyze
    - meal_types: List of meal types (e.g., 'Breakfast', 'Lunch', 'Dinner')
    - request_id: Optional request ID for logging correlation
    
    Returns:
    - None
    """
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    # Fetch previous meal plans (last 3 weeks)
    last_week_meal_plan = MealPlan.objects.filter(user=user, week_start_date=meal_plan.week_start_date - timedelta(days=7)).first()
    two_weeks_ago_meal_plan = MealPlan.objects.filter(user=user, week_start_date=meal_plan.week_start_date - timedelta(days=14)).first()
    three_weeks_ago_meal_plan = MealPlan.objects.filter(user=user, week_start_date=meal_plan.week_start_date - timedelta(days=21)).first()

    # Query the user's meal plan meals
    current_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan)
    previous_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=last_week_meal_plan)
    two_weeks_ago_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=two_weeks_ago_meal_plan)
    three_weeks_ago_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=three_weeks_ago_meal_plan)

    current_meal_plan_str = format_meal_plan(current_meal_plan_meals)
    previous_week_plan_str = format_meal_plan(previous_meal_plan_meals)
    two_weeks_ago_plan_str = format_meal_plan(two_weeks_ago_meal_plan_meals)
    three_weeks_ago_plan_str = format_meal_plan(three_weeks_ago_meal_plan_meals)

    try:
        input = [
            {
                "role": "developer",
                "content": (
                    """
                    You are a meal planning assistant tasked with ensuring variety in the user's meal plans. Analyze the current week's meal plan in the context of the previous two weeks' meal plans. Identify any meals that are duplicates or too similar to previous meals and should be replaced. Provide your response in the specified JSON format.

                    Evaluate the meal plans as follows:
                    - Compare the meals of the current week against those from the previous two weeks.
                    - Assess both exact duplicates and meals that are too similar in terms of ingredients, preparation, or flavor profile.
                    - Consider meals too similar if they share the majority of their main ingredients or would result in the user experiencing a lack of variety.

                    # Steps

                    1. Gather the meal plans for the current and previous two weeks.
                    2. Identify duplicate or similar meals within the current week's plan when compared to the prior weeks.
                    3. Create a list of meals to replace, specifying the detailed information for each meal using the MealsToReplaceSchema.

                    # Output Format

                    The output should be a JSON object following the MealsToReplaceSchema structure:
                    ```json
                    {
                    "meals_to_replace": [
                        {
                        "meal_id": [meal_id],
                        "day": "[day_of_week]",
                        "meal_type": "[meal_type]"
                        },
                        ...
                    ]
                    }
                    ```

                    # Examples

                    **Example Input:**
                    - Current Week's Meals: A list of meals with IDs, days, and types.
                    - Previous Two Weeks' Meals: Lists of meals for comparison.

                    **Example Output:**
                    ```json
                    {
                    "meals_to_replace": [
                        {
                        "meal_id": 101,
                        "day": "Tuesday",
                        "meal_type": "Lunch"
                        },
                        {
                        "meal_id": 205,
                        "day": "Thursday",
                        "meal_type": "Dinner"
                        }
                    ]
                    }
                    ```

                    # Notes

                    - Pay special attention to varying the protein sources, culinary styles, and key ingredients.
                    - If no replacements are needed, return an empty list for `meals_to_replace`.
                    - Ensure that the JSON output strictly adheres to the schema without any additional fields.
                    """
                )
            },
            {
                "role": "user",
                "content": (
                    f"User ID: {user.id}\n"
                    f"Meal Plan ID: {meal_plan.id}\n\n"
                    f"{generate_user_context(user)}\n\n"
                    f"Current Meal Plan:\n{current_meal_plan_str}\n\n"
                    f"Previous Week's Meal Plan:\n{previous_week_plan_str}\n\n"
                    f"Two Weeks Ago Meal Plan:\n{two_weeks_ago_plan_str}\n\n"
                    f"Three Weeks Ago Meal Plan:\n{three_weeks_ago_plan_str}\n\n"
                    "Please identify meals in the current meal plan that should be replaced to ensure variety. "
                )
            }
        ]
        #store=True,
        #metadata={'tag': 'meal-plan-analysis'}
        groq_client = _get_groq_client()
        if groq_client:

            groq_messages = [
                {"role": ("system" if m.get("role") == "developer" else m.get("role")), "content": m.get("content")}
                for m in input
            ]
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.analyze_and_replace_meals',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=groq_messages,
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "meals_to_replace",
                        "schema": MealsToReplaceSchema.model_json_schema(),
                    },
                },
            )
            assistant_message = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=input,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "meals_to_replace",
                        "schema": MealsToReplaceSchema.model_json_schema(),
                        "strict": True
                    }
                }
            )

            assistant_message = response.output_text

        try:
            # Step 1: Deserialize the string into a Python dictionary
            parsed_response = json.loads(assistant_message)

            # Step 2: Validate the parsed response with Pydantic
            meals_to_replace = MealsToReplaceSchema.model_validate(parsed_response)
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"analyze_and_replace_meals", "traceback": traceback.format_exc()})
            return

        # Initialize existing_meal_ids before replacements
        existing_meal_ids = list(current_meal_plan_meals.values_list('meal__id', flat=True))

        # Fetch all possible replacements for each meal type and shuffle them
        all_possible_replacements = {}
        for meal_type in meal_types:
            possible_replacements = list(get_possible_replacement_meals(
                user,
                meal_type,
                existing_meal_ids=existing_meal_ids
            ))
            shuffle(possible_replacements)
            all_possible_replacements[meal_type] = possible_replacements

        for meal_info in meals_to_replace:
            logger.warning(f"meal_info: {meal_info}")
            meal_replacement_list = meal_info[1]  # This will be the list of MealToReplace objects

            for meal_replacement in meal_replacement_list:
                meal_type = meal_replacement.meal_type
                day = meal_replacement.day
                old_meal_id = meal_replacement.meal_id

                possible_replacements = all_possible_replacements.get(meal_type, [])
                if not possible_replacements:
                    logger.warning(f"No possible replacements found for meal type {meal_type} on {day}")
                    # If we don't have a valid old_meal_id, skip removal to avoid 'Meal None not found.'
                    if not old_meal_id:
                        logger.warning(f"[{request_id}] Skipping removal for {day} {meal_type}: old_meal_id is None")
                        continue
                    # Delete the meal from the meal plan
                    result_remove = remove_meal_from_plan(
                        request=SimpleNamespace(data={'user_id': user.id}),
                        meal_plan_id=meal_plan.id,
                        meal_id=old_meal_id,
                        day=day,
                        meal_type=meal_type
                    )

                    if result_remove['status'] == 'success':
                        logger.info(f"[{request_id}] Removed meal {old_meal_id} from {day} ({meal_type})")  

                        # Fallback: Create a new meal
                        result = generate_and_create_meal(
                            user=user,
                            meal_plan=meal_plan,  # Pass the meal plan object
                            meal_type=meal_type,
                            existing_meal_names=set(),
                            existing_meal_embeddings=[],
                            user_id=user.id,
                            day_name=day,
                            request_id=request_id
                        )
                    else:
                        logger.error(f"[{request_id}] Failed to create a fallback meal for {meal_type} on {day}: {result_remove['message']}")
                    
                    continue  # Move to the next meal to replace

                # Iterate over possible replacements until a suitable one is found
                replacement_found = False
                while possible_replacements and not replacement_found:
                    # Pop a meal from the shuffled list to ensure it's not reused
                    new_meal = possible_replacements.pop()
                    new_meal_id = new_meal.id

                    # Perform the sanity check
                    if perform_comprehensive_sanity_check(new_meal, user, request_id):
                        # Update existing meal IDs to prevent selecting the same meal again
                        existing_meal_ids.append(new_meal_id)

                        # Log the replacement details for debugging
                        logger.info(f"[{request_id}] Replacing meal ID {old_meal_id} with meal ID {new_meal_id} for {meal_type} on {day}")

                        # Call replace_meal_in_plan
                        result = replace_meal_in_plan(
                            request=SimpleNamespace(data={'user_id': user.id}),
                            meal_plan_id=meal_plan.id,
                            old_meal_id=old_meal_id,
                            new_meal_id=new_meal_id,
                            day=day,
                            meal_type=meal_type
                        )

                        if result['status'] == 'success':
                            logger.info(f"[{request_id}] Successfully replaced meal {old_meal_id} with {new_meal_id} on {day} ({meal_type})")
                            replacement_found = True
                        else:
                            logger.error(f"[{request_id}] Failed to replace meal {old_meal_id} on {day} ({meal_type}): {result['message']}")
                            traceback.print_exc()
                    else:
                        logger.warning(f"[{request_id}] Meal '{new_meal.name}' failed comprehensive sanity check. Trying next possible replacement.")

                if not replacement_found:
                    logger.error(f"[{request_id}] Could not find a suitable replacement for meal ID {old_meal_id} on {day} ({meal_type}).")

    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"analyze_and_replace_meals", "traceback": traceback.format_exc()})
        return




def format_meal_plan(meal_plan_meals):
    return '\n'.join([
        f"{meal.meal.id}: {meal.meal.name} on {meal.day} ({meal.meal_type})" 
        for meal in meal_plan_meals
    ])

def get_possible_replacement_meals(user, meal_type, existing_meal_ids):
    # Collect regular dietary preferences
    regular_dietary_prefs = list(user.dietary_preferences.all())
    
    # Collect custom dietary preferences
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())
    
    # Build Q filters separately for regular and custom dietary preferences
    regular_prefs_filter = Q()
    for pref in regular_dietary_prefs:
        regular_prefs_filter |= Q(dietary_preferences=pref)
    
    custom_prefs_filter = Q()
    for custom_pref in custom_dietary_prefs:
        custom_prefs_filter |= Q(custom_dietary_preferences=custom_pref)
    
    # Combine both filters using OR
    combined_filter = regular_prefs_filter | custom_prefs_filter
    

    # Query meals that match the user's preferences and exclude existing meal IDs
    possible_meals = Meal.objects.filter(
        combined_filter,        # Combined dietary preferences
        meal_type=meal_type,
        creator_id=user.id
    ).exclude(
        id__in=existing_meal_ids
    ).distinct()

    return possible_meals

def find_existing_meal(
    user,
    meal_type: str,
    existing_meal_embeddings: List[List[float]], 
    existing_meal_names: Set[str],
    skipped_meal_ids: Set[int],
    min_similarity: float = 0.8,
    min_rating_threshold: int = 3,
    min_confidence: float = 0.7,
    max_meals_to_analyze: int = 5  # Limit API calls
) -> Optional[Meal]:
    # Convert existing meal names to lowercase for consistency
    existing_meal_names_lower = {name.lower() for name in existing_meal_names}

    # Identify meals with bad reviews from this user
    from reviews.models import Review
    from django.contrib.contenttypes.models import ContentType
    from meals.models import MealCompatibility
    meal_ct = ContentType.objects.get(app_label="meals", model="meal")
    badly_reviewed_meal_ids = Review.objects.filter(
        user=user,
        rating__lt=min_rating_threshold,
        content_type=meal_ct
    ).values_list('object_id', flat=True)

    mealplan_ct = ContentType.objects.get(app_label="meals", model="mealplan")
    badly_reviewed_mealplan_ids = Review.objects.filter(
        user=user,
        rating__lt=min_rating_threshold,
        content_type=mealplan_ct
    ).values_list('object_id', flat=True)

    meals_in_bad_plans = MealPlanMeal.objects.filter(
        meal_plan__in=badly_reviewed_mealplan_ids
    ).values_list('meal_id', flat=True).distinct()

    # Build Q filter for user's dietary prefs
    regular_dietary_prefs = list(user.dietary_preferences.all())
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())
    everything_pref = next((pref for pref in regular_dietary_prefs if pref.name == "Everything"), None)

    # Get potential meals
    if everything_pref and len(regular_dietary_prefs) == 1 and not custom_dietary_prefs:
        potential_meals = Meal.objects.filter(
            meal_type=meal_type,
            creator_id=user.id
        )
    else:
        # Build Q filter for dietary prefs
        regular_prefs_filter = Q()
        for pref in regular_dietary_prefs:
            regular_prefs_filter |= Q(dietary_preferences=pref)

        custom_prefs_filter = Q()
        for custom_pref in custom_dietary_prefs:
            custom_prefs_filter |= Q(custom_dietary_preferences=custom_pref)

        combined_filter = regular_prefs_filter | custom_prefs_filter

        potential_meals = Meal.objects.filter(
            combined_filter,
            meal_type=meal_type,
            creator_id=user.id
        )

    # Apply exclusions for non-allergy reasons first (we'll check allergies later)
    potential_meals = potential_meals.exclude(
        id__in=skipped_meal_ids
    ).exclude(
        name__in=existing_meal_names_lower
    ).exclude(
        id__in=badly_reviewed_meal_ids
    ).exclude(
        id__in=meals_in_bad_plans
    ).distinct()

    # Add chef-created meals if user has a postal code
    from local_chefs.models import ChefPostalCode
    from meals.models import ChefMealEvent
    from django.db.models import F
    
    user_postal_code = None
    if hasattr(user, 'address'):
        user_postal_code = user.address.input_postalcode
        user_country = user.address.country if hasattr(user.address, 'country') else None
    current_date = timezone.now().date()
        
    chef_meals = Meal.objects.none()
    chef_meal_ids = []
    if user_postal_code:
        # Find chefs serving user's postal code - FIXED to query by code field
        chef_ids = ChefPostalCode.objects.filter(
            postal_code__code=user_postal_code,
            postal_code__country=user_country
        ).values_list('chef_id', flat=True)
                
        # Find upcoming chef meal events
        upcoming_chef_events = ChefMealEvent.objects.filter(
            chef_id__in=chef_ids,
            meal__meal_type=meal_type,
            event_date__gte=current_date,
            status__in=['scheduled', 'open'],
            order_cutoff_time__gt=timezone.now(),
            orders_count__lt=F('max_orders')
        )

        chef_meal_ids = list(upcoming_chef_events.values_list('meal_id', flat=True).distinct())

        # Get chef meals with exclusions
        if chef_meal_ids:
            all_chef_meals = Meal.objects.filter(
                id__in=chef_meal_ids,
                meal_type=meal_type
            )

            # Apply the same dietary filters for chef meals (unless "Everything" preference)
            chef_meals = all_chef_meals
            if not (everything_pref and len(regular_dietary_prefs) == 1 and not custom_dietary_prefs):
                # Log each meal's dietary preferences before filtering
                for meal in all_chef_meals:
                    meal_prefs = [pref.name for pref in meal.dietary_preferences.all()]
                    meal_custom_prefs = [pref.custom_name for pref in meal.custom_dietary_preferences.all()]
                
                chef_meals = all_chef_meals.filter(combined_filter)
            
            # Check each meal to see why it might be excluded
            for meal in all_chef_meals:
                excluded = False
                reason = []
                
                if meal.name.lower() in existing_meal_names_lower:
                    excluded = True
                    reason.append(f"Name '{meal.name}' already in meal plan")
                
                if meal.id in badly_reviewed_meal_ids:
                    excluded = True
                    reason.append("Meal was poorly reviewed")
                
                if meal.id in meals_in_bad_plans:
                    excluded = True
                    reason.append("Meal was in a poorly reviewed meal plan")
                
                if meal.id in skipped_meal_ids:
                    excluded = True
                    reason.append("Meal was previously skipped")
                
            chef_meals = chef_meals.exclude(
                name__in=existing_meal_names_lower
            ).exclude(
                id__in=badly_reviewed_meal_ids
            ).exclude(
                id__in=meals_in_bad_plans
            ).exclude(
                id__in=skipped_meal_ids
            )
            
            # Keep chef meals separate so we can prioritize them in ordering later
            chef_meal_ids = list(chef_meals.values_list('id', flat=True))
            logger.info(f"Including {len(chef_meal_ids)} chef-created meals in recommendations for user {user.username}")

    # If no potential meals of any kind, return None
    if not potential_meals.exists() and len(chef_meal_ids) == 0:
        logger.info(f"No potential meals (including chef meals) found for user {user.username} and meal type {meal_type} after basic filtering.")
        return None

    # Get a list of meals for analysis, prioritizing chef meals first
    prioritized_meals = []
    if chef_meal_ids:
        prioritized_meals.extend(list(Meal.objects.filter(id__in=chef_meal_ids)))
    non_chef_qs = potential_meals.exclude(id__in=chef_meal_ids) if chef_meal_ids else potential_meals
    prioritized_meals.extend(list(non_chef_qs))
    meals_for_analysis = prioritized_meals
    
    # For embedding similarity check
    filtered_meals = []
    for meal in meals_for_analysis:
        if existing_meal_embeddings and meal.meal_embedding is not None:
            is_unique = True
            for existing_embedding in existing_meal_embeddings:
                try:
                    similarity = cosine_similarity(meal.meal_embedding, existing_embedding)
                    if similarity >= min_similarity:
                        is_unique = False
                        break
                except Exception:
                    is_unique = False
                    break
            if is_unique:
                filtered_meals.append(meal)
        else:
            filtered_meals.append(meal)
    
    # Limit the number of meals for AI analysis to avoid too many API calls
    filtered_meals = filtered_meals[:max_meals_to_analyze]
    
    # NEW: Check for allergens using our GPT-powered approach
    allergen_safe_meals = []
    for meal in filtered_meals:
        # Check if the meal is safe for the user's allergies
        is_safe, flagged_ingredients, substitutions = check_meal_for_allergens_gpt(meal, user)
        if is_safe:
            allergen_safe_meals.append(meal)
        else:
            logger.info(f"Meal '{meal.name}' excluded due to potential allergens: {', '.join(flagged_ingredients)}")
    
    # If no allergen-safe meals found
    if not allergen_safe_meals:
        logger.info(f"No allergen-safe meals found for user {user.username} after allergy checking.")
        return None
    
    # Continue with the rest of the compatibility checks on the allergen-safe meals
    for meal in allergen_safe_meals:
        try:
            is_compatible = True
            for pref in regular_dietary_prefs + custom_dietary_prefs:
                pref_name = pref.name if hasattr(pref, 'name') else pref.custom_name
                
                # First check if we have cached compatibility results
                cached_result = MealCompatibility.objects.filter(
                    meal=meal,
                    preference_name=pref_name
                ).first()
                
                if cached_result:
                    # Use cached results
                    result = {
                        "is_compatible": cached_result.is_compatible,
                        "confidence": cached_result.confidence,
                        "reasoning": cached_result.reasoning
                    }
                else:
                    # Perform new analysis
                    result = analyze_meal_compatibility(meal, pref_name)
                    
                    # Cache the results for future use
                    try:
                        MealCompatibility.objects.create(
                            meal=meal,
                            preference_name=pref_name,
                            is_compatible=result.get("is_compatible", False),
                            confidence=result.get("confidence", 0.0),
                            reasoning=result.get("reasoning", "")
                        )
                    except Exception as e:
                        # n8n traceback
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        requests.post(n8n_traceback_url, json={"error": str(e), "source":"analyze_meal_compatibility", "traceback": traceback.format_exc()})
                
                if not result.get("is_compatible", False) or result.get("confidence", 0.0) < min_confidence:
                    is_compatible = False
                    logger.info(f"Meal '{meal.name}' is not compatible with {pref_name} diet: {result.get('reasoning', 'No reason provided')}")
                    break
            
            if is_compatible:
                logger.info(f"Found compatible meal '{meal.name}' for user {user.username}")
                return meal
                
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"analyze_meal_compatibility", "traceback": traceback.format_exc()})
            continue
    
    # If no meal passes all checks
    return None

def guess_meal_ingredients_gpt(meal_name: str, meal_description: str) -> List[str]:
    """
    Use GPT to guess typical/hidden ingredients for a meal based on name & description.
    """
    prompt_messages = [
        {
            "role": "developer",
            "content": (
                """
                Predict the ingredients likely used in a given meal name and description.

                Use your culinary expertise to deduce both common and hidden ingredients that would typically be used in the preparation of the provided meal. Consider traditional recipes, regional variations, and modern twists.

                # Steps

                1. **Analyze the Meal Name**: Start by identifying keywords from the meal name that can hint at specific ingredients.
                2. **Evaluate the Description**: Look for descriptive words that suggest flavors, textures, or cooking methods which indicate certain ingredients.
                3. **Consider Recipe Traditions**: Think about traditional recipes for the dish from different regions or variations that might incorporate unique ingredients.
                4. **Include Common Ingredients**: Identify staple ingredients generally found in the dish based on your culinary knowledge.
                5. **Suggest Hidden Ingredients**: Consider any unique or less obvious ingredients that could enhance the meal's flavor profile.

                # Output Format

                Your response should conform to the following JSON schema:

                ```json
                {
                "likely_ingredients": {
                    "type": "array",
                    "items": {"type": "string"}
                }
                }
                ```

                # Examples

                ### Example 1
                **Input**
                - Meal Name: "Spaghetti Carbonara"
                - Description: "A classic Italian pasta dish made with eggs, cheese, pancetta, and pepper."

                **Output**
                ```json
                {
                "likely_ingredients": ["spaghetti", "eggs", "Pecorino Romano cheese", "pancetta", "black pepper", "garlic", "olive oil"]
                }
                ```

                ### Example 2
                **Input**
                - Meal Name: "Thai Green Curry"
                - Description: "A spicy, aromatic dish with a coconut milk base and a vibrant green hue from green curry paste."

                **Output**
                ```json
                {
                "likely_ingredients": ["coconut milk", "green curry paste", "chicken", "bamboo shoots", "Thai basil", "fish sauce", "lemongrass", "galangal", "kaffir lime leaves"]
                }
                ```

                # Notes

                - Consider cross-referencing with common ingredients used in well-known variations of the dish.
                - Balance the list of ingredients between universally recognized essentials and unique, chef-inspired inclusions.
                """
            )
        },
        {
            "role": "user",
            "content": (
                f"Meal name: {meal_name}\n"
                f"Description: {meal_description}\n\n"
                "List typical or hidden ingredients that might appear, e.g. sauces, marinades, "
                "or common garnishes."
            )
        }
    ]
    
    try:
        groq_client = _get_groq_client()
        if groq_client:
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.guess_meal_ingredients_gpt',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": prompt_messages[0]["content"]},
                    {"role": "user", "content": prompt_messages[1]["content"]},
                ],
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "likely_ingredients",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "likely_ingredients": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["likely_ingredients"],
                            "additionalProperties": False
                        },
                    },
                },
            )
            raw = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=prompt_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "likely_ingredients",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "likely_ingredients": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["likely_ingredients"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                }
            )
            raw = response.output_text
        data = json.loads(raw)
        return data.get("likely_ingredients", [])
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"guess_meal_ingredients_gpt", "traceback": traceback.format_exc()})
        return []

def is_chef_meal(meal):
    """
    Determine if a meal is created by a chef (vs. system-generated).
    
    Args:
        meal: The Meal object to check
        
    Returns:
        bool: True if the meal is chef-created, False otherwise
    """
    from meals.models import ChefMealEvent
    
    # Check if the meal is linked to any chef meal events
    return ChefMealEvent.objects.filter(meal=meal).exists()

def check_meal_for_allergens_gpt(meal, user) -> Tuple[bool, List[str], Dict[str, List[str]]]:
    """
    Checks if a meal is safe for a user with allergies and suggests substitutions for flagged ingredients.
    
    Args:
        meal: The Meal object to check
        user: The CustomUser object with allergies
        
    Returns:
        Tuple[bool, List[str], Dict[str, List[str]]]: (is_safe, [flagged_ingredients], {ingredient: [substitutions]})
        - is_safe: True if the meal is safe, False if it likely contains an allergen
        - flagged_ingredients: List of ingredients that were flagged as potential allergens
        - substitutions: Dictionary mapping flagged ingredients to lists of suggested substitutions
    """
    from meals.models import MealAllergenSafety
    from django.utils import timezone
    from datetime import timedelta
    
    # Skip the check if user has no allergies
    user_allergies = list(set((user.allergies or []) + (user.custom_allergies or [])))
    if not user_allergies:
        # No allergies to check against
        return True, [], {}
    
    # Check if we have a recent cached result (within 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    cached_check = MealAllergenSafety.objects.filter(
        meal=meal, 
        user=user,
        last_checked__gt=seven_days_ago
    ).first()
    
    # If we have a cached result, use it
    if cached_check:
        logger.info(f"Using cached allergy check for meal '{meal.name}' and user '{user.username}'")
        # Include substitutions in return if they exist
        substitutions = cached_check.substitutions or {}
        return cached_check.is_safe, cached_check.flagged_ingredients, substitutions
    
    logger.info(f"Performing new allergy check for meal '{meal.name}' and user '{user.username}'")
    
    # No cached result, perform the check
    allergy_list_str = ", ".join(user_allergies)

    # Gather chef-listed ingredients
    chef_ingredients = []
    for dish in meal.dishes.all():
        chef_ingredients.extend([ing.name.lower() for ing in dish.ingredients.all()])
    
    # Ask GPT to guess hidden ingredients
    guessed_ingredients = guess_meal_ingredients_gpt(meal.name, meal.description or "")
    guessed_ingredients = [ing.lower() for ing in guessed_ingredients]
    
    # Combine them
    combined_ingredients = list(set(chef_ingredients + guessed_ingredients))
    
    if not combined_ingredients:
        logger.warning(f"No ingredients found for meal '{meal.name}'. Cannot properly check for allergens.")
        # Save this result to avoid repeated checks of empty ingredient lists
        try:
            MealAllergenSafety.objects.update_or_create(
                meal=meal,
                user=user,
                defaults={
                    'is_safe': False,
                    'flagged_ingredients': ["No ingredients found to analyze"],
                    'reasoning': "Cannot determine safety without ingredients",
                    'substitutions': {}
                }
            )
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
        
        return False, ["No ingredients found to analyze"], {}
    
    # Check for obvious matches first (faster than API calls)
    flagged_ingredients = []
    for ingredient in combined_ingredients:
        for allergy in user_allergies:
            # Direct match - ingredient name contains allergy name
            if allergy.lower() in ingredient.lower():
                flagged_ingredients.append(ingredient)
                break
    
    # Check if this is a chef meal - if so, we can't offer substitutions
    is_chef = is_chef_meal(meal)
    
    if flagged_ingredients:
        # For direct matches on regular meals, ask GPT for substitution suggestions
        # For chef meals, we don't offer substitutions
        substitutions = {}
        if not is_chef:
            try:
                substitutions = get_substitution_suggestions(flagged_ingredients, user_allergies, meal.name)
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
        else:
            logger.info(f"Meal '{meal.name}' is chef-created, not offering substitutions")
            
        reasoning = f"Direct ingredient match: {', '.join(flagged_ingredients)} contains user allergens: {allergy_list_str}"
        if is_chef:
            reasoning += " (Chef-created meal, no substitutions available)"
            
        try:
            MealAllergenSafety.objects.update_or_create(
                meal=meal,
                user=user,
                defaults={
                    'is_safe': False,
                    'flagged_ingredients': flagged_ingredients,
                    'reasoning': reasoning,
                    'substitutions': substitutions
                }
            )
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
            
        return False, flagged_ingredients, substitutions
    
    # No obvious matches, now check with GPT for more sophisticated analysis with substitutions
    prompt_messages = [
        {
            "role": "developer",
            "content": (
                """
                Analyze each ingredient for potential allergens based on the user's dietary restrictions. For any ingredients that could contain or be derived from allergens, suggest 1-2 substitutions that maintain the dish's flavor profile and culinary function.

                Include reasoning to explain why ingredients are flagged and why specific substitutions are suggested.

                # Steps

                1. **Identify Allergens**: Determine the allergens the user needs to avoid.
                2. **Analyze Ingredients**: Examine each ingredient to assess whether it contains or is derived from any of the allergies.
                3. **Reasoning**: Explain why the ingredient is considered safe or unsafe.
                4. **Substitution Suggestion**: For flagged ingredients, recommend 1-2 substitutions that ensure safety and maintain the dish's flavor and function.

                # Output Format

                Use the following JSON schema for output:

                - `is_safe`: Boolean indicating if all ingredients are safe.
                - `flagged_ingredients`: List of ingredients that may contain allergens.
                - `substitutions`: Object where each flagged ingredient maps to an array of potential substitutions.
                - `reasoning`: String explaining the analysis process.

                Example:

                ```json
                {
                "is_safe": true,
                "flagged_ingredients": ["ingredient1", "ingredient2"],
                "substitutions": {
                    "ingredient1": ["substitute1a", "substitute1b"],
                    "ingredient2": ["substitute2a"]
                },
                "reasoning": "After examining the ingredients, ingredient1 contains a common allergen, and ingredient2 is derived from another allergen. Suitable substitutions for ingredient1 are substitute1a and substitute1b, while substitute2a is recommended for ingredient2."
                }
                ```

                # Examples

                **Input:**
                User is allergic to nuts and dairy.

                **Output:**
                ```json
                {
                "is_safe": false,
                "flagged_ingredients": ["almonds", "milk"],
                "substitutions": {
                    "almonds": ["pumpkin seeds", "sunflower seeds"],
                    "milk": ["almond milk", "oat milk"]
                },
                "reasoning": "Almonds are a type of tree nut, which the user is allergic to. Milk is a dairy product. Substitute almond with pumpkin seeds or sunflower seeds, and replace milk with almond milk or oat milk to maintain culinary function and flavor."
                }
                ```

                # Notes

                - Always consider maintaining the original dish's flavor profile and culinary functions when suggesting substitutions.
                - Ensure that all suggested substitutes are free from the user's identified allergens.
                - Clarify any assumptions made regarding the user's dietary restrictions or specific ingredients.
                """
            )
        },
        {
            "role": "user",
            "content": (
                f"The user has these allergies: {allergy_list_str}.\n\n"
                f"Ingredients to check: {', '.join(combined_ingredients)}.\n\n"
                f"Meal name: {meal.name}\n"
                f"Description: {meal.description or 'Not provided'}\n\n"
                "For each ingredient, determine if it could potentially contain or be derived from "
                "any of the user's allergens. For any flagged ingredients, suggest 1-2 substitutions that are "
                "safe alternatives and would maintain the dish's flavor profile and culinary function."
            )
        }
    ]
    
    try:
        groq_client = _get_groq_client()
        schema = {
            "type": "object",
            "properties": {
                "is_safe": {"type": "boolean"},
                "flagged_ingredients": {"type": "array", "items": {"type": "string"}},
                "substitutions": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "reasoning": {"type": "string"}
            },
            "required": ["is_safe", "flagged_ingredients", "reasoning"],
            "additionalProperties": False
        }
        if groq_client:
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.check_meal_for_allergens_gpt',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": prompt_messages[0]["content"]},
                    {"role": "user", "content": prompt_messages[1]["content"]},
                ],
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "allergen_analysis",
                        "schema": schema,
                    },
                },
            )
            raw = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=prompt_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "allergen_analysis",
                        "schema": schema,
                        "strict": True
                    }
                }
            )
            raw = response.output_text
        data = json.loads(raw)
        is_safe = data.get("is_safe", False)
        gpt_flagged = data.get("flagged_ingredients", [])
        
        # For chef meals, don't offer substitutions regardless of what GPT suggests
        substitutions = {}
        if not is_chef and not is_safe:
            substitutions = data.get("substitutions", {})
            
        reasoning = data.get("reasoning", "")
        
        # For chef meals, add a note about not offering substitutions
        if is_chef and not is_safe:
            reasoning += " (Chef-created meal, no substitutions available)"
        
        if not is_safe:
            logger.info(f"Meal '{meal.name}' flagged for potential allergens: {', '.join(gpt_flagged)}. Reasoning: {reasoning}")
            if not is_chef and substitutions:
                logger.info(f"Suggested substitutions: {substitutions}")
            elif is_chef:
                logger.info(f"Meal is chef-created, no substitutions offered")
        
        # Cache the result
        try:
            MealAllergenSafety.objects.update_or_create(
                meal=meal,
                user=user,
                defaults={
                    'is_safe': is_safe,
                    'flagged_ingredients': gpt_flagged,
                    'reasoning': reasoning,
                    'substitutions': substitutions
                }
            )
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
            logger.error(f"Error caching allergy safety result: {e}")
        
        return is_safe, gpt_flagged, substitutions
    
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
        logger.error(f"Error in GPT allergen check for meal '{meal.name}': {e}")
        
        # Cache the error result
        try:
            MealAllergenSafety.objects.update_or_create(
                meal=meal,
                user=user,
                defaults={
                    'is_safe': False,
                    'flagged_ingredients': ["Error during analysis"],
                    'reasoning': f"Error during GPT analysis: {str(e)}",
                    'substitutions': {}
                }
            )
        except Exception as cache_error:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(cache_error), "source":"check_meal_for_allergens_gpt", "traceback": traceback.format_exc()})
            logger.error(f"Error caching allergy safety error result: {cache_error}")
        
        # If API call fails, fall back to being cautious - flag as unsafe
        return False, ["Error during analysis"], {}

def get_substitution_suggestions(flagged_ingredients, user_allergies, meal_name):
    """
    Get substitution suggestions for flagged ingredients based on user allergies.
    
    Args:
        flagged_ingredients: List of ingredients that were flagged as potential allergens
        user_allergies: List of user's allergies
        meal_name: Name of the meal for context
    
    Returns:
        Dict with a "substitutions" key containing a list of mappings. Each
        mapping has an "ingredient" name and a list of "alternatives".
    """
    from meals.pydantic_models import IngredientSubstitutions
    
    try:
        prompt_messages = [
            {
                "role": "developer",
                "content": (
                    """
                    Provide substitution suggestions for flagged ingredients based on user allergies.

                    You are a culinary expert specialized in ingredient substitutions for those with allergies or dietary restrictions. Your task is to suggest safe, delicious alternatives that maintain the dish's flavor profile and culinary function.

                    # Steps

                    1. Identify each ingredient in the `flagged_ingredients` list that matches the user's allergies from the `user_allergies` list.
                    2. For each flagged ingredient:
                    - Understand the ingredient's role in the meal (e.g., flavor, texture, function).
                    - Suggest alternatives that are not in the `user_allergies` list and match the ingredient's role.
                    - Ensure the substitution aligns with the culinary profile of the `meal_name`.
                    3. Construct and return the recommendations as a JSON object containing a `substitutions` array. Each array item should include the `ingredient` name and a list of safe `alternatives`.

                    # Output Format

                    Return a JSON object with a single `substitutions` array. Each element should be an object with `ingredient` and `alternatives` fields.


                    # Examples

                    ### Example Input
                    - flagged_ingredients: ["milk", "peanut", "egg"]
                    - user_allergies: ["dairy", "peanut"]
                    - meal_name: "Vegan Pancakes"

                    ### Example Output
                    ```json
                    {
                        "substitutions": [
                            {"ingredient": "milk", "alternatives": ["almond milk", "coconut milk", "soy milk"]},
                            {"ingredient": "peanut", "alternatives": ["sunflower seed butter", "almond butter"]}
                        ]
                    }
                    ```

                    # Notes

                    - Consider the common culinary function of each ingredient such as binding, leavening, or flavoring.
                    - It's important to tailor your substitutes to the type of meal. For example, if the meal is a dessert, sweeter alternatives might be more appropriate.
                    - Always ensure substitutes are safe given the listed user allergies.
                    """
                )
            },
            {
                "role": "user",
                "content": (
                    f"For the dish '{meal_name}', I need substitutions for these flagged ingredients: "
                    f"{', '.join(flagged_ingredients)}.\n\n"
                    f"The user has these allergies/restrictions: {', '.join(user_allergies)}.\n\n"
                    "For each flagged ingredient, suggest 1-2 substitutions that are:\n"
                    "1. Safe for the user's allergies/restrictions\n"
                    "2. Maintain the dish's flavor profile\n"
                    "3. Serve the same culinary function (texture, binding, etc.)\n\n"
                    "Return a JSON object with a `substitutions` array where each item lists an `ingredient` and its `alternatives`."
                )
            }
        ]
        
        groq_client = _get_groq_client()
        if groq_client:
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.get_substitution_suggestions',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": prompt_messages[0]["content"]},
                    {"role": "user", "content": prompt_messages[1]["content"]},
                ],
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "ingredient_substitutions",
                        "schema": IngredientSubstitutions.model_json_schema(),
                    },
                },
            )
            raw = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=prompt_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "ingredient_substitutions",
                        "schema": IngredientSubstitutions.model_json_schema()
                    }
                }
            )
            raw = response.output_text
        
        # Parse response and convert to a simple mapping
        result = json.loads(raw)
        subs = {}
        for item in result.get("substitutions", []):
            ingredient = item.get("ingredient")
            alternatives = item.get("alternatives", [])
            if ingredient:
                subs[ingredient] = alternatives
        return subs
    except Exception as e:
        logger.error(f"Error generating substitution suggestions: {e}")
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"get_substitution_suggestions", "traceback": traceback.format_exc()})
        return {}

def get_similar_meal(user_id, name, description, meal_type):
    """
    Retrieves an existing meal similar to the provided details.
    """
    # Get Creator
    creator = CustomUser.objects.get(id=user_id)
    
    # Get all potential matches first (without allergen filtering)
    similar_meals = Meal.objects.filter(
        creator=creator,
        meal_type=meal_type
    ).exclude(
        name=name  # Exclude the current meal by name
    ).distinct()
    
    similar_meal_count = similar_meals.count()
    logger.info(f"Found {similar_meal_count} potential matches for meal type {meal_type} before allergen filtering")
    
    # Filter meals for allergens
    safe_meals = []
    for meal in similar_meals:
        is_safe, flagged_ingredients, substitutions = check_meal_for_allergens_gpt(meal, creator)
        if is_safe:
            safe_meals.append(meal)
        else:
            logger.info(f"Excluding meal '{meal.name}' due to potential allergens: {', '.join(flagged_ingredients)}")
    
    logger.info(f"After allergen filtering, {len(safe_meals)} safe meals remain")
    
    # No safe meals found
    if not safe_meals:
        return None
    
    # Compute embedding for the current meal's description
    current_embedding = get_embedding(description)  # 1D array
    
    # Find the most similar meal by embedding
    best_match = None
    highest_similarity = 0
    
    for meal in safe_meals:
        if not meal.meal_embedding:
            continue  # Skip meals without embeddings
        
        # Compute cosine similarity
        similarity = cosine_similarity(current_embedding, meal.meal_embedding)
        
        if similarity >= 0.8 and similarity > highest_similarity:  # Threshold for similarity
            highest_similarity = similarity
            best_match = meal
    
    return best_match  # Return the most similar meal or None

def get_user_allergies(user):
    """
    Retrieve a list of all allergies for a user by combining primary and custom allergies.

    Args:
        user (CustomUser): The user instance.

    Returns:
        List[str]: A list of cleaned allergy names in lowercase.
    """
    combined_allergies = set((user.allergies or []) + (user.custom_allergies or []))
    all_allergies = [allergy.lower().strip() for allergy in combined_allergies]

    return all_allergies

def perform_comprehensive_sanity_check(meal, user, request_id=None):
    """
    Performs a comprehensive check to determine if a meal is suitable for a user.
    This combines allergy safety checks and dietary preference compatibility.
    
    Args:
        meal: The Meal object to check
        user: The CustomUser object
        request_id: Optional request ID for logging
        
    Returns:
        bool: True if the meal is suitable, False otherwise
    """
    from meals.models import MealAllergenSafety, MealCompatibility
    from django.utils import timezone
    from datetime import timedelta
    
    log_prefix = f"[{request_id}] " if request_id else ""
    
    # Check for cached comprehensive result
    # First, check if the meal has already been determined to be unsafe due to allergens
    seven_days_ago = timezone.now() - timedelta(days=7)
    cached_allergen_check = MealAllergenSafety.objects.filter(
        meal=meal, 
        user=user,
        last_checked__gt=seven_days_ago
    ).first()
    
    # If we have a cached allergen check and it failed, check if it has substitutions
    if cached_allergen_check and not cached_allergen_check.is_safe:
        if cached_allergen_check.substitutions and len(cached_allergen_check.substitutions) > 0:
            # Check if this meal is already a modified/substitution variant based on name
            is_modified_meal = any(indicator in meal.name.lower() for indicator in ['modified', 'adapted', 'substituted', 'allergen-free', '(modified)'])
            if is_modified_meal:
                logger.info(f"{log_prefix}Meal '{meal.name}' appears to be already modified, considering it safe.")
                return True
            else:
                logger.info(f"{log_prefix}Meal '{meal.name}' is unsafe for user {user.username} but has substitutions available.")
                # Continue to preference check - we'll handle substitutions when actually adding the meal
        else:
            logger.info(f"{log_prefix}Using cached allergen check: Meal '{meal.name}' is unsafe for user {user.username} due to allergens and has no substitutions.")
            return False
    
    # Check for cached dietary preference compatibility results
    # Get all user's preferences
    regular_dietary_prefs = list(user.dietary_preferences.all())
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())
    all_prefs = regular_dietary_prefs + custom_dietary_prefs
    
    # Check if we have any incompatible dietary preferences cached
    for pref in all_prefs:
        pref_name = pref.name if hasattr(pref, 'name') else pref.custom_name
        
        cached_pref_check = MealCompatibility.objects.filter(
            meal=meal,
            preference_name=pref_name
        ).first()
        
        if cached_pref_check and (not cached_pref_check.is_compatible or cached_pref_check.confidence < 0.7):
            logger.info(f"{log_prefix}Using cached preference check: Meal '{meal.name}' is incompatible with {pref_name} for user {user.username}.")
            return False
    
    # If we have a cached positive allergen check, we can skip that part
    if cached_allergen_check and cached_allergen_check.is_safe:
        logger.info(f"{log_prefix}Using cached allergen check: Meal '{meal.name}' is safe for user {user.username}.")
        # Skip to dietary preference check
        if not perform_openai_sanity_check(meal, user):
            logger.info(f"{log_prefix}Meal '{meal.name}' failed preference sanity check.")
            return False
        logger.info(f"{log_prefix}Meal '{meal.name}' passed all sanity checks for user {user.username}")
        return True
    
    # If no conclusive cached results, perform full checks
    # Step 1: Check for allergies first (fastest rejection)
    is_safe, flagged_ingredients, substitutions = check_meal_for_allergens_gpt(meal, user)
    if not is_safe:
        # With our new approach, we'll mark meals with substitutions as potentially usable
        if substitutions and len(substitutions) > 0:
            logger.info(f"{log_prefix}Meal '{meal.name}' failed allergen safety check but has substitutions available.")
            # Fall through to preference check
        else:
            logger.info(f"{log_prefix}Meal '{meal.name}' failed allergen safety check with no substitutions. Flagged ingredients: {', '.join(flagged_ingredients)}")
            return False
    
    # Step 2: Check if meal passes the existing sanity check for user preferences
    if not perform_openai_sanity_check(meal, user):
        logger.info(f"{log_prefix}Meal '{meal.name}' failed preference sanity check.")
        return False
    
    # Both checks passed (or allergen check failed but substitutions are available)
    logger.info(f"{log_prefix}Meal '{meal.name}' passed all sanity checks for user {user.username}")
    return True

def apply_substitutions_to_meal(meal, substitutions, user):
    """
    Create a modified version of a meal with ingredient substitutions.
    
    Args:
        meal: The original Meal object
        substitutions: Dictionary mapping flagged ingredients to lists of substitution suggestions
        user: The user for whom the substitutions are being made
        
    Returns:
        Meal: A new or modified Meal object with substitutions applied, or None if failed
    """
    from django.db import transaction
    
    # Validate inputs
    if not meal or not user:
        logger.error("Invalid meal or user provided to apply_substitutions_to_meal")
        return None
    
    # Check if this is a chef meal - if so, we can't modify it
    if is_chef_meal(meal):
        logger.warning(f"Cannot apply substitutions to chef-created meal '{meal.name}' for user {user.username}")
        return None
    
    # Check if user is a chef to determine what type of substitution we can create
    user_is_chef = hasattr(user, 'chef') and user.chef
    if user_is_chef:
        logger.info(f"User {user.username} is a chef - will create new dishes with ingredient substitutions")
    else:
        logger.info(f"User {user.username} is not a chef - will create meal with substitution notes only")
    
    # Validate that the meal has dishes to work with
    if not meal.dishes.exists():
        logger.warning(f"Cannot apply substitutions to meal '{meal.name}' - no dishes found")
        return None
    
    # Validate substitutions parameter
    if not substitutions or not isinstance(substitutions, dict):
        logger.warning(f"Cannot apply substitutions to meal '{meal.name}' - invalid substitutions provided")
        return None
    
    logger.info(f"Applying substitutions to meal '{meal.name}' for user {user.username}")
    
    # Gather original ingredients with their dishes for reference
    original_ingredients = {}
    for dish in meal.dishes.all():
        for ingredient in dish.ingredients.all():
            original_ingredients[ingredient.name.lower()] = {
                'dish': dish,
                'ingredient': ingredient
            }
    
    # Validate that we actually have ingredients to substitute
    if not original_ingredients:
        logger.warning(f"Cannot apply substitutions to meal '{meal.name}' - no ingredients found in dishes")
        return None
    
    # Generate a modified recipe and instructions with substitutions
    try:
        substitutions_str = json.dumps(substitutions)
        original_ingredients_str = ', '.join(original_ingredients.keys())
        
        prompt_messages = [
            {
                "role": "developer",
                "content": (
                    """
                    Adapt a recipe to accommodate specific ingredient substitutions while maintaining the dish's flavor, texture, and culinary integrity. As a culinary expert, modify the recipe to ensure that the changes align with the desired culinary standards.

                    Utilize the following schema to structure your output:

                    - **modified_name**: The new name of the dish reflecting the substitutions.
                    - **modified_description**: A brief description of the dish with the new ingredients.
                    - **modified_instructions**: Detailed cooking instructions for the modified dish.
                    - **ingredient_changes**: A list detailing the original and substitute ingredients used in the recipe.

                    # Output Format

                    The output should be formatted as a JSON object following this structure:

                    ```json
                    {
                    "modified_name": "string",
                    "modified_description": "string",
                    "modified_instructions": "string",
                    "ingredient_changes": [
                        {
                        "original": "string",
                        "substitute": "string"
                        }
                        // Add more objects as necessary for additional substitutions
                    ]
                    }
                    ```

                    # Steps

                    1. Identify the ingredients that need to be substituted.
                    2. Choose appropriate substitute ingredients that maintain flavor, texture, and culinary integrity.
                    3. Modify the recipe instructions to incorporate the new ingredients effectively.
                    4. Update the dish's name and description to reflect the changes.
                    5. Document each substitution clearly.

                    # Examples

                    **Example Start**

                    **Input**: A recipe for 'Classic Caesar Salad' with a request to substitute anchovies and croutons.

                    **Output**:

                    ```json
                    {
                    "modified_name": "Vegan Caesar Salad",
                    "modified_description": "A plant-based twist on the classic Caesar salad, featuring savory toasted almonds and smoky coconut flakes instead of anchovies.",
                    "modified_instructions": "Toss lettuce with dressing made of vegan ingredients and top with toasted almonds. Sprinkle with smoky coconut flakes instead of anchovies.",
                    "ingredient_changes": [
                        {
                        "original": "anchovies",
                        "substitute": "smoky coconut flakes"
                        },
                        {
                        "original": "croutons",
                        "substitute": "toasted almonds"
                        }
                    ]
                    }
                    ```

                    **Example End** 

                    (Real examples should include more detailed instructions and substitutions where necessary.)

                    # Notes

                    - Ensure substitutions are suitable for dietary needs if specified.
                    - Maintain the balance between the original recipe and the target dietary requirements or preferences.
                    - Be mindful of dietary restrictions, allergies, and preferences when suggesting substitutions.
                    """
                )
            },
            {
                "role": "user",
                "content": (
                    f"I need to modify this meal:\n"
                    f"Name: {meal.name}\n"
                    f"Description: {meal.description or 'Not provided'}\n"
                    f"Original ingredients: {original_ingredients_str}\n\n"
                    f"The following substitutions need to be made: {substitutions_str}\n\n"
                    "Please provide:\n"
                    "1. A modified name for the meal that indicates it's been adapted (e.g., 'Gluten-Free Pasta')\n"
                    "2. Updated instructions that explain how to use the substitutions\n"
                    "3. Any adjustments to cooking times or methods needed for the substitutions\n"
                    "4. A complete list of ingredients with the substitutions applied"
                )
            }
        ]
        
        groq_client = _get_groq_client()
        if groq_client:
            raw_create = getattr(getattr(groq_client.chat, 'completions', None), 'with_raw_response', None)
            if raw_create:
                raw_create = groq_client.chat.completions.with_raw_response.create
            groq_resp = groq_call_with_retry(
                raw_create_fn=raw_create,
                create_fn=groq_client.chat.completions.create,
                desc='meal_plan_service.apply_substitutions_to_meal',
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": prompt_messages[0]["content"]},
                    {"role": "user", "content": prompt_messages[1]["content"]},
                ],
                temperature=0.3,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "modified_meal",
                        "schema": ModifiedMealSchema.model_json_schema(),
                    },
                },
            )
            raw = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",  # Using more capable model for recipe adaptation
                input=prompt_messages,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "modified_meal",
                        "schema": ModifiedMealSchema.model_json_schema(),
                        "strict": True
                    }
                }
            )
            raw = response.output_text
        
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
            return None
        
        # Validate that required fields are present
        required_fields = ["modified_name", "modified_description", "modified_instructions", "ingredient_changes"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"OpenAI response missing required fields {missing_fields} for meal '{meal.name}'")
            return None
        
        # Create a new meal as a variant of the original
        with transaction.atomic():
            # Create new meal (mark as modified in the name if not already indicated)
            modified_name = data["modified_name"].strip() if data["modified_name"] else f"{meal.name} (Modified)"
            if not any(indicator in modified_name.lower() for indicator in ['modified', 'adapted', 'substituted', 'allergen-free']):
                modified_name = f"{modified_name} (Modified)"
            
            # Ensure the name is unique for this user to avoid constraint violations
            base_name = modified_name
            counter = 1
            while Meal.objects.filter(name=modified_name, creator=user).exists():
                modified_name = f"{base_name} ({counter})"
                counter += 1
            
            # Safely build description with fallbacks
            description_parts = []
            if data.get('modified_description'):
                description_parts.append(data['modified_description'].strip())
            if data.get('modified_instructions'):
                description_parts.append(f"Instructions: {data['modified_instructions'].strip()}")
            
            description = '\n\n'.join(description_parts) if description_parts else f"Modified version of {meal.name}"
            
            modified_meal = Meal.objects.create(
                name=modified_name,
                description=description,
                meal_type=meal.meal_type,
                creator=user
            )
            
            # For regular customers, we can't create new dishes (they require a chef)
            # Instead, we'll create a simplified meal that documents the substitutions
            # without creating new dish/ingredient database objects
            
            if user_is_chef:
                # User is a chef - they can create modified dishes
                for original_dish in meal.dishes.all():
                    # Use the user's chef profile for new dishes
                    dish_chef = user.chef
                    
                    # Ensure unique dish name for this chef
                    base_dish_name = f"{original_dish.name} (Modified)"
                    dish_name = base_dish_name
                    counter = 1
                    while Dish.objects.filter(name=dish_name, chef=dish_chef).exists():
                        dish_name = f"{base_dish_name} ({counter})"
                        counter += 1
                    
                    new_dish = Dish.objects.create(
                        name=dish_name,
                        chef=dish_chef
                    )
                    
                    # Get substitution mapping for easy lookup
                    substitution_map = {}
                    try:
                        for change in data["ingredient_changes"]:
                            if isinstance(change, dict) and "original" in change and "substitute" in change:
                                substitution_map[change["original"].lower()] = change["substitute"]
                            else:
                                logger.warning(f"Invalid ingredient change format: {change}")
                    except (KeyError, TypeError) as e:
                        # n8n traceback
                        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                        requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
                        logger.error(f"Error processing ingredient changes: {e}")
                        continue  # Skip this dish if ingredient changes are malformed
                    
                    # For substituted ingredients, create new ones or find existing ones
                    ingredients_added = 0
                    for original_ingredient in original_dish.ingredients.all():
                        ing_name = original_ingredient.name.lower()
                        if ing_name in substitution_map:
                            # Create or find substitution ingredient
                            substitute_name = substitution_map[ing_name]
                            try:
                                substitute_ingredient, created = Ingredient.objects.get_or_create(
                                    name=substitute_name,
                                    chef=dish_chef,
                                    defaults={
                                        'calories': original_ingredient.calories,
                                        'fat': original_ingredient.fat,
                                        'carbohydrates': original_ingredient.carbohydrates,
                                        'protein': original_ingredient.protein,
                                        'is_custom': True
                                    }
                                )
                                new_dish.ingredients.add(substitute_ingredient)
                                ingredients_added += 1
                            except Exception as e:
                                # n8n traceback
                                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                                requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
                                # Fall back to using the original ingredient
                                new_dish.ingredients.add(original_ingredient)
                                ingredients_added += 1
                        else:
                            # Keep original ingredient
                            new_dish.ingredients.add(original_ingredient)
                            ingredients_added += 1
                    
                    # Verify the dish has ingredients before adding to meal
                    if ingredients_added == 0:
                        logger.warning(f"Dish '{new_dish.name}' has no ingredients - removing it")
                        new_dish.delete()
                        continue
                    
                    # Add the new dish to the modified meal
                    modified_meal.dishes.add(new_dish)
            else:
                # User is not a chef - we can't create new dishes/ingredients
                # Instead, keep original dishes but document substitutions in the meal description
                logger.info(f"User {user.username} is not a chef - creating simplified substituted meal without new dishes")
                
                # Copy original dishes to the modified meal (without changes)
                for original_dish in meal.dishes.all():
                    modified_meal.dishes.add(original_dish)
                
                # Document the substitutions in the meal description
                substitution_notes = []
                try:
                    for change in data["ingredient_changes"]:
                        if isinstance(change, dict) and "original" in change and "substitute" in change:
                            substitution_notes.append(f"• Replace {change['original']} with {change['substitute']}")
                        else:
                            logger.warning(f"Invalid ingredient change format: {change}")
                except (KeyError, TypeError) as e:
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
                    logger.error(f"Error processing ingredient changes for notes: {e}")
                
                if substitution_notes:
                    substitution_text = f"\n\n**INGREDIENT SUBSTITUTIONS:**\n" + "\n".join(substitution_notes)
                    modified_meal.description += substitution_text
            
            # Verify the modified meal has at least one dish
            if not modified_meal.dishes.exists():
                logger.error(f"Modified meal '{modified_meal.name}' has no dishes - cannot create meal")
                modified_meal.delete()
                return None
            
            # Copy dietary preferences
            for pref in meal.dietary_preferences.all():
                modified_meal.dietary_preferences.add(pref)
            
            # Copy custom dietary preferences
            for custom_pref in meal.custom_dietary_preferences.all():
                modified_meal.custom_dietary_preferences.add(custom_pref)
            
            # Generate embedding for the modified meal
            try:
                from meals.meal_embedding import prepare_meal_representation
                
                # Create a proper meal representation for embedding
                meal_representation = prepare_meal_representation(modified_meal)
                embedding = get_embedding(meal_representation)
                
                if embedding and isinstance(embedding, list) and len(embedding) == 1536:
                    modified_meal.meal_embedding = embedding
                    logger.info(f"Successfully generated embedding for modified meal '{modified_meal.name}'")
                else:
                    logger.warning(f"Failed to generate valid embedding for modified meal '{modified_meal.name}'. Will schedule for batch processing.")
                    # Let the batch processing handle it later
            except ImportError:
                logger.info(f"Meal embedding module not available - embedding will be generated by batch process")
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
                logger.error(f"Error generating embedding for modified meal '{modified_meal.name}': {e}")
                # Continue without embedding - it will be generated by the batch process
            
            modified_meal.save()
            
            logger.info(f"Successfully created modified meal '{modified_meal.name}' from '{meal.name}'")
            return modified_meal
            
    except json.JSONDecodeError as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
        return None
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_substitutions_to_meal", "traceback": traceback.format_exc()})
        return None

def regenerate_replaced_meal(original_meal_id, user, meal_type, meal_plan, request_id=None):
    """
    Attempts to regenerate a meal that was replaced with a better one.
    """
    try:
        original_meal = Meal.objects.get(id=original_meal_id)
        
        # Generate a new meal
        result = generate_and_create_meal(
            user=user,
            meal_plan=meal_plan,
            meal_type=meal_type,
            existing_meal_names=[],  # Empty to avoid duplicate validation
            existing_meal_embeddings=[],  # Empty to avoid duplicate validation
            user_id=user.id,
            day_name=None,  # Not needed for regeneration
            request_id=request_id,
            allow_cached=False  # Ensure fresh generation
        )
        
        if result['status'] == 'success':
            # No approval flow — nothing to notify here
            return True
        else:
            logger.error(f"[{request_id}] Failed to regenerate meal for {original_meal.name}")
            return False
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"regenerate_replaced_meal", "traceback": traceback.format_exc()})
        logger.error(f"[{request_id}] Exception regenerating meal: {e}")
        return False

def apply_modifications(
    user,
    meal_plan: MealPlan,
    raw_prompt: str,
    *,
    request_id: Optional[str] = None,
):
    """
    High-level entry point: parse the user's request and apply slot-level changes.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())

    logger.info("[%s] Parsing modification request for MealPlan %s", request_id, meal_plan.id)
    
    try:
        parsed_req = parse_modification_request(raw_prompt, meal_plan)
        try:
            slot_summ = [
                {
                    "meal_plan_meal_id": getattr(s, 'meal_plan_meal_id', None),
                    "should_remove": getattr(s, 'should_remove', False),
                    "rules_count": len(getattr(s, 'change_rules', []) or []),
                    "rules": getattr(s, 'change_rules', []),
                }
                for s in parsed_req.slots
            ]
            preview = str(slot_summ)
        except Exception:
            pass
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_modifications", "traceback": traceback.format_exc()})
        raise

    # Map slot IDs to DB rows once to avoid repetitive queries
    try:
        meals = meal_plan.mealplanmeal_set.select_related("meal").all()
        id_to_mpm = {
            mpm.id: mpm
            for mpm in meals
        }
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_modifications", "traceback": traceback.format_exc()})
        raise

    num_changes = 0
    for slot in parsed_req.slots:
        
        # Check if we need to skip this slot
        if not slot.change_rules:
            continue  # No change -> skip

        try:
            # Convert meal_plan_meal_id to int if it's a string
            meal_id = int(slot.meal_plan_meal_id) if isinstance(slot.meal_plan_meal_id, str) else slot.meal_plan_meal_id
            mpm = id_to_mpm.get(meal_id)
        except Exception as e:
            mpm = None

        if not mpm:
            logger.warning(
                "[%s] Slot ID %s not found – skipping (parser error?)",
                request_id,
                slot.meal_plan_meal_id,
            )
            continue

        logger.info(
            "[%s] Modifying %s (%s %s) with rules %s",
            request_id,
            mpm.meal.name,
            mpm.day,
            mpm.meal_type,
            slot.change_rules,
        )

        try:
            # Join change rules into a semicolon-separated string
            rules_text = "; ".join(slot.change_rules)
            
            # Check if this meal should be removed without replacement
            if slot.should_remove:
                logger.info(
                    "[%s] Meal %s (%s %s) marked for removal without replacement",
                    request_id,
                    mpm.meal.name,
                    mpm.day,
                    mpm.meal_type
                )
            
            modify_existing_meal_plan(
                user=user,
                meal_plan_id=meal_plan.id,
                user_prompt=rules_text,
                days_to_modify=[mpm.day],
                prioritized_meals={mpm.day: [mpm.meal_type]},
                request_id=request_id,
                should_remove=slot.should_remove,  # Pass the should_remove flag
            )
            num_changes += 1
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_modifications", "traceback": traceback.format_exc()})
            raise

    # Re-analyse plan only once
    if num_changes:
        try:
            analyze_and_replace_meals(user, meal_plan, ["Breakfast", "Lunch", "Dinner"], request_id)
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"apply_modifications", "traceback": traceback.format_exc()})
            raise
            
        logger.info("[%s] Applied %d slot change(s) for MealPlan %s", request_id, num_changes, meal_plan.id)
    else:
        logger.info("[%s] No slot required changes – meal plan unchanged", request_id)
    
    return meal_plan
