import logging
from datetime import timedelta
from typing import List, Set, Optional
from django.conf import settings
import json
from django.shortcuts import get_object_or_404
import numpy as np
from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from openai import OpenAI
try:
    from groq import Groq  # optional Groq client
except Exception:
    Groq = None
import uuid
import time
import traceback
import os
import requests
from custom_auth.models import CustomUser
from meals.models import Meal, MealPlan, MealPlanMeal, PantryItem, MealPlanMealPantryUsage, MealCompatibility
from meals.pydantic_models import SanitySchema, UsageList
from shared.utils import (generate_user_context, create_meal,
                          get_embedding, cosine_similarity, get_openai_client)
from meals.pantry_management import get_expiring_pantry_items, compute_effective_available_items
from openai import OpenAIError, BadRequestError

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

def _household_coverage_ok(user: CustomUser, composed_dishes) -> bool:
    """
    Minimal coverage check ensuring each household member can eat at least one dish.
    Rules:
    - Babies (<2 yrs): require a dish with target_groups containing 'baby' or dietary_tags including 'Baby-Safe'.
    - Members with dietary preferences: require a dish whose dietary_tags includes at least one of their preferences.
    - Others (no preferences): any dish with target_groups including 'general' OR any non-baby dish.
    If no household members are defined, return True.
    """
    try:
        members_qs = getattr(user, 'household_members', None)
        if members_qs is None or not members_qs.exists():
            return True

        dishes = composed_dishes or []
        if not isinstance(dishes, list) or len(dishes) == 0:
            return False

        def has_baby_safe(d):
            tags = [t.lower() for t in (d.get('dietary_tags') or [])]
            groups = [g.lower() for g in (d.get('target_groups') or [])]
            return ('baby-safe' in tags) or any(g in ['baby', 'infant'] for g in groups)

        def covers_pref(d, pref_name: str) -> bool:
            tags = [t.lower() for t in (d.get('dietary_tags') or [])]
            return pref_name.lower() in tags

        def is_general(d) -> bool:
            groups = [g.lower() for g in (d.get('target_groups') or [])]
            return 'general' in groups or len(groups) == 0

        for member in members_qs.all():
            # Baby coverage
            if getattr(member, 'age', None) is not None and member.age < 2:
                if not any(has_baby_safe(d) for d in dishes):
                    return False
                continue

            # Dietary preference coverage
            member_prefs = list(getattr(member, 'dietary_preferences', []).all()) if hasattr(member, 'dietary_preferences') else []
            if member_prefs:
                # at least one preference must be covered by at least one dish
                names = [getattr(p, 'name', '').lower() for p in member_prefs]
                if not any(any(covers_pref(d, n) for n in names) for d in dishes):
                    return False
                continue

            # General eater coverage
            if not any(is_general(d) for d in dishes):
                # fallback: if no explicit general dish, allow any non-baby dish
                if not any(not has_baby_safe(d) for d in dishes):
                    return False

        return True
    except Exception:
        # Fail-open to avoid blocking generation in edge cases
        return True

def use_pantry_item(pantry_item: PantryItem, units_to_use: int) -> None:
    """
    Increments used_count for this pantry item by units_to_use,
    ensuring we don't exceed the total quantity.
    """
    if units_to_use <= 0:
        return  # do nothing if zero or invalid
    
    if pantry_item.available_quantity < units_to_use:
        # Not enough available to fulfill. You can either:
        # - raise an Exception
        # - partially use what's left
        # - or skip usage
        raise ValueError(f"Not enough {pantry_item.item_name} available to use {units_to_use}. Only {pantry_item.available_quantity} left.")
    
    pantry_item.used_count += units_to_use
    pantry_item.save()

def day_to_offset(day_name: str) -> int:
    """Convert 'Monday' -> 0, 'Tuesday' -> 1, etc."""
    mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    return mapping.get(day_name, 0)

def generate_and_create_meal(
    user, 
    meal_plan, 
    meal_type, 
    existing_meal_names, 
    existing_meal_embeddings, 
    user_id, 
    day_name, 
    max_attempts=3,
    user_prompt=None,
    request_id=None,
    user_goal_description: Optional[str] = None
):
    """
    Generate and create a meal for a specific day and meal type.
    
    Parameters:
    - user: The user to create the meal for
    - meal_plan: The MealPlan object to add the meal to
    - meal_type: The type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')
    - existing_meal_names: Set of existing meal names to avoid duplicates
    - existing_meal_embeddings: List of existing meal embeddings for similarity checks
    - user_id: The ID of the user
    - day_name: The day of the week (e.g., 'Monday', 'Tuesday')
    - max_attempts: Maximum number of attempts to generate a valid meal
    - user_prompt: Optional user prompt to guide meal generation
    - request_id: Optional request ID for logging correlation
    - user_goal_description: Optional string describing the user's dietary or macro goal, forwarded to the generation prompt.
    
    Returns:
    - Dictionary with status, message, meal, and used_pantry_item
    """
    # Import here to avoid circular imports
    from meals.meal_plan_service import perform_comprehensive_sanity_check
    from meals.macro_info_retrieval import get_meal_macro_information
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())
    # High-signal breadcrumb visible at WARNING level
    # Generation start breadcrumb (kept at INFO for normal verbosity)
    logger.info(f"[{request_id}] Start generate_and_create_meal user={getattr(user, 'id', user_id)} plan={getattr(meal_plan, 'id', 'unknown')} day={day_name} meal_type={meal_type}")
        
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"[{request_id}] Attempt={attempt} day={day_name} meal_type={meal_type} existing_count={len(existing_meal_names)} composed_embeddings={len(existing_meal_embeddings)}")

        # Step A: Generate meal details
        meal_details = generate_meal_details(
            user,
            meal_type,
            existing_meal_names,
            existing_meal_embeddings,
            meal_plan=meal_plan,
            user_prompt=user_prompt,
            request_id=request_id,
            user_goal_description=user_goal_description,
        )
        if not meal_details:
            logger.error(f"[{request_id}] Attempt {attempt}: Failed to generate meal details for {meal_type} on {day_name}.")
            continue  # Retry
        else:
            logger.info(f"[{request_id}] meal_name='{meal_details.get('name')}' pantry_used={len(meal_details.get('used_pantry_items', []))} composed_dishes={len(meal_details.get('composed_dishes') or [])}")

        used_pantry_items = meal_details.get('used_pantry_items', [])
        logger.info(f"[{request_id}] Used pantry items: {used_pantry_items}")

        # NEW: coverage check for composed dishes across the household
        composed_dishes = meal_details.get('composed_dishes')
        if composed_dishes and not _household_coverage_ok(user, composed_dishes):
            logger.warning(f"[{request_id}] Attempt {attempt}: composed_dishes failed household coverage. Retrying.")
            continue

        # Step B: Create the meal record
        meal_data = create_meal(
            user_id=user_id,
            name=meal_details.get('name'),
            dietary_preferences=meal_details.get('dietary_preferences'),
            description=meal_details.get('description'),
            meal_type=meal_type,
            used_pantry_items=used_pantry_items,
            composed_dishes=meal_details.get('composed_dishes'),
        )

        # Handle the "info" status if a similar meal was found
        if meal_data['status'] == 'info' and 'similar_meal_id' in meal_data:
            similar_meal_id = meal_data['similar_meal_id']
            try:
                meal = Meal.objects.get(id=similar_meal_id)
                # Skip if similar meal was used in any of the previous 3 weeks
                try:
                    ranges = [
                        (
                            meal_plan.week_start_date - timedelta(days=7*i),
                            meal_plan.week_end_date - timedelta(days=7*i)
                        ) for i in range(1, 4)
                    ]
                    from django.db.models import Q
                    reuse_q = Q(meal_plan__user=user) & Q(meal_id=meal.id)
                    week_q = Q()
                    for ws, we in ranges:
                        week_q |= Q(meal_plan__week_start_date=ws, meal_plan__week_end_date=we)
                    used_recently = MealPlanMeal.objects.filter(reuse_q & week_q).exists()
                    if used_recently:
                        logger.info(f"[{request_id}] Similar meal '{meal.name}' was used in the last 3 weeks; skipping reuse.")
                        continue  # Retry generation to find a different meal
                except Exception:
                    pass
                offset = day_to_offset(day_name)
                meal_date = meal_plan.week_start_date + timedelta(days=offset)
                logger.info(f"[{request_id}] Similar meal '{meal.name}' already exists. Adding to meal plan.")
                # Remove meal plan meal for this day and meal type if it exists
                MealPlanMeal.objects.filter(
                    meal_plan=meal_plan,
                    day=day_name,
                    meal_type=meal_type
                ).delete()
                MealPlanMeal.objects.create(
                    meal_plan=meal_plan,
                    meal=meal,
                    day=day_name,
                    meal_date=meal_date,
                    meal_type=meal_type,
                )
                existing_meal_names.add(meal.name)
                existing_meal_embeddings.append(meal.meal_embedding)
                return {
                    'status': 'success',
                    'message': f'Similar meal found and added: {meal.name}.',
                    'meal': meal,
                    'used_pantry_item': False,  # No pantry items in a "similar meal" scenario
                }
            except Meal.DoesNotExist:
                logger.error(f"[{request_id}] Similar meal with ID {similar_meal_id} does not exist.")
                continue  # Retry

        # If meal creation failed for other reasons
        if meal_data['status'] != 'success':
            logger.error(f"[{request_id}] Attempt {attempt}: Failed to create meal: {meal_data.get('message')}")
            continue  # Retry
        else:
            # Created candidate meal – log at WARNING for Celery warning-level visibility
            try:
                candidate_name = meal_data.get('meal', {}).get('name')
            except Exception:
                candidate_name = None
            logger.info(f"[{request_id}] Created candidate meal '{candidate_name or '?'}' for {day_name} {meal_type}")

        # Step C: Verify the newly-created meal
        try:
            meal_id = meal_data['meal'].get('id') if meal_data.get('meal') else None
            if not meal_id:
                logger.warning(f"[{request_id}] Skipping macro/video fetch: missing meal_id in response.")
                continue  # Retry generation cleanly
            meal = Meal.objects.get(id=meal_id)
            
            # Get ingredients if available
            ingredients = []
            try:
                for dish in meal.dishes.all():
                    ingredients.extend([i.name for i in dish.ingredients.all()])
                logger.info(f"[{request_id}] Found {len(ingredients)} ingredients for meal '{meal.name}': {ingredients}")
            except Exception as e:
                logger.warning(f"[{request_id}] Could not retrieve ingredients for meal '{meal.name}': {e}")
                
            # DIRECT ENHANCEMENT: Add macro information
            try:
                if meal and meal.id:
                    logger.info(f"[{request_id}] Getting macro information for meal '{meal.name}'")
                    macro_info = get_meal_macro_information(
                        meal_name=meal.name,
                        meal_description=meal.description,
                        ingredients=ingredients
                    )
                    if macro_info:
                        logger.info(f"[{request_id}] Saving macro information for meal '{meal.name}': {macro_info}")
                        meal.macro_info = json.dumps(macro_info)
                        meal.save(update_fields=['macro_info'])
                        logger.info(f"[{request_id}] Successfully added macro information to meal '{meal.name}'")
                    else:
                        logger.warning(f"[{request_id}] No macro information returned for meal '{meal.name}'")
            except Exception as e:
                logger.error(f"[{request_id}] Error adding macro information to meal '{meal.name}': {e}")
                logger.error(f"[{request_id}] {traceback.format_exc()}")

            # Verify the data was actually saved
            try:
                meal.refresh_from_db()
                logger.info(f"[{request_id}] Verification - Meal '{meal.name}' now has: macro_info: {bool(meal.macro_info)}, youtube_videos: {bool(meal.youtube_videos)}")
            except Exception as e:
                logger.error(f"[{request_id}] Error verifying saved data for meal '{meal.name}': {e}")
                
        except Meal.DoesNotExist:
            logger.error(f"[{request_id}] Meal with ID {meal_id} does not exist after creation.")
            continue  # Retry

        # Step D: Perform a comprehensive sanity check
        sanity_ok = perform_comprehensive_sanity_check(meal, user, request_id)
        logger.info(f"[{request_id}] sanity_ok={sanity_ok} meal_id={meal.id} name='{meal.name}'")
        if not sanity_ok:
            logger.warning(f"[{request_id}] Attempt {attempt}: Generated meal '{meal.name}' failed comprehensive sanity check.")
            continue  # Retry

        # Step E: Actually attach the meal to the meal plan
        offset = day_to_offset(day_name)
        meal_date = meal_plan.week_start_date + timedelta(days=offset)
        # Remove meal plan meal for this day and meal type if it exists
        MealPlanMeal.objects.filter(
            meal_plan=meal_plan,
            day=day_name,
            meal_type=meal_type
        ).delete()
        new_meal_plan_meal = MealPlanMeal.objects.create(
            meal_plan=meal_plan,
            meal=meal,
            day=day_name,
            meal_date=meal_date,
            meal_type=meal_type,
        )

        # Step F: If GPT used pantry items, create bridging usage records
        used_any_pantry = False
        if len(used_pantry_items) > 0:
            used_any_pantry = True
            logger.info(f"[{request_id}] Processing {len(used_pantry_items)} pantry items for meal '{meal.name}'")
            for item_name in used_pantry_items:
                pantry_item_obj = PantryItem.objects.filter(user=user, item_name=item_name).first()
                if pantry_item_obj:
                    bridging_obj = MealPlanMealPantryUsage.objects.create(
                        meal_plan_meal=new_meal_plan_meal,
                        pantry_item=pantry_item_obj,
                        quantity_used=0,
                        usage_unit=pantry_item_obj.weight_unit
                    )
                    usage_data = [
                        {
                            "item_name": bridging_obj.pantry_item.item_name,
                            "item_type": bridging_obj.pantry_item.item_type,
                            "quantity_used": bridging_obj.quantity_used,
                            "usage_unit": bridging_obj.usage_unit,
                        }
                    ]
                    determine_usage_for_meal.delay(
                        meal_plan_meal_id=new_meal_plan_meal.id,
                        meal_name=meal.name,
                        meal_description=meal.description,
                        used_pantry_info=usage_data,
                        serving_size=user.household_member_count,
                        request_id=request_id
                    )
                    logger.info(f"[{request_id}] Scheduled usage determination for pantry item '{item_name}'")
                else:
                    logger.warning(f"[{request_id}] Pantry item '{item_name}' not found for user {user.username}")

        # Step G: Update context for subsequent calls
        existing_meal_names.add(meal.name)
        existing_meal_embeddings.append(meal.meal_embedding)
        logger.info(f"[{request_id}] Added new meal '{meal.name}' for {day_name} {meal_type}.")
        logger.info(f"[{request_id}] Attached meal '{meal.name}' to plan on {meal_date}")

        # Step H: Return success, letting caller know if pantry was used
        return {
            'status': 'success',
            'message': 'Meal created and added successfully.',
            'meal': meal,
            'used_pantry_item': used_any_pantry,
        }

    logger.error(f"[{request_id}] Failed to generate and create meal for {meal_type} on {day_name} after {max_attempts} attempts.")
    return {
        'status': 'error',
        'message': f'Failed to create meal after {max_attempts} attempts.',
        'used_pantry_item': False,  # In a fail scenario
    }
 
def perform_openai_sanity_check(meal, user):
    """
    Check if a meal meets a user's dietary preferences using OpenAI.
    Results are cached in the MealCompatibility model to avoid redundant API calls.
    
    Args:
        meal: The Meal object to check
        user: The CustomUser object
        
    Returns:
        bool: True if the meal meets dietary preferences, False otherwise
    """
    user_context = generate_user_context(user)
    combined_allergies = set((user.allergies or []) + (user.custom_allergies or []))
    allergies_str = ', '.join(combined_allergies) if combined_allergies else 'None'
    
    # Get all user's preferences
    regular_dietary_prefs = list(user.dietary_preferences.all())
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())
    all_prefs = regular_dietary_prefs + custom_dietary_prefs
    
    # Check if we have cached compatibility results for all preferences
    all_compatible = True
    all_cached = True
    
    for pref in all_prefs:
        pref_name = pref.name if hasattr(pref, 'name') else pref.custom_name
        
        cached_result = MealCompatibility.objects.filter(
            meal=meal,
            preference_name=pref_name
        ).first()
        
        if cached_result:
            # Use cached result
            if not cached_result.is_compatible or cached_result.confidence < 0.7:
                # If any preference is incompatible, the meal is incompatible
                logger.info(f"Using cached dietary check: Meal '{meal.name}' is incompatible with {pref_name}")
                return False
        else:
            # We don't have a cached result for at least one preference
            all_cached = False
    
    # If we have cached results for all preferences and they're all compatible, return True
    if all_cached and all_compatible:
        logger.info(f"Using cached dietary checks: Meal '{meal.name}' is compatible with all user preferences")
        return True
    
    # We need to perform a sanity check with OpenAI
    try:
        checker_prompt = f"""
        You are a **dietary-compliance checker**.

        --- TASK ---
        Given:
        • **Meal ingredients** (list of strings)  
        • **Allergens to avoid** (list of strings)  
        • **Dietary preferences** (list of strings)

        Return a JSON object that **exactly** matches this shape:

        {{
        "allergen_check": true | false
        }}

        — Output rules —
        1. `allergen_check` **true**  →  meal contains none of the listed allergens **and** meets every dietary preference.  
        2. `allergen_check` **false** →  otherwise.  
        3. Output **only** the JSON (no prose, no code-fences, no keys beyond the one shown).  
        4. Boolean values must be lowercase `true` / `false`.  
        5. Assume dietary preferences are strict (e.g., “vegetarian” excludes meat, poultry, fish).  
        6. If cross-contamination is explicitly noted in ingredients, treat as containing the allergen.

        --- EXAMPLES ---
        INPUT  
        • Ingredients: ["wheat", "milk", "peanut"]  
        • Allergens: ["peanut", "soy"]  
        • Preferences: ["vegetarian"]

        OUTPUT  
        {{"allergen_check": false}}

        INPUT  
        • Ingredients: ["rice", "broccoli", "tofu"]  
        • Allergens: ["peanut", "soy"]  
        • Preferences: ["vegetarian"]

        OUTPUT  
        {{"allergen_check": true}}

        --- USER DATA ---
        User context: {user_context}  
        Allergens to avoid: {allergies_str}  
        Meal name: "{meal.name}"  
        Meal description: {meal.description}  
        Meal dietary tags: {meal.dietary_preferences.all()} {meal.custom_dietary_preferences.all()}
        """
        groq_client = _get_groq_client()
        if groq_client:
            groq_resp = groq_client.chat.completions.create(
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": "You are a dietary-compliance checker. Return ONLY the JSON object that passes the provided schema; no prose."},
                    {"role": "user", "content": checker_prompt},
                ],
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "sanity_check",
                        "schema": SanitySchema.model_json_schema(),
                    },
                },
            )
            gpt_output = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=[
                    {
                        "role": "developer",
                        "content": (
                            # Stable meta-instruction
                            "You are a dietary-compliance checker. "
                            "Return ONLY the JSON object that passes the provided schema; no prose."
                        )
                    },
                    {
                        "role": "user",
                        "content": checker_prompt,
                    }
                ],
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'sanity_check',
                        'schema': SanitySchema.model_json_schema()
                    }
                }
            )

            gpt_output = response.output_text
        # Robustly parse and access JSON fields
        _parsed = json.loads(gpt_output)
        if isinstance(_parsed, list):
            _candidate = next((item for item in _parsed if isinstance(item, dict)), None)
            if _candidate is None and _parsed:
                _first = _parsed[0]
                if isinstance(_first, str):
                    try:
                        _inner = json.loads(_first)
                        if isinstance(_inner, dict):
                            _candidate = _inner
                    except Exception:
                        pass
            _parsed = _candidate or {}
        allergen_check = _parsed.get('allergen_check', False)
        
        # Cache the result for each preference
        if allergen_check:
            confidence = 1.0  # High confidence for positive results
            reasoning = "Meal meets all user dietary preferences according to GPT analysis"
        else:
            confidence = 0.0  # Low confidence for negative results
            reasoning = "Meal does not meet user dietary preferences according to GPT analysis"
        
        # Cache the result for each preference (with the same result)
        for pref in all_prefs:
            pref_name = pref.name if hasattr(pref, 'name') else pref.custom_name
            try:
                MealCompatibility.objects.update_or_create(
                    meal=meal,
                    preference_name=pref_name,
                    defaults={
                        'is_compatible': allergen_check,
                        'confidence': confidence,
                        'reasoning': reasoning
                    }
                )
            except Exception as e:
                logger.error(f"Error caching compatibility result for {pref_name}: {e}")
        
        return allergen_check

    except Exception as e:
        logger.error(f"Error during OpenAI sanity check: {e}")
        return False

def generate_meal_details(
    user,
    meal_type,
    existing_meal_names,
    existing_meal_embeddings,
    meal_plan,
    min_similarity=0.1,
    max_attempts=5,
    user_prompt=None,
    request_id=None,
    user_goal_description: Optional[str] = None
):
    """
    Generate meal details using OpenAI GPT model.
    
    Parameters:
    - user: The user to generate the meal for
    - meal_type: The type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')
    - existing_meal_names: Set of existing meal names to avoid duplicates
    - existing_meal_embeddings: List of existing meal embeddings for similarity checks
    - meal_plan: The MealPlan object to add the meal to
    - min_similarity: Minimum similarity threshold for deduplication
    - max_attempts: Maximum number of attempts to generate a valid meal
    - user_prompt: Optional user prompt to guide meal generation
    - request_id: Optional request ID for logging correlation
    - user_goal_description: Optional string describing the user's dietary or macro goal, forwarded to the generation prompt.
    
    Returns:
    - Dictionary containing generated meal details
    """
    from meals.pydantic_models import DietaryPreference

    if request_id is None:
        request_id = str(uuid.uuid4())

    # Short-circuit in test mode
    if settings.TEST_MODE:
        logger.info('[TEST_MODE] short-circuit meal generation')
        return {
            'name': 'Test Meal',
            'description': 'This is a test meal',
            'dietary_preferences': ['Everything'],
            'ingredients': []
        }
    allowed_enum = ", ".join(pref.value for pref in DietaryPreference)
    static_rules = f"… tags from: {allowed_enum}"

    # Rest of the function continues with normal processing
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        logger.info(f"[{request_id}] Attempt {attempts} to generate meal details for {meal_type}.")

        # 1) Fetch user's expiring pantry items and leftover availability
        expiring_pantry_items = get_expiring_pantry_items(user)  # e.g. [{'item_id': 1, 'item_name': 'Beef', 'quantity': 4}, ...]
        effective_avail_dict = compute_effective_available_items(user, meal_plan, days_threshold=7)

        # For logging and prompt: just show item names
        expiring_items_str = (
            ', '.join(d["item_name"] for d in expiring_pantry_items) 
            if expiring_pantry_items else "None"
        )

        # 2) Filter each expiring item by leftover
        updated_expiring_items = []
        for item_info in expiring_pantry_items:
            item_id = item_info.get("item_id")
            if not item_id:
                continue  # skip if there's no ID
            real_qty = item_info.get("quantity", 0)
            leftover_data = effective_avail_dict.get(item_id, (real_qty, ""))  # default to (real_qty, "")
            leftover_qty, leftover_unit = leftover_data  # e.g. leftover_qty=2.5, leftover_unit='lb'

            if leftover_qty <= 0:
                continue  # item is fully used/reserved, skip
            new_item = dict(item_info)
            new_item["quantity"] = leftover_qty
            updated_expiring_items.append(new_item)

        # 3) Identify previous 3 weeks' meals relative to the target plan (to avoid duplicates)
        try:
            target_week_start = getattr(meal_plan, 'week_start_date', None)
            target_week_end = getattr(meal_plan, 'week_end_date', None)
            if target_week_start and target_week_end:
                week_ranges = [
                    (target_week_start - timedelta(days=7*i), target_week_end - timedelta(days=7*i))
                    for i in range(1, 4)
                ]
            else:
                # Fallback to calendar-based weeks if plan dates are unavailable
                base_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
                week_ranges = [
                    (base_start - timedelta(days=7*i), (base_start - timedelta(days=7*i)) + timedelta(days=6))
                    for i in range(1, 4)
                ]
        except Exception:
            base_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
            week_ranges = [
                (base_start - timedelta(days=7*i), (base_start - timedelta(days=7*i)) + timedelta(days=6))
                for i in range(1, 4)
            ]

        from django.db.models import Q
        week_q = Q()
        for ws, we in week_ranges:
            week_q |= Q(meal_plan__week_start_date=ws, meal_plan__week_end_date=we)
        previous_meals = MealPlanMeal.objects.filter(
            Q(meal_plan__user=user) & week_q
        ).select_related('meal')

        previous_meal_names = set(previous_meals.values_list('meal__name', flat=True))
        previous_meal_embeddings = list(previous_meals.values_list('meal__meal_embedding', flat=True))

        # Combine meal names & embeddings with the ones passed in
        combined_meal_names = existing_meal_names.union(previous_meal_names)

        import numpy as np
        combined_meal_embeddings = []
        for emb in existing_meal_embeddings + previous_meal_embeddings:
            if isinstance(emb, np.ndarray):
                emb = emb.tolist()
            # Ensure it's a valid 1536-dim embedding of floats
            if isinstance(emb, list) and len(emb) == 1536 and all(isinstance(x, (int, float)) for x in emb):
                combined_meal_embeddings.append(emb)
            else:
                logger.error(f"Invalid or malformed embedding: {emb}")

        # 4) Gather user allergy/goal info for the GPT prompt
        allergens = set(user.allergies or []) | set(user.custom_allergies or [])
        allergens_str = ', '.join(allergens) if allergens else 'None'
        user_goals = user_goal_description if user_goal_description is not None else getattr(getattr(user, 'goal', None), 'goal_description', 'None')

        # 5) Build the GPT prompt
        base_prompt = build_user_context(user, expiring_items_str, user_goals, combined_meal_names, allergens_str, meal_type)

        static_rules = f"""
        You are a meal‑planning assistant focused on generating specific, appetizing, and diverse meals for a given week.
        
        Naming rules for the meal "name":
        - Use a concise, enticing title that references the primary composed dish (and optionally one secondary).
        - Prefer dish-driven names like “Lemon Herb Chicken with Roasted Vegetables” rather than generic labels.
        - Avoid marketing/goal terms and generics: balanced, healthy, low-calorie, fat loss, weight loss, plan, meal, dinner, lunch, breakfast.
        - Do not include body-goal or diet buzzwords in the name; save those for the description if needed.
        - Keep under 60 characters where possible; use Title Case.
        
        When creating "composed_dishes":
        - Ensure each dish has a clear name and tags; reuse one dish to cover multiple groups when appropriate.
        - chef_name must be null for user-generated dishes; set is_chef_dish=false.
        
        For "dietary_preferences" output 1–3 tags chosen from: {allowed_enum}
        """
        # 6) Attempt up to max_attempts

        for attempt in range(max_attempts):
            try:
                # Pass the list of possible dietary preferences to the model
                # Add dietary preferences to the base prompt
                meal_json_schema = {
                    "type": "object",
                    "properties": {
                        "meal": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "dietary_preferences": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "used_pantry_items": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "composed_dishes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "dietary_tags": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            },
                                            "target_groups": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                            },
                                            "notes": {"type": "string"},
                                            "ingredients": {"type": "array", "items": {"type": "string"}},
                                            "is_chef_dish": {"type": "boolean"}
                                        },
                                        "required": ["name", "dietary_tags", "target_groups", "notes", "ingredients", "is_chef_dish"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": [
                                "name",
                                "description",
                                "dietary_preferences",
                                "used_pantry_items",
                                "composed_dishes"
                            ],
                            "additionalProperties": False
                        }
                    },
                    "required": ["meal"],
                    "additionalProperties": False,
                }
                groq_client = _get_groq_client()
                if groq_client:
                    groq_resp = groq_client.chat.completions.create(
                        model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                        messages=[
                            {"role": "system", "content": static_rules + "\n\nOutput must include a 'composed_dishes' array that covers all household members: at minimum provide dishes for babies (<2 years) as baby-safe, vegans if present, and a general dish for unrestricted members. Reuse one dish to cover multiple groups when possible (e.g., a vegan-general dish). Each dish object must match the ComposedDish schema in MealData: name, dietary_tags, target_groups, optional notes and ingredients, and include is_chef_dish. The meal 'name' MUST reference at least the primary composed dish (e.g., include that dish’s name)."},
                            {"role": "user", "content": base_prompt},
                        ],
                        temperature=0.4,
                        top_p=1,
                        stream=False,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "meal_details",
                                "schema": meal_json_schema,
                            },
                        },
                    )
                    gpt_output = groq_resp.choices[0].message.content or "{}"
                else:
                    response = get_openai_client().responses.create(
                        model="gpt-5-mini",
                        input=[
                            {"role": "developer", "content": static_rules + "\n\nOutput must include a 'composed_dishes' array that covers all household members: at minimum provide dishes for babies (<2 years) as baby-safe, vegans if present, and a general dish for unrestricted members. Reuse one dish to cover multiple groups when possible (e.g., a vegan-general dish). Each dish object must match the ComposedDish schema in MealData: name, dietary_tags, target_groups, optional notes and ingredients, and include is_chef_dish. The meal 'name' MUST reference at least the primary composed dish (e.g., include that dish’s name)."},
                            {"role": "user", "content": base_prompt}
                        ],
                        text={
                            "format": {
                                'type': 'json_schema',
                                'name': 'meal_details',
                                'schema': meal_json_schema
                            }
                        }
                    )

                    gpt_output = response.output_text
                logger.info(f"[{request_id}] [DEBUG] GPT output: {gpt_output}")
                meal_data = json.loads(gpt_output)
                if isinstance(meal_data, list):
                    candidate = next((item for item in meal_data if isinstance(item, dict)), None)
                    if candidate is None and meal_data:
                        first = meal_data[0]
                        if isinstance(first, str):
                            try:
                                inner = json.loads(first)
                                if isinstance(inner, dict):
                                    candidate = inner
                            except Exception:
                                pass
                    meal_data = candidate or {}
                logger.info(f"[{request_id}] [DEBUG] Meal data: {meal_data}")
                meal_dict = meal_data.get('meal', {})
                meal_name = meal_dict.get('name')
                description = meal_dict.get('description')
                dietary_preferences = meal_dict.get('dietary_preferences', [])
                used_pantry_items = meal_dict.get('used_pantry_items', [])
                composed_dishes = meal_dict.get('composed_dishes')

                # Basic checks
                if not meal_name or not description or not dietary_preferences:
                    logger.error(f"[{request_id}] [Attempt {attempt+1}] Meal data incomplete: {meal_data}. Skipping.")
                    continue

                meal_representation = (
                    f"Name: {meal_name}, Description: {description}, "
                    f"Dietary Preferences: {dietary_preferences}, Meal Type: {meal_type}, "
                    f"Chef: {user.username}, Price: 'N/A'"
                )
                new_meal_embedding = get_embedding(meal_representation)

                # Uniqueness check vs. existing embeddings
                similar_meal_found = False
                for emb in combined_meal_embeddings:
                    similarity = cosine_similarity(new_meal_embedding, emb)
                    if similarity > (1 - min_similarity):
                        similar_meal_found = True
                        break

                if similar_meal_found:
                    continue

                # If no similarity found, we return the new meal data
                return {
                    'name': meal_name,
                    'description': description,
                    'dietary_preferences': dietary_preferences,
                    'meal_embedding': new_meal_embedding,
                    'used_pantry_items': used_pantry_items,
                    'composed_dishes': composed_dishes
                }

            except Exception as e:
                # n8n traceback
                if settings.DEBUG:
                    logger.error(f"Error during meal generation: {e}")
                    logger.error(traceback.format_exc())
                else:
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_meal_details", "traceback": traceback.format_exc()})
                    continue

        logger.error(f"[{request_id}] Failed to generate a unique meal after {max_attempts} attempts.")
        return None

def build_user_context(user, expiring_items_str, user_goals, combined_meal_names, allergens_str, meal_type, user_prompt=None):
    # fresh every attempt
    lines = [
        f"The user has expiring pantry items: {expiring_items_str or 'none'}",
        f"Do NOT copy previous meals: {', '.join(combined_meal_names)}",
        f"User goal: {user_goals}",
        f"Allergens: {allergens_str}",
        f"Household: {generate_user_context(user)}",
        f"Meal type required: {meal_type}",
    ]
    if user_prompt:
        lines.append(f"User request: {user_prompt}")
    return "\n".join(lines)

@shared_task
def determine_usage_for_meal(
    meal_plan_meal_id: int,
    meal_name: str,
    meal_description: str,
    used_pantry_info: list,
    serving_size: int,
    request_id=None
):
    """
    Determine the usage of pantry items for a meal.
    
    Parameters:
    - meal_plan_meal_id: The ID of the MealPlanMeal
    - meal_name: The name of the meal
    - meal_description: The description of the meal
    - used_pantry_info: List of pantry items used in the meal
    - serving_size: The serving size of the meal
    - request_id: Optional request ID for logging correlation
    
    Returns:
    - None
    """
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    logger = logging.getLogger(__name__)

    meal_plan_meal = get_object_or_404(MealPlanMeal, id=meal_plan_meal_id)
    user = meal_plan_meal.meal_plan.user

    used_items_str = json.dumps(used_pantry_info, ensure_ascii=False)

    regular_diet_prefs = list(user.dietary_preferences.all())
    custom_diet_prefs = list(user.custom_dietary_preferences.all())
    combined_prefs = regular_diet_prefs + custom_diet_prefs

    system_msg = (
        """
        Calculate the quantity of each pantry item needed for a meal based on the user's desired serving size and return the results in the specified JSON format.

        Here are the schemas that describe the structure of your response:

        - `UsageItem`: Represents an individual pantry item and includes:
        - `item_name`: The exact name of the pantry item.
        - `quantity_used`: A float indicating the number only (no text) of units required.
        - `unit`: The unit of measurement, such as 'cups', 'pieces', or 'grams'.

        - `UsageList`: A top-level object that contains an array of `UsageItem`.

        # Steps

        1. **Gather Input**: Determine the base recipe quantity for each pantry item in a single serving.
        2. **Calculate Quantities**: Multiply the base recipe quantity by the user's desired serving size to get the total quantity needed for each pantry item.
        3. **Create JSON**: Format the results according to the provided JSON schema.

        # Output Format

        Produce the output as a JSON object in the following structure:
        ```
        {
        "usage_items": [
            {
            "item_name": "string",
            "quantity_used": float,
            "unit": "string"
            },
            ...
        ]
        }
        ```

        # Examples

        **Input**: Base recipe requires 1 cup of milk and 2 eggs per serving. User desires 3 servings.

        **Output**:
        ```json
        {
        "usage_items": [
            {
            "item_name": "milk",
            "quantity_used": 3.0,
            "unit": "cups"
            },
            {
            "item_name": "eggs",
            "quantity_used": 6.0,
            "unit": "pieces"
            }
        ]
        }
        ```

        # Notes

        - Ensure all numeric quantities are represented as floats. Do not include unit names inside `quantity_used`.
        - Follow the JSON schema strictly, especially with field names and types.
        - Consider units carefully, especially when multiple units are possible for an item (e.g., grams vs. ounces).
        """
    )

    user_msg = (
        f"Meal Name: '{meal_name}'\n"
        f"Description: {meal_description}\n"
        f"Serving size: {serving_size} people (consider individual household member dietary needs and ages when determining quantities)\n"
        f"Items to use: {used_items_str}\n"
        f"User's dietary preferences: {combined_prefs}\n"
        f"User context with household member details: {generate_user_context(user)}\n"
        "Only return usage for the items in used_pantry_info. "
        "If an item is not used, omit it. Also specify the unit (e.g., 'cans' or 'cups'). "
        "Adjust quantities based on individual household member needs, ages, and dietary restrictions."
    )

    try:
        groq_client = _get_groq_client()
        if groq_client:
            groq_resp = groq_client.chat.completions.create(
                model=getattr(settings, 'GROQ_MODEL', 'openai/gpt-oss-120b'),
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                top_p=1,
                stream=False,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "meal_usage",
                        "schema": UsageList.model_json_schema(),
                    },
                },
            )
            usage_json = groq_resp.choices[0].message.content or "{}"
        else:
            response = get_openai_client().responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "developer", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                text={
                    "format": {
                        'type': 'json_schema',
                        'name': 'meal_usage',
                        'schema': UsageList.model_json_schema()
                    }
                }
            )
            usage_json = response.output_text
    except Exception as e:
        logger.error(f"Error calling GPT for usage (MealPlanMeal {meal_plan_meal_id}): {e}")
        return

    # Parse GPT's JSON
    try:
        usage_data = UsageList.model_validate_json(usage_json)
    except Exception as e:
        logger.error(f"Failed to parse usage data as JSON for MealPlanMeal {meal_plan_meal_id}: {e}")
        return

    logger.info(f"Usage data for MealPlanMeal {meal_plan_meal_id}: {usage_data}")

    # Update bridging usage
    from decimal import Decimal
    for usage_item in usage_data.usage_items:
        item_name = usage_item.item_name
        qty_str = usage_item.quantity_used
        usage_unit = usage_item.unit or ""

        try:
            quantity_used = Decimal(str(qty_str))
        except:
            quantity_used = Decimal("0")

        logger.info(f"Setting bridging usage for '{item_name}': {quantity_used} {usage_unit}")

        # Find the PantryItem
        pantry_item = PantryItem.objects.filter(
            user=user, 
            item_name__iexact=item_name
        ).first()
        if not pantry_item:
            logger.warning(f"No PantryItem found for '{item_name}'. Skipping bridging update.")
            continue

        # Create or update bridging
        obj, created = MealPlanMealPantryUsage.objects.get_or_create(
            meal_plan_meal=meal_plan_meal,
            pantry_item=pantry_item,
            defaults={"quantity_used": quantity_used, "usage_unit": usage_unit}
        )
        if not created:
            obj.quantity_used = quantity_used
            obj.usage_unit = usage_unit
            obj.save()

    logger.info(f"Finished updating usage info for MealPlanMeal ID={meal_plan_meal_id}")

    # 1) Re-run compute_effective_available_items to see new leftover
    from meals.pantry_management import compute_effective_available_items

    leftover_dict = compute_effective_available_items(user, meal_plan_meal.meal_plan)

    # 2) Log each item's new leftover
    for item_id, leftover_data in leftover_dict.items():
        # If your function returns just a float, leftover_data is a float
        # If it returns (leftover_amount, unit), unpack it:
        if isinstance(leftover_data, tuple):
            leftover_val, leftover_unit = leftover_data
        else:
            leftover_val = leftover_data
            leftover_unit = ""

        # Find the item's name
        try:
            pantry_item = PantryItem.objects.get(id=item_id)
            item_name = pantry_item.item_name
        except PantryItem.DoesNotExist:
            item_name = f"Unknown(ID={item_id})"

        logger.info(
            f"[{request_id}] [DEBUG] After bridging usage, leftover for '{item_name}' = {leftover_val} {leftover_unit}"
    )
