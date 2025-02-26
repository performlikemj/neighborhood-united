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
import uuid

from custom_auth.models import CustomUser
from meals.models import Meal, MealPlan, MealPlanMeal, PantryItem, MealPlanMealPantryUsage
from meals.pydantic_models import MealOutputSchema, SanitySchema, UsageList
from shared.utils import (generate_user_context, create_meal,
                          get_embedding, cosine_similarity)
from meals.pantry_management import get_expiring_pantry_items, compute_effective_available_items
from openai import OpenAIError, BadRequestError

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

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
    request_id=None
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
    
    Returns:
    - Dictionary with status, message, meal, and used_pantry_item
    """
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())
        
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"[{request_id}] Attempt {attempt} to generate and create meal for {meal_type} on {day_name}.")

        # Step A: Generate meal details
        meal_details = generate_meal_details(
            user,
            meal_type,
            existing_meal_names,
            existing_meal_embeddings,
            meal_plan=meal_plan,
            user_prompt=user_prompt,
            request_id=request_id
        )
        if not meal_details:
            logger.error(f"[{request_id}] Attempt {attempt}: Failed to generate meal details for {meal_type} on {day_name}.")
            continue  # Retry

        used_pantry_items = meal_details.get('used_pantry_items', [])
        logger.info(f"[{request_id}] Used pantry items: {used_pantry_items}")

        # Step B: Create the meal record
        meal_data = create_meal(
            user_id=user_id,
            name=meal_details.get('name'),
            dietary_preference=meal_details.get('dietary_preference'),
            description=meal_details.get('description'),
            meal_type=meal_type,
            used_pantry_items=used_pantry_items,
        )

        # Handle the "info" status if a similar meal was found
        if meal_data['status'] == 'info' and 'similar_meal_id' in meal_data:
            similar_meal_id = meal_data['similar_meal_id']
            try:
                meal = Meal.objects.get(id=similar_meal_id)
                offset = day_to_offset(day_name)
                meal_date = meal_plan.week_start_date + timedelta(days=offset)
                logger.info(f"[{request_id}] Similar meal '{meal.name}' already exists. Adding to meal plan.")
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

        # Step C: Verify the newly-created meal
        try:
            meal_id = meal_data['meal']['id']
            meal = Meal.objects.get(id=meal_id)
        except Meal.DoesNotExist:
            logger.error(f"[{request_id}] Meal with ID {meal_id} does not exist after creation.")
            continue  # Retry

        # Step D: Perform an optional sanity check
        sanity_ok = perform_openai_sanity_check(meal, user)
        if not sanity_ok:
            logger.warning(f"[{request_id}] Attempt {attempt}: Generated meal '{meal.name}' failed sanity check.")
            continue  # Retry

        # Step E: Actually attach the meal to the meal plan
        offset = day_to_offset(day_name)
        meal_date = meal_plan.week_start_date + timedelta(days=offset)

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
                        serving_size=user.preferred_servings,
                        request_id=request_id
                    )
                    logger.info(f"[{request_id}] Scheduled usage determination for pantry item '{item_name}'")
                else:
                    logger.warning(f"[{request_id}] Pantry item '{item_name}' not found for user {user.username}")

        # Step G: Update context for subsequent calls
        existing_meal_names.add(meal.name)
        existing_meal_embeddings.append(meal.meal_embedding)
        logger.info(f"[{request_id}] Added new meal '{meal.name}' for {day_name} {meal_type}.")

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
    user_context = generate_user_context(user)
    combined_allergies = set((user.allergies or []) + (user.custom_allergies or []))
    allergies_str = ', '.join(combined_allergies) if combined_allergies else 'None'
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that checks whether a meal has the possibility of including a user's allergens and meets their dietary preference. "
                        "If they do contain allergens or doesn't meet their requirements, you return 'False'. If they are allergen-free AND align with their preferences, you return 'True'."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Given the following user preferences: {user_context}. "
                        f"The user has the following allergies: {allergies_str}. "
                        f"The meal is called '{meal.name}' and is described as: {meal.description}. "
                        f"The dietary information about the meal are: {meal.dietary_preferences.all()} and/or {meal.custom_dietary_preferences.all()}. "
                    )
                }
            ],
            store=True,
            metadata={'tag': 'sanity_check'},
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    "name": "Sanity",
                    "schema": SanitySchema.model_json_schema()
                }
            }
        )

        gpt_output = response.choices[0].message.content
        allergen_check = json.loads(gpt_output).get('allergen_check', False)
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
    request_id=None
):
    """
    Generate meal details using OpenAI.
    
    Parameters:
    - user: The user to generate the meal for
    - meal_type: The type of meal (e.g., 'Breakfast', 'Lunch', 'Dinner')
    - existing_meal_names: Set of existing meal names to avoid duplicates
    - existing_meal_embeddings: List of existing meal embeddings for similarity checks
    - meal_plan: The MealPlan object
    - min_similarity: Minimum similarity threshold for duplicate detection
    - max_attempts: Maximum number of attempts to generate a valid meal
    - user_prompt: Optional user prompt to guide meal generation
    - request_id: Optional request ID for logging correlation
    
    Returns:
    - Dictionary with meal details or None if generation fails
    """
    # Generate a request ID if not provided
    if request_id is None:
        request_id = str(uuid.uuid4())

    previous_week_start = timezone.now().date() - timedelta(days=timezone.now().weekday() + 7)
    previous_week_end = previous_week_start + timedelta(days=6)

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

    # 3) Identify previous week's meals (to avoid duplicates)
    previous_meals = MealPlanMeal.objects.filter(
        meal_plan__user=user,
        meal_plan__week_start_date=previous_week_start,
        meal_plan__week_end_date=previous_week_end
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
    user_goals = getattr(user.goal, 'goal_description', 'None')

    # 5) Build the GPT prompt
    base_prompt = f"""
    You are a helpful meal-planning assistant.
    The user has expiring pantry items with these *effective* quantities:
    {expiring_items_str}.

    Requirements:
    1. Only use these expiring items if they make sense together.
    2. Do not invent additional pantry items not in the user's pantry.
    3. If an expiring item conflicts with user allergies, skip it.
    4. The meal must be realistic—avoid bizarre flavor combos.
    5. Return JSON with the MealOutputSchema format, including "used_pantry_items".
    6. Use at most 2 expiring items to avoid wild combos.
    """

    if user_prompt:
        base_prompt += f"""
        
        The user has specifically requested:
        {user_prompt}

        Make sure the generated meal satisfies these requirements while still meeting
        all dietary restrictions and preferences.
        """

    base_prompt += f"""
    Example JSON structure:
    {{
      "status": "success",
      "message": "Meal created successfully!",
      "current_time": "2023-10-05T10:00:00Z",
      "meal": {{
          "name": "Hearty Lentil Tomato Stew",
          "description": "...",
          "dietary_preference": "Everything",
          "meal_type": "{meal_type}",
          "used_pantry_items": ["lentils", "tomato sauce"]
      }}
    }}

    Now, generate a new meal that:
    - Is not too similar to: {', '.join(combined_meal_names)}
    - Meets the user's goal: {user_goals}
    - Avoids user allergies: {allergens_str}
    - Aligns with user preferences: {generate_user_context(user)}
    - Is served as: {meal_type}

    Begin!
    """

    # 6) Attempt up to max_attempts
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates a single meal JSON."},
                    {"role": "user", "content": base_prompt}
                ],
                store=True,
                metadata={'tag': 'meal_details'},
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        "name": "Meal",
                        "schema": MealOutputSchema.model_json_schema()
                    }
                }
            )

            gpt_output = response.choices[0].message.content
            meal_data = json.loads(gpt_output)

            meal_dict = meal_data.get('meal', {})
            meal_name = meal_dict.get('name')
            description = meal_dict.get('description')
            dietary_preference = meal_dict.get('dietary_preference')
            used_pantry_items = meal_dict.get('used_pantry_items', [])

            # Basic checks
            if not meal_name or not description or not dietary_preference:
                logger.error(f"[{request_id}] [Attempt {attempt+1}] Meal data incomplete: {meal_data}. Skipping.")
                continue

            meal_representation = (
                f"Name: {meal_name}, Description: {description}, "
                f"Dietary Preference: {dietary_preference}, Meal Type: {meal_type}, "
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
                logger.debug(f"[{request_id}] [Attempt {attempt+1}] Found a similar meal. Retrying.")
                continue

            # If no similarity found, we return the new meal data
            return {
                'name': meal_name,
                'description': description,
                'dietary_preference': dietary_preference,
                'meal_embedding': new_meal_embedding,
                'used_pantry_items': used_pantry_items
            }

        except Exception as e:
            logger.error(f"[{request_id}] [Attempt {attempt+1}] Error generating meal: {e}")
            return None

    logger.error(f"[{request_id}] Failed to generate a unique meal after {max_attempts} attempts.")
    return None


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
        "You are a helpful assistant that calculates how much of each used pantry item "
        "is needed for a meal, given the user's desired serving size. "
        "Return JSON in this form: "
        "[{\"item_name\": \"...\", \"quantity_used\": <float>, \"unit\": \"...\"}]."
    )

    user_msg = (
        f"Meal Name: '{meal_name}'\n"
        f"Description: {meal_description}\n"
        f"Serving size: {serving_size}\n"
        f"Items to use: {used_items_str}\n"
        f"User's dietary preferences: {combined_prefs}\n"
        "Only return usage for the items in used_pantry_info. "
        "If an item is not used, omit it. Also specify the unit (e.g., 'cans' or 'cups')."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            store=True,
            metadata={'tag': 'meal_usage'},
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "Meal",
                    "schema": UsageList.model_json_schema()
                }
            }
        )
        usage_json = response.choices[0].message.content
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