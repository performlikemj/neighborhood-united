"""
Focus: High-level orchestration of meal plan creation, scheduling, and integrating other modules.
"""
import json
import logging
import os
import random
import requests
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from types import SimpleNamespace
from random import shuffle
from typing import List, Set, Optional, Tuple
from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from openai import OpenAI, OpenAIError
from custom_auth.models import CustomUser
from meals.email_service import send_meal_plan_approval_email, generate_emergency_supply_list
from meals.meal_generation import generate_and_create_meal, perform_openai_sanity_check
from meals.models import Meal, MealPlan, MealPlanMeal, MealPlanInstruction
from meals.tasks import MAX_ATTEMPTS
from meals.pydantic_models import (MealsToReplaceSchema, MealPlanApprovalEmailSchema, BulkPrepInstructions)
from shared.utils import (generate_user_context, get_embedding, cosine_similarity, replace_meal_in_plan,
                          remove_meal_from_plan)
from django.db.transaction import TransactionManagementError
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.db import transaction

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_KEY)

@shared_task
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
        if meal_plan:
            try:
                send_meal_plan_approval_email(meal_plan.id)
            except Exception as e:
                logger.error(f"Error sending approval email for user {user.username}: {e}")
                traceback.print_exc()
            
            if user.emergency_supply_goal > 0:
                try:
                    generate_emergency_supply_list(user.id)
                except Exception as e:
                    logger.error(f"Error generating emergency supply list for user {user.username}: {e}")
                    traceback.print_exc()
    except CustomUser.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")

@shared_task
def create_meal_plan_for_all_users():
    today = timezone.now().date()

    # If today is Sunday, we want to start the meal plan for the next day (Monday)
    start_of_week = today + timedelta(days=1) if today.weekday() == 6 else today - timedelta(days=today.weekday()) + timedelta(days=7)
    
    # End of the week is 6 days after the start of the week
    end_of_week = start_of_week + timedelta(days=6)

    # Fetch all users
    users = CustomUser.objects.filter(email_confirmed=True)

    for user in users:
        meal_plan = create_meal_plan_for_user(user, start_of_week, end_of_week)
        if meal_plan:
            try:
                send_meal_plan_approval_email(meal_plan.id)
            except Exception as e:
                logger.error(f"Error sending approval email for user {user.username}: {e}")
                traceback.print_exc()

def day_to_offset(day_name: str) -> int:
    """Convert 'Monday' -> 0, 'Tuesday' -> 1, etc."""
    mapping = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    return mapping.get(day_name, 0)

def create_meal_plan_for_user(user, start_of_week=None, end_of_week=None, monday_date=None, request_id=None):
    """
    Create a meal plan for a user for a specific week.
    
    Parameters:
    - user: The user to create the meal plan for
    - start_of_week: The start date of the week
    - end_of_week: The end date of the week
    - monday_date: The Monday date of the week (optional)
    - request_id: Optional request ID for logging correlation
    
    Returns:
    - The created meal plan or None if creation failed
    """
    from meals.pantry_management import get_expiring_pantry_items
    
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    logger.info(f"[{request_id}] Creating meal plan for user {user.username} from {start_of_week} to {end_of_week}")
    
    # Use a transaction to prevent race conditions
    with transaction.atomic():
        # Check for existing meal plan with select_for_update to lock the rows
        existing_meal_plan = MealPlan.objects.select_for_update().filter(
            user=user,
            week_start_date=start_of_week if monday_date is None else monday_date,
            week_end_date=end_of_week
        ).first()
        
        if existing_meal_plan:
            # Check if the plan has meals
            existing_meals = MealPlanMeal.objects.filter(meal_plan=existing_meal_plan)
            
            if existing_meals.exists():
                logger.info(f"[{request_id}] User {user.username} already has meals for the week. Returning existing plan.")
                return existing_meal_plan
            else:
                # Empty meal plan - delete it and create a new one
                logger.warning(f"[{request_id}] Found empty meal plan (ID: {existing_meal_plan.id}) for user {user.username}. Deleting it.")
                existing_meal_plan.delete()
                logger.info(f"[{request_id}] Deleted empty meal plan (ID: {existing_meal_plan.id})")

        # Create a new meal plan
        try:
            if monday_date is None:
                meal_plan = MealPlan.objects.create(
                    user=user,
                    week_start_date=start_of_week,
                    week_end_date=end_of_week,
                )
            else:
                meal_plan = MealPlan.objects.create(
                    user=user,
                    week_start_date=monday_date,
                    week_end_date=end_of_week,
                )
            logger.info(f"[{request_id}] Created new meal plan (ID: {meal_plan.id}) for user {user.username}")
        except Exception as e:
            logger.error(f"[{request_id}] Error creating meal plan for user {user.username}: {str(e)}")
            return None

    user_id = user.id
    
    # These operations can be outside the transaction since we now have a valid meal plan
    meal_types = ['Breakfast', 'Lunch', 'Dinner']
    existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
    existing_meal_names = set(existing_meals.values_list('meal__name', flat=True))
    existing_meal_embeddings = list(existing_meals.values_list('meal__meal_embedding', flat=True))

    skipped_meal_ids = set()
    used_pantry_item = False  # ADDED

    day_count = (end_of_week - start_of_week).days + 1
    logger.info(f"[{request_id}] Creating meal plan for {day_count} days")
    
    for day_offset in range(day_count):
        meal_date = start_of_week + timedelta(days=day_offset)
        day_name = meal_date.strftime('%A')
        logger.debug(f"[{request_id}] Processing day: {day_name} ({meal_date})")
        
        for meal_type in meal_types:
            # Check if a meal already exists for this day and meal type
            if MealPlanMeal.objects.filter(
                meal_plan=meal_plan,
                meal_date=meal_date,
                day=day_name,
                meal_type=meal_type
            ).exists():
                logger.debug(f"[{request_id}] Meal already exists for {day_name} {meal_type}. Skipping.")
                continue

            attempt = 0
            meal_added = False

            while attempt < MAX_ATTEMPTS and not meal_added:
                attempt += 1
                logger.debug(f"[{request_id}] Attempt {attempt} to add meal for {day_name} {meal_type}")

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
                    result = generate_and_create_meal(
                        user=user,
                        meal_plan=meal_plan,
                        meal_type=meal_type,
                        existing_meal_names=existing_meal_names,
                        existing_meal_embeddings=existing_meal_embeddings,
                        user_id=user_id,
                        day_name=day_name,
                        request_id=request_id
                    )
                    if result['status'] == 'success':
                        meal = result['meal']
                        meal_added = True
                        logger.info(f"[{request_id}] Successfully generated new meal '{meal.name}' for {day_name} {meal_type}")
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
                    if perform_openai_sanity_check(meal_found, user):
                        try:
                            offset = day_to_offset(day_name)
                            meal_date = meal_plan.week_start_date + timedelta(days=offset)
                            MealPlanMeal.objects.create(
                                meal_plan=meal_plan,
                                meal=meal_found,
                                day=day_name,
                                meal_date=meal_date,
                                meal_type=meal_type,
                            )
                            existing_meal_names.add(meal_found.name)
                            existing_meal_embeddings.append(meal_found.meal_embedding)
                            logger.info(f"[{request_id}] Added existing meal '{meal_found.name}' for {day_name} {meal_type}.")
                            meal_added = True
                        except Exception as e:
                            logger.error(f"[{request_id}] Error adding meal '{meal_found.name}' to meal plan: {e}")
                            skipped_meal_ids.add(meal_found.id)
                    else:
                        logger.warning(f"[{request_id}] Meal '{meal_found.name}' fails sanity check. Skipping.")
                        skipped_meal_ids.add(meal_found.id)
                        meal_found = None  # Retry

                if attempt >= MAX_ATTEMPTS and not meal_added:
                    logger.error(f"[{request_id}] Failed to add meal for {day_name} {meal_type} after {MAX_ATTEMPTS} attempts.")

    # Check if we added any meals
    meal_count = MealPlanMeal.objects.filter(meal_plan=meal_plan).count()
    if meal_count == 0:
        logger.error(f"[{request_id}] No meals were added to meal plan (ID: {meal_plan.id}). Deleting it.")
        meal_plan.delete()
        return None

    logger.info(f"[{request_id}] Meal plan created successfully for {user.username} with {meal_count} meals")

    # If any meal used pantry items, skip replacements
    if used_pantry_item:
        logger.info(f"[{request_id}] At least one meal used soon-to-expire pantry items; skipping replacements.")
    else:
        logger.info(f"[{request_id}] Analyzing and replacing meals if needed.")
        analyze_and_replace_meals(user, meal_plan, meal_types, request_id)

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

    # Fetch previous meal plans
    last_week_meal_plan = MealPlan.objects.filter(user=user, week_start_date=meal_plan.week_start_date - timedelta(days=7)).first()
    two_weeks_ago_meal_plan = MealPlan.objects.filter(user=user, week_start_date=meal_plan.week_start_date - timedelta(days=14)).first()

    # Query the user's meal plan meals
    current_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan)
    previous_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=last_week_meal_plan)
    two_weeks_ago_meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=two_weeks_ago_meal_plan)

    current_meal_plan_str = format_meal_plan(current_meal_plan_meals)
    previous_week_plan_str = format_meal_plan(previous_meal_plan_meals)
    two_weeks_ago_plan_str = format_meal_plan(two_weeks_ago_meal_plan_meals)

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a meal planning assistant tasked with ensuring variety in the user's meal plans. "
                    "Analyze the current week's meal plan in the context of the previous two weeks' meal plans. "
                    "Identify any meals that are duplicates or too similar to previous meals and should be replaced. "
                    "Provide your response in the specified JSON format."
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
                    "Please identify meals in the current meal plan that should be replaced to ensure variety. "
                    "Provide your response in the following JSON format:\n"
                    "{\n"
                    "  \"meals_to_replace\": [\n"
                    "    {\"meal_id\": int, \"day\": str, \"meal_type\": str},\n"
                    "    ...\n"
                    "  ]\n"
                    "}"
                )
            }
        ]
        store=True,
        metadata={'tag': 'meal-plan-analysis'}
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={
                'type': 'json_schema',
                'json_schema': 
                    {
                        "name": "MealsToReplace",
                        "schema": MealsToReplaceSchema.model_json_schema()
                    }
                }
        )

        assistant_message = response.choices[0].message.content

        try:
            # Step 1: Deserialize the string into a Python dictionary
            parsed_response = json.loads(assistant_message)

            # Step 2: Validate the parsed response with Pydantic
            meals_to_replace = MealsToReplaceSchema.model_validate(parsed_response)
        except Exception as e:
            logger.error(f"Error parsing assistant's response: {e}")
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
                        logger.error(f"[{request_id}] Failed to create a fallback meal for {meal_type} on {day}: {result['message']}")
                    
                    continue  # Move to the next meal to replace

                # Iterate over possible replacements until a suitable one is found
                replacement_found = False
                while possible_replacements and not replacement_found:
                    # Pop a meal from the shuffled list to ensure it's not reused
                    new_meal = possible_replacements.pop()
                    new_meal_id = new_meal.id

                    # Perform the sanity check
                    if perform_openai_sanity_check(new_meal, user):
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
                        logger.warning(f"[{request_id}] Meal '{new_meal.name}' failed sanity check. Trying next possible replacement.")

                if not replacement_found:
                    logger.error(f"[{request_id}] Could not find a suitable replacement for meal ID {old_meal_id} on {day} ({meal_type}).")

    except Exception as e:
        logger.error(f"Error during meal plan analysis and replacement: {e}")
        traceback.print_exc()
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
    min_rating_threshold: int = 3,  # <--- define your threshold
) -> Optional[Meal]:
    # Convert existing meal names to lowercase for consistency
    existing_meal_names_lower = {name.lower() for name in existing_meal_names}

    # Collect regular dietary preferences
    regular_dietary_prefs = list(user.dietary_preferences.all())
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())

    # (1) Identify meals with bad reviews from this user
    from reviews.models import Review
    from django.contrib.contenttypes.models import ContentType
    meal_ct = ContentType.objects.get(app_label="meals", model="meal")
    badly_reviewed_meal_ids = (
        Review.objects
        .filter(
            user=user,
            rating__lt=min_rating_threshold,
            content_type=meal_ct
        )
        # "object_id" holds the actual Meal's primary key
        .values_list('object_id', flat=True)
    )

    mealplan_ct = ContentType.objects.get(app_label="meals", model="mealplan")

    badly_reviewed_mealplan_ids = (
        Review.objects
        .filter(
            user=user,
            rating__lt=min_rating_threshold,
            content_type=mealplan_ct
        )
        .values_list('object_id', flat=True)
    )

    meals_in_bad_plans = (
        MealPlanMeal.objects.filter(meal_plan__in=badly_reviewed_mealplan_ids)
        .values_list('meal_id', flat=True)
        .distinct()
    )

    # (2) Build your base Q filter for user's dietary prefs
    everything_pref = next((pref for pref in regular_dietary_prefs if pref.name == "Everything"), None)

    if everything_pref and len(regular_dietary_prefs) == 1 and not custom_dietary_prefs:
        potential_meals = Meal.objects.filter(
            meal_type=meal_type,
            creator_id=user.id
        )
    else:
        # build Q filter for the user's dietary prefs
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

    # (3) Exclude meals the user explicitly wants to skip,
    #     exclude existing meal names, and exclude badly reviewed meals
    potential_meals = (
        potential_meals
        .exclude(id__in=skipped_meal_ids)
        .exclude(name__in=existing_meal_names_lower)
        .exclude(id__in=badly_reviewed_meal_ids)
        .exclude(id__in=meals_in_bad_plans)
        .distinct()
    )

    # same uniqueness checks as before
    if not potential_meals.exists():
        print(f"No potential meals found for user {user.username} and meal type {meal_type} after rating filter.")
        return None

    # If no existing embeddings, just pick the first
    if not existing_meal_embeddings:
        return potential_meals.first()

    # Otherwise do your similarity check
    for meal in potential_meals:
        if meal.meal_embedding is None or meal.meal_embedding.size == 0:
            continue
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
            return meal
    
    return None


def get_similar_meal(user_id, name, description, meal_type):
    """
    Retrieves an existing meal similar to the provided details.
    """

    # Example logic to find a similar meal
    similar_meals = Meal.objects.filter(
        creator_id=user_id,
        meal_type=meal_type
    ).exclude(
        name=name  # Exclude the current meal by name
    ).exclude(
        Q(dishes__ingredients__name__in=get_user_allergies(user_id))  # Exclude meals with allergens
    ).distinct()
    
    similar_meal_count = similar_meals.count()

    # Compute embedding for the current meal's description
    current_embedding = get_embedding(description)  # 1D array

    # Initialize counters for similarity matches
    similarity_matches = 0

    for meal in similar_meals:
        if not meal.meal_embedding:
            continue  # Skip meals without embeddings
        
        # Convert meal embedding to a 1D array
        existing_embedding = meal.meal_embedding  # 1D array
        
        # Compute cosine similarity without reshaping
        similarity = cosine_similarity(current_embedding, existing_embedding)

        if similarity >= 0.8:  # Threshold for similarity
            similarity_matches += 1
            return meal  # Return the first sufficiently similar meal

    return None  # No similar meal found

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