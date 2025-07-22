"""
Focus: Generating and managing instructions for bulk prep and daily tasks.
"""
import os
import json
import logging
import re
from django.shortcuts import get_object_or_404
import requests
import pytz
import textwrap
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from collections import defaultdict
from pydantic import ValidationError
from openai import OpenAI, OpenAIError
from meals.models import MealPlanMeal, MealPlan, MealPlanInstruction, Instruction, Meal
from meals.pydantic_models import Instructions as InstructionsSchema
from meals.serializers import MealPlanMealSerializer
from custom_auth.models import CustomUser
from shared.utils import generate_user_context, get_openai_client, build_age_safety_note
from meals.pantry_management import get_expiring_pantry_items
from meals.pydantic_models import BulkPrepInstructions, DailyTask
from django.template.loader import render_to_string
from meals.macro_info_retrieval import get_meal_macro_information
from meals.youtube_api_search import find_youtube_cooking_videos
import traceback
from .celery_utils import handle_task_failure

logger = logging.getLogger(__name__)


@shared_task
@handle_task_failure
def send_daily_meal_instructions():
    from meals.models import MealPlanMeal, MealPlan, MealPlanInstruction
    from meals.meal_assistant_implementation import MealPlanningAssistant

    # Get the current time in UTC
    current_utc_time = timezone.now()

    # Loop through all users who have not unsubscribed from emails
    users = CustomUser.objects.filter(unsubscribed_from_emails=False)

    for user in users:
        # Skip users who opted out of emails
        if user.unsubscribed_from_emails:
            continue
        # Convert current UTC time to the user's time zone
        try:
            user_timezone = pytz.timezone(user.timezone)
        except pytz.UnknownTimeZoneError:
            logger.error(f"Unknown timezone for user {user.email}: {user.timezone}")
            continue

        user_time = current_utc_time.astimezone(user_timezone)

        # # Check if it's 8 PM in the user's time zone
        if user_time.hour == 20:

            # Get the next day's date in the user's time zone
            next_day = user_time.date() + timedelta(days=1)
            next_day_name = next_day.strftime('%A')   # e.g. "Saturday"

            meal_plan_meals_for_next_day = MealPlanMeal.objects.filter(
                meal_plan__user=user,
                meal_plan__week_start_date__lte=next_day,
                meal_plan__week_end_date__gte=next_day,
                day=next_day_name
            )
            # Check one meal to see if meal plan is daily or bulk
            meal_plan = meal_plan_meals_for_next_day.first().meal_plan if meal_plan_meals_for_next_day.exists() else None
            
            if meal_plan is None:
                logger.info(f"No meal plan found for user {user.email} on {next_day_name}")
                continue
            if meal_plan.is_approved is False:
                logger.info(f"Meal plan for user {user.email} on {next_day_name} is not approved")
                continue
            if meal_plan.meal_prep_preference == 'daily':
                if meal_plan_meals_for_next_day.exists():
                    # Get the IDs of the MealPlanMeals for the next day
                    meal_plan_meal_ids = list(meal_plan_meals_for_next_day.values_list('id', flat=True))
                    generate_instructions.delay(meal_plan_meal_ids)
            elif meal_plan.meal_prep_preference == 'one_day_prep':
                # Check for follow-up instructions scheduled for next_day
                follow_up_instruction = MealPlanInstruction.objects.filter(
                    meal_plan=meal_plan,
                    date=next_day,
                    is_bulk_prep=False
                ).first()
            
                if follow_up_instruction:
                    instruction_text = follow_up_instruction.instruction_text
            
                    # Deserialize and validate the instruction_text
                    try:
                        instruction_data = json.loads(instruction_text)
                        # If instruction_data is a list, wrap it into a dictionary
                        if isinstance(instruction_data, list):
                            instruction_data = {
                                "day": next_day_name,
                                "tasks": instruction_data,
                                "total_estimated_time": None  # Set this appropriately if available
                            }
                        
                        daily_task = DailyTask.model_validate(instruction_data)
                    except Exception as e:
                        logger.error(f"Failed to parse follow-up instructions for user {user.email}: {e}")
                        continue
            
                    formatted_instructions = format_follow_up_instructions(daily_task, user.username)
            
                    # Send directly via in-app assistant instead of email
                    try:
                        formatted_message = f"Follow-up instructions for {next_day_name}:\n\n"
                        
                        # Format each task by meal type
                        tasks_by_meal_type = defaultdict(list)
                        for task in daily_task.tasks:
                            # Handle cases where task might not have meal_type attribute
                            meal_type = getattr(task, 'meal_type', 'Other')
                            tasks_by_meal_type[meal_type].append(task)
                        
                        meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack']
                        
                        for mt in meal_types_order:
                            tasks = tasks_by_meal_type.get(mt, [])
                            if tasks:
                                formatted_message += f"## {mt}\n"
                                for task in tasks:
                                    formatted_message += f"- {task.description}\n"
                                    if task.notes:
                                        formatted_message += f"  Note: {task.notes}\n"
                                formatted_message += "\n"
                        
                        assistant = MealPlanningAssistant(user_id=user.id)
                        result = MealPlanningAssistant.send_notification_via_assistant(
                            user_id=user.id,
                            message_content=formatted_message,
                            subject=f"Follow-up instructions for {next_day_name}"
                        )
                        if result:
                            logger.info(f"Follow-up instructions sent to MealPlanningAssistant for user {user.email}")
                        else:
                            logger.error(f"Failed to send follow-up instructions to MealPlanningAssistant for user {user.email}")
                    except Exception as e:
                        logger.error(
                            f"Failed to send follow-up instructions to MealPlanningAssistant for user {user.email}: {e}",
                            exc_info=True
                        )
                else:
                    logger.info(f"No follow-up instructions for user {user.email} on {next_day} for meal plan {meal_plan.id}")
            else:
                logger.info(f"No meals found for user {user.email} on {next_day_name}")

@shared_task
@handle_task_failure
def generate_instructions(meal_plan_meal_ids):
    """
    Generate cooking instructions for a list of MealPlanMeal IDs and send a consolidated email to the user.
    Includes fetching/generating macro info using existing functions.
    """
    logger.info(f"=== MEAL INSTRUCTIONS DEBUG: generate_instructions called for meal_plan_meal_ids={meal_plan_meal_ids}")
    
    from meals.models import MealAllergenSafety
    from meals.meal_assistant_implementation import MealPlanningAssistant
    if not isinstance(meal_plan_meal_ids, list):
        meal_plan_meal_ids = [meal_plan_meal_ids]  # Convert single ID to a list

    # Eagerly load related user and meal data
    meal_plan_meals = MealPlanMeal.objects.filter(id__in=meal_plan_meal_ids).select_related('meal_plan__user', 'meal')

    if not meal_plan_meals.exists():
        logger.error(f"No MealPlanMeals found for IDs: {meal_plan_meal_ids}")
        return

    # Assuming all meals belong to the same user and plan
    first_meal = meal_plan_meals.first()
    user = first_meal.meal_plan.user
    meal_plan = first_meal.meal_plan # Get the meal plan object
    user_email = user.email
    user_name = user.username

    # Import is_chef_meal function here to avoid circular imports
    from meals.meal_plan_service import is_chef_meal

    # Retrieve user preferences
    household_member_count = getattr(user, 'household_member_count', 1)
    user_preferred_language = user.preferred_language or 'English'

    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        # Ensure expiring_pantry_items is a list of strings (names) if needed by the prompt later
        expiring_items_str = ', '.join([item['name'] for item in expiring_pantry_items]) if expiring_pantry_items else 'None'
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
        expiring_items_str = 'None'

    try:
        user_context = generate_user_context(user)
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
        user_context = 'No additional user context provided.'

    instructions_list = []
    meals_to_update = [] # Keep track of meals with new metadata

    for meal_plan_meal in meal_plan_meals:
        meal = meal_plan_meal.meal
        meal_plan_meal_data = MealPlanMealSerializer(meal_plan_meal).data
        metadata_updated = False # Track if metadata was updated for *this* meal

        # --- Fetch/Generate Meal Metadata using existing functions ---
        # Macro Info
        if not meal.macro_info:
            logger.info(f"Macro info missing for meal {meal.id}. Attempting to fetch.")
            try:
                macro_data = get_meal_macro_information(meal) # Expects Meal object
                if macro_data:
                    # Assuming the function returns a dict/Pydantic model, convert to JSON string for storage
                    meal.macro_info = json.dumps(macro_data) if not isinstance(macro_data, str) else macro_data
                    metadata_updated = True
                    logger.info(f"Successfully fetched macro info for meal {meal.id}.")
                else:
                    logger.info(f"No macro info found/generated for meal {meal.id}.")
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})

        if metadata_updated:
            meals_to_update.append(meal) # Add meal to list for bulk update later
        # --- End Metadata Fetching ---

        # Check if meal is chef-created
        is_chef = is_chef_meal(meal)

        # Get substitution info (similar logic as before)
        substitution_info = []
        if not is_chef:
            # Logic to populate substitution_info based on MealAllergenSafety or variant status
            # (Keep existing logic for substitution_info here)
            # Example placeholder for substitution check:
            allergen_checks = MealAllergenSafety.objects.filter(meal=meal, user=user).exclude(substitutions__isnull=True).exclude(substitutions={})
            for check in allergen_checks:
                 if check.substitutions:
                     for original, subs in check.substitutions.items():
                         if subs:
                             substitution_info.append({'original': original, 'substitute': ', '.join(subs)})
            # Also check variant logic if applicable
            if getattr(meal, 'is_substitution_variant', False) and meal.base_meal:
                 # Add logic to find substitutions in variants
                 pass


        # Add age safety note
        age_note = build_age_safety_note(user)

        # Check for existing instructions first (Using the imported Instruction model)
        existing_instruction = Instruction.objects.filter(meal_plan_meal=meal_plan_meal).first()

        if existing_instruction:
            logger.info(f"Instructions already exist for MealPlanMeal ID {meal_plan_meal.id}. Using existing instructions.")
            instructions_content = existing_instruction.content
        else:
            # Generate instructions using OpenAI API
            try:
                meal_data_json = json.dumps(meal_plan_meal_data) # Serialize specific MealPlanMeal
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
                continue  # Skip this meal

            try:
                substitution_str = ""
                if substitution_info and not is_chef:
                    substitution_str = "Ingredient substitution information:\\\\n"
                    for sub in substitution_info:
                        substitution_str += f"- Replace {sub['original']} with {sub['substitute']}\\\\n"

                chef_note = ""
                if is_chef:
                    chef_note = "IMPORTANT: This is a chef-created meal and must be prepared exactly as specified. No ingredient substitutions are allowed."

                # --- Include Metadata (fetched or existing) in Prompt ---
                metadata_prompt_part = "\\\\n\\\\nAdditional Context:"
                macro_info_str = "Not available."
                video_info_str = "Not available."

                if meal.macro_info:
                    try:
                        # Attempt to parse if it's a JSON string, otherwise use as is
                        macro_data = json.loads(meal.macro_info) if isinstance(meal.macro_info, str) else meal.macro_info
                        macro_info_str = f"Calories: {macro_data.get('calories', 'N/A')}, Protein: {macro_data.get('protein', 'N/A')}g, Carbs: {macro_data.get('carbohydrates', 'N/A')}g, Fat: {macro_data.get('fat', 'N/A')}g. Serving: {macro_data.get('serving_size', 'N/A')}."
                    except (json.JSONDecodeError, TypeError, AttributeError) as e:
                        logger.warning(f"Could not parse macro_info for prompt display (meal {meal.id}): {e}")
                        macro_info_str = "Available but format unclear." # Or simply pass the raw string if safe: meal.macro_info
                metadata_prompt_part += f"\\\\n- Estimated Nutrition: {macro_info_str}"
                # --- End Metadata Prompt ---

                response = get_openai_client().responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {
                            "role": "developer",
                            "content":
                            (
                                f"## Mission\n"
                                f"You are **Sous‑Chef**, a multilingual culinary expert who writes crystal‑clear, "
                                "step‑by‑step cooking instructions.  You ALWAYS return a JSON object that "
                                "validates against the provided `Instructions` schema.  No prose or markdown. "
                                f"Write cooking instructions in **{user_preferred_language}**. "
                                f" **Age Safety Note**: {age_note or 'None'}\n\n"
                                f"## Data Available\n"
                                f"- **Meal data**: ingredients, methods, times.\n"
                                f"- **User context**: household ages, dietary needs, kitchen skill.\n"
                                f"- **Expiring pantry items**: {expiring_items_str} (use when sensible to cut waste).\n"
                                f"- **Metadata**: {metadata_prompt_part.strip()}\n\n"
                                f"## Output Rules\n"
                                f"1.  Return exactly one JSON object—nothing else—conforming to the `Instructions` "
                                f"   schema below (Pydantic `extra='forbid'`).\n"
                                f"2.  `steps` **must** be ordered; start numbering at **1**.\n"
                                f"3.  `description` ≤ 2 concise sentences; write in {user_preferred_language}.\n"
                                f"4.  `duration`: use value from meal data; if missing, write `'N/A'`.\n"
                                f"5.  Max total tokens ≈ 350 to avoid cost spikes.\n"
                                f"6.  Never repeat nutrition or video metadata inside `description`.\n"
                                f"7.  If you cannot comply, return `null`.\n\n"
                                f"### Instructions schema (immutable)\n"
                                f"{InstructionsSchema.model_json_schema()}"
                            )
                        },
                        {
                            "role": "user",
                            "content":
                            (
                                f"Generate the instructions now.\n\n"
                                f"- **Meal**: {meal_data_json}\n"
                                f"- **Household**: {user_context}\n"
                                f"- **Substitutions**: {substitution_str.strip()}\n"
                                f"- **Chef note**: {chef_note.strip()}\n"
                            )
                        }
                    ],
                    #store=True, # Consider if storing OpenAI requests is needed
                    #metadata={'tag': 'daily_instructions', 'meal_plan_meal_id': meal_plan_meal.id},
                    text={
                        "format": {
                        'type': 'json_schema',
                        'name': 'get_instructions',
                        'schema': InstructionsSchema.model_json_schema()
                        }
                    },
                    temperature=0.4,
                )

                instructions_content = response.output_text
                logger.info(f"Generated instructions for MealPlanMeal ID {meal_plan_meal.id}")

                # Save the newly generated instruction (Using the imported Instruction model)
                Instruction.objects.create(
                    meal_plan_meal=meal_plan_meal,
                    content=instructions_content,
                    # Add any other fields if your Instruction model requires them
                )

            except OpenAIError as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
                continue # Skip this meal
            except ValidationError as e:
                 # n8n traceback
                 n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                 requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
                 continue # Skip this meal
            except Exception as e:
                logger.error(f"Unexpected error generating instructions for MealPlanMeal ID {meal_plan_meal.id}: {e}", exc_info=True)
                continue # Skip this meal

        # Process and format the instructions (whether existing or new)
        try:
            instructions_dict = json.loads(instructions_content)
            # Validate with Pydantic
            validated_instructions = InstructionsSchema.model_validate(instructions_dict)

            # Format for email (keep existing HTML formatting logic)
            formatted_instructions = f"<div class='meal-instruction-block'><h4>{meal.name} ({meal_plan_meal.meal_type})</h4><table class='instruction-table'>"
            formatted_instructions += "<tr><th style='width:100px;'>Step</th><th>Description</th></tr>" # Table header

            for step in validated_instructions.steps:
                 step_number = step.step_number
                 step_description = step.description
                 duration = step.duration or "N/A"
                 # Format each step as a table row
                 formatted_instructions += f"<tr>"
                 formatted_instructions += f"<td style='vertical-align: top; padding: 5px; font-weight: bold;'>Step {step_number}</td>"
                 formatted_instructions += f"<td style='vertical-align: top; padding: 5px;'>{step_description}<br><small><i>Est. Time: {duration}</i></small></td>"
                 formatted_instructions += f"</tr>"

            formatted_instructions += "</table></div>"


            # Append the formatted instructions to the list for the email
            instructions_list.append({
                'meal_name': meal.name,
                'formatted_instructions': formatted_instructions,
                'macro_info': meal.macro_info, # Add raw macro info string
                'meal_id': meal_plan_meal.id, # Keep original meal_plan_meal id
                'meal_plan_id': meal_plan.id,
                'meal_type': meal_plan_meal.meal_type,
                'meal_date': meal_plan_meal.meal_date, # Use the date from MealPlanMeal
            })
        except (json.JSONDecodeError, ValidationError) as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})


    # --- Bulk update meals with new metadata ---
    if meals_to_update:
        try:
            # Ensure unique meals are updated if a meal appears multiple times in meal_plan_meals
            unique_meals_to_update = {m.id: m for m in meals_to_update}.values()
            Meal.objects.bulk_update(list(unique_meals_to_update), ['macro_info'])
            logger.info(f"Bulk updated metadata for {len(unique_meals_to_update)} meals.")
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
    # --- End bulk update ---

    if not instructions_list:
        logger.info(f"No instructions generated or formatted for user {user_email}")
        return


    meal_dates = set(item['meal_date'] for item in instructions_list if item['meal_date'] is not None)
    # Determine the subject line based on the dates of the meals
    if len(meal_dates) == 1:
        # All meals are on the same date
        meal_date = meal_dates.pop()
        meal_day_of_week = meal_date.strftime('%A')  # e.g., 'Sunday'
        subject = f"Your Cooking Instructions for {meal_day_of_week}'s Meals"
    else:
        # Meals are on different dates
        current_user_time = timezone.now().astimezone(pytz.timezone(user.timezone))
        current_date_str = current_user_time.strftime('%A %B %d')
        subject = f"Your Requested Cooking Instructions for {current_date_str}"


    # Group instructions by meal type
    grouped_instructions = defaultdict(list)
    for item in instructions_list:
        meal_type = item['meal_type']
        grouped_instructions[meal_type].append(item)

    # Define the order of meal types
    meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other']  # Add any other meal types as needed

    # Pre-resolve and store in a new variable
    ordered_meals = []
    for mt in meal_types_order:
        meals = grouped_instructions.get(mt, [])
        ordered_meals.append((mt, meals))

    # Get current meal plan
    meal_plan = first_meal.meal_plan
    # Get approval token
    approval_token = meal_plan.approval_token
    # Build context for the template
    streamlit_url = os.getenv("STREAMLIT_URL") 
    context = {
        'subject': subject,
        'user_name': user_name,
        'ordered_meals': ordered_meals,
        'profile_url': f"{streamlit_url}/profile",
        'streamlit_url': streamlit_url,
        'user_id': user.id,
        'approval_token': approval_token,
    }

    # --- Send via in-app assistant instead of email ---
    instructions_message_parts = [subject, ""]  # top-line heading

    for meal_type, meals in ordered_meals:
        if not meals:
            continue
        instructions_message_parts.append(f"## {meal_type}")
        for item in meals:
            # Strip HTML so GPT chat shows plain text
            text_only = re.sub(r"<[^>]+>", "", item["formatted_instructions"])
            instructions_message_parts.append(text_only)
        instructions_message_parts.append("")      # blank line between sections

    message_content = "\n".join(instructions_message_parts)

    try:
        assistant = MealPlanningAssistant(user_id=user.id)
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_content,
            subject=subject
        )
        if result:
            logger.info(f"Daily meal instructions sent to MealPlanningAssistant for user {user_email}")
        else:
            logger.error(f"Failed to send daily meal instructions to MealPlanningAssistant for user {user_email}")
    except Exception as e:
        logger.error(
            f"Failed to send instructions to MealPlanningAssistant for user {user_email}: {e}",
            exc_info=True,
        )

@shared_task
@handle_task_failure
def generate_bulk_prep_instructions(meal_plan_id):
    """
    Generate bulk meal prep instructions for a given meal plan.
    """
    logger.info(f"=== MEAL INSTRUCTIONS DEBUG: generate_bulk_prep_instructions called for meal_plan_id={meal_plan_id}")
    print(f"=== MEAL INSTRUCTIONS DEBUG: generate_bulk_prep_instructions called for meal_plan_id={meal_plan_id}")
    print(f"=== MEAL INSTRUCTIONS DEBUG: THIS IS NOT THE EMERGENCY PANTRY PLAN FUNCTION!")
    logger.info(f"MEAL INSTRUCTIONS DEBUG: THIS IS NOT THE EMERGENCY PANTRY PLAN FUNCTION!")

    from meals.models import Meal, MealPlan, MealPlanMeal, MealPlanInstruction, PantryItem
    from django.db import transaction
    from collections import defaultdict
    import uuid
    from meals.pydantic_models import BulkPrepInstructions
    import json
    import requests
    import os

    from meals.models import MealPlan, MealPlanInstruction, MealAllergenSafety, Ingredient, Meal, MealPlanMeal
    from meals.serializers import MealPlanSerializer
    from meals.meal_assistant_implementation import MealPlanningAssistant

    # Import is_chef_meal function here to avoid circular imports
    from meals.meal_plan_service import is_chef_meal
    # Import metadata functions
    from meals.macro_info_retrieval import get_meal_macro_information

    logger.info(f"Starting bulk prep generation for MealPlan ID: {meal_plan_id}")
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)
    user = meal_plan.user

    # Check if instructions already exist
    existing_instructions = MealPlanInstruction.objects.filter(
        meal_plan=meal_plan,
        is_bulk_prep=True
    ).first()

    if existing_instructions:
        logger.info(f"Bulk prep instructions already exist for meal plan {meal_plan_id}. Skipping generation.")
        # Optionally: trigger the email send task if instructions exist but weren't sent?
        # send_bulk_prep_instructions.delay(meal_plan_id)
        return

    # Get all MealPlanMeal objects for this meal plan
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
    if not meal_plan_meals.exists():
        logger.warning(f"No meals found for MealPlan ID {meal_plan_id}. Cannot generate bulk prep.")
        return

    # Get full serialized data of the MealPlan (might be needed for overall context)
    # serializer = MealPlanSerializer(meal_plan)
    # meal_plan_data = serializer.data

    # Get user preferences
    household_member_count = getattr(user, 'household_member_count', 1)
    user_preferred_language = user.preferred_language or 'English'

    # --- Collect Metadata and Substitution Info for ALL meals --- 
    all_meals_data_for_prompt = []
    substitution_info = []
    chef_meals_present = False
    meals_to_update = [] # Track meals needing metadata save

    for meal_plan_meal in meal_plan_meals:
        meal = meal_plan_meal.meal
        is_chef = is_chef_meal(meal)
        if is_chef:
            chef_meals_present = True

        # --- Fetch/Generate Metadata using existing functions ---
        metadata_updated = False
        # Macro Info
        if not meal.macro_info:
            logger.info(f"Macro info missing for bulk prep meal {meal.id}. Attempting fetch.")
            try:
                macro_data = get_meal_macro_information(meal)
                if macro_data:
                    meal.macro_info = json.dumps(macro_data) if not isinstance(macro_data, str) else macro_data
                    metadata_updated = True
                    logger.info(f"Successfully fetched macro info for bulk prep meal {meal.id}.")
            except Exception as e:
                logger.error(f"Error fetching macro info for bulk prep meal {meal.id}: {e}", exc_info=True)
        if metadata_updated:
            # Add the meal object itself, not just ID, for bulk_update
            meals_to_update.append(meal)
        # --- End Metadata Fetching ---

        # Append meal data along with its metadata for the main prompt
        # Make sure to use the potentially updated meal.macro_info and meal.youtube_videos
        meal_info_for_prompt = {
            "day": meal_plan_meal.day,
            "meal_type": meal_plan_meal.meal_type,
            "name": meal.name,
            "description": meal.description or "",
            "is_chef_meal": is_chef,
            "macro_info": meal.macro_info, # Use the potentially updated field
            # TODO: Add ingredients list here if needed by the prompt
            # "ingredients": [ing.name for dish in meal.dishes.all() for ing in dish.ingredients.all()]
        }
        all_meals_data_for_prompt.append(meal_info_for_prompt)

        # Collect Substitution Info (only for non-chef meals)
        if not is_chef:
            # (Keep existing logic for collecting substitution_info here)
            # Based on MealAllergenSafety
            allergen_checks = MealAllergenSafety.objects.filter(meal=meal, user=user).exclude(substitutions__isnull=True).exclude(substitutions={})
            for check in allergen_checks:
                 if check.substitutions:
                     for original, subs in check.substitutions.items():
                         if subs:
                             substitution_info.append({
                                 'meal_name': meal.name,
                                 'original': original,
                                 'substitute': ', '.join(subs),
                                 'notes': f"For {meal.name}, replace {original} with {', '.join(subs)}"
                             })
            # Based on variant status
            if getattr(meal, 'is_substitution_variant', False) and meal.base_meal:
                 for dish in meal.dishes.all():
                    for ingredient in dish.ingredients.all():
                        if getattr(ingredient, 'is_substitution', False) and getattr(ingredient, 'original_ingredient', None):
                            substitution_info.append({
                                'meal_name': meal.name,
                                'original': ingredient.original_ingredient,
                                'substitute': ingredient.name,
                                'notes': f"For {meal.name}, use {ingredient.name} instead of {ingredient.original_ingredient}"
                            })
    # --- End Data Collection Loop ---

    # --- Bulk update meals with new metadata ---
    if meals_to_update:
        try:
            # Ensure unique meals are updated
            unique_meals_to_update = {m.id: m for m in meals_to_update}.values()
            Meal.objects.bulk_update(list(unique_meals_to_update), ['macro_info'])
            logger.info(f"Bulk updated metadata for {len(meals_to_update)} meals during bulk prep generation.")
        except Exception as e:
            logger.error(f"Error bulk updating meal metadata during bulk prep generation: {e}", exc_info=True)
    # --- End bulk update ---


    # Get expiring pantry items
    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        expiring_items_str = ', '.join(item['name'] for item in expiring_pantry_items) if expiring_pantry_items else 'None'
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
        expiring_items_str = 'None'

    # Generate the user context
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
        user_context = 'No additional user context provided.'

    # Add age safety note
    age_note = build_age_safety_note(user)


    try:
        # Format substitution information for prompt
        substitution_str = ""
        if substitution_info:
            substitution_str = "\\\\n\\\\nIngredient substitution information (apply ONLY to non-chef meals):\\\\n"
            # Use a set to avoid duplicate notes
            unique_notes = {sub['notes'] for sub in substitution_info}
            for note in unique_notes:
                substitution_str += f"- {note}\\\\n"

        ###########################################
        # BUILD THE CHAT MESSAGES
        ###########################################

        # -- sanity‑checked variables ------------
        user_lang   = user_preferred_language or "English"
        meals_json  = json.dumps(all_meals_data_for_prompt, ensure_ascii=False)
        subs_text   = build_substitution_bullets(substitution_info)   # helper returns '' if none
        meta_part   = build_metadata_prompt_part(meal_plan_meals)
        chef_text   = ("\nIMPORTANT: Some meals are chef‑created and MUST NOT be altered."
                    if chef_meals_present else "")
        # ----------------------------------------

        messages = [
            {
                "role": "developer",
                "content": (
                    f"You are **Batch‑Chef**, a multilingual bulk‑meal‑prep specialist. "
                    f"Return ONE JSON object matching the `BulkPrepInstructions` schema. "
                    f"No markdown, no explanations. "
                    f" **Age Safety Note**: {age_note or 'None'}. "
                    f"## Objective\nPrepare a one‑session bulk‑prep plan in **{user_lang}**.\n\n"

                    f"## Data\n"
                    f"- Weekly meals JSON:\n```json\n{meals_json}\n```\n"
                    f"- Household context: {user_context} (diners={household_member_count})\n"
                    f"- Expiring items: {expiring_items_str}\n"
                    f"- Metadata: {meta_part}\n\n"

                    f"## Rules\n"
                    f"1. Output fields: `bulk_prep_steps` then `daily_tasks`, both ordered by `step_number`.\n"
                    f"2. Group like operations (e.g., chop all veg) before cooking grains/proteins.\n"
                    f"3. Hot foods must cool to ≤40 °F/4 °C within 2 h before storage. "
                    f"4. Storage `notes`: fridge ≤4 days; freezer ≤3 months. "
                    f"5. Each `description` ≤2 concise sentences in {user_lang}.\n"
                    f"6. Use provided durations or `'N/A'`.\n"
                    f"7. Never repeat nutrition/video metadata.\n"
                    f"8. If you cannot comply, output `null`.\n"
                    f"9. Keep total tokens ≈400; be terse.\n\n"

                    f"## Extras\n{subs_text}{chef_text}"
                )
            },
            {
                "role": "user",
                "content": (
                    "Generate the bulk‑prep plan now. Remember: nutrition/video info is context only."
                )
            }
        ]
        # Generate the bulk prep instructions using OpenAI
        response = get_openai_client().responses.create(
            model="gpt-4.1-mini", # Or gpt-4-turbo if more complexity needed
            input=messages,
            text={
                "format": {
                'type': 'json_schema',
                'name': 'bulk_prep_instructions',
                'schema': BulkPrepInstructions.model_json_schema()
                }
            }
        )

        # Check if the response was successful
        if response and response.output_text:
            generated_instructions_text = response.output_text
            # Create a new MealPlanInstruction
            MealPlanInstruction.objects.update_or_create(
                meal_plan=meal_plan,
                is_bulk_prep=True,
                defaults={
                    'instruction_text': generated_instructions_text,
                    'date': meal_plan.week_start_date
                }
            )
            logger.info(f"Generated bulk prep instructions for meal plan {meal_plan_id}")
            
            # Notify the user in-app that bulk-prep instructions are ready
            try:
                assistant = MealPlanningAssistant(user_id=user.id)
                
                # Parse the instructions for context
                try:
                    instruction_data = json.loads(generated_instructions_text)
                    validated_prep = BulkPrepInstructions.model_validate(instruction_data)
                    
                    # Format bulk prep steps
                    bulk_prep_steps = validated_prep.bulk_prep_steps
                    daily_tasks = validated_prep.daily_tasks
                    
                    # Format the steps by meal type
                    steps_formatted = ""
                    steps_by_meal_type = defaultdict(list)
                    
                    for step in bulk_prep_steps:
                        steps_by_meal_type[step.meal_type].append(step)
                    
                    meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other']
                    
                    for meal_type in meal_types_order:
                        steps = steps_by_meal_type.get(meal_type, [])
                        if steps:
                            # Filter out steps with empty descriptions before numbering
                            non_empty_steps = [step for step in steps if step and step.description and step.description.strip()]
                            if non_empty_steps:
                                steps_formatted += f"\n{meal_type} Prep:\n"
                                for i, step in enumerate(non_empty_steps, 1):
                                    steps_formatted += f"{i}. {step.description}\n"
                                    if step.notes:
                                        steps_formatted += f"   Note: {step.notes}\n"
                    
                    # Format the daily tasks by day
                    daily_tasks_formatted = ""
                    tasks_by_day = defaultdict(list)
                    
                    for task in daily_tasks:
                        tasks_by_day[task.day].append(task)
                    
                    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    start_day_index = meal_plan.week_start_date.weekday()
                    ordered_days = [(start_day_index + i) % 7 for i in range(7)]
                    ordered_day_names = [day_names[i] for i in ordered_days]
                    
                    for day_name in ordered_day_names:
                        daily_tasks_for_day = tasks_by_day.get(day_name, [])
                        if daily_tasks_for_day:
                            daily_tasks_formatted += f"\n{day_name}:\n"
                            for daily_task in daily_tasks_for_day:
                                # Each daily_task has a list of task steps
                                for task_step in daily_task.tasks:
                                    if task_step.description and task_step.description.strip():
                                        daily_tasks_formatted += f"- {task_step.meal_type}: {task_step.description}\n"
                                        if task_step.notes:
                                            daily_tasks_formatted += f"  Note: {task_step.notes}\n"
                    
                    # Create detailed message with full context
                    message_content = (
                        f"Your bulk meal-prep instructions for the week of "
                        f"{meal_plan.week_start_date.strftime('%B %d')} - {meal_plan.week_end_date.strftime('%B %d')} are ready!\n\n"
                        f"Here are the bulk preparation steps you should complete:\n{steps_formatted}\n\n"
                        f"And here are the follow-up tasks for each day of the week:\n{daily_tasks_formatted}\n\n"
                        f"This will help you save time during the week by preparing multiple meals at once."
                    )
                    
                except Exception as e:
                    # Fallback to simple notification if parsing fails
                    # n8n traceback
                    n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                    requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
                    message_content = (
                        "Your bulk meal-prep instructions for the upcoming week are ready! "
                        "Open the chat to review them."
                    )
                
                result = MealPlanningAssistant.send_notification_via_assistant(
                    user_id=user.id,
                    message_content=message_content,
                    subject=f"Bulk Meal Prep Instructions for {meal_plan.week_start_date.strftime('%B %d')} - {meal_plan.week_end_date.strftime('%B %d')}"
                )
                if result:
                    logger.info(
                        f"Bulk-prep notification sent to MealPlanningAssistant for user {user.email}"
                    )
                else:
                    logger.error(
                        f"Failed to send bulk-prep notification to MealPlanningAssistant for user {user.email}"
                    )
            except Exception as e:
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                requests.post(n8n_traceback_url, json={"error": str(e), "source":"generate_instructions", "traceback": traceback.format_exc()})
            
            # Send an email with the bulk prep instructions
            send_bulk_prep_instructions.delay(meal_plan_id)
        else:
            logger.error(f"Failed to generate bulk prep instructions for meal plan {meal_plan_id}")
    
    except Exception as e:
        logger.error(f"Error generating bulk prep instructions for meal plan {meal_plan_id}: {str(e)}")

def build_substitution_bullets(subs):
    if not subs:
        return ""
    bullets = "\nIngredient substitutions for non‑chef meals:\n"
    seen = set()
    for s in subs:
        if s["notes"] not in seen:
            bullets += f"- {s['notes']}\n"
            seen.add(s["notes"])
    return bullets

@shared_task
@handle_task_failure
def send_bulk_prep_instructions(meal_plan_id):
    """
    Send a generated bulk prep instructions to the user via the meal planning assistant.
    """
    from meals.models import MealPlan, MealPlanInstruction
    from meals.meal_assistant_implementation import MealPlanningAssistant
    
    try:
        # Get the meal plan and bulk prep instruction
        meal_plan = MealPlan.objects.get(id=meal_plan_id)
        user = meal_plan.user
        
        # Skip if user has opted out of emails
        if user.unsubscribed_from_emails:
            logger.info(f"User {user.email} has unsubscribed from emails.")
            return {"status": "skipped", "reason": "user_opted_out"}
        
        # Get the instruction text from the database
        instruction = MealPlanInstruction.objects.filter(meal_plan=meal_plan, is_bulk_prep=True).first()
        if not instruction or not instruction.instruction_text:
            logger.error(f"No bulk prep instructions found for meal plan {meal_plan_id}")
            return {"status": "error", "reason": "no_instructions_found"}
        
        # Parse the instruction text as JSON
        try:
            instruction_data = json.loads(instruction.instruction_text)
            validated_prep = BulkPrepInstructions.model_validate(instruction_data)
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_bulk_prep_instructions", "traceback": traceback.format_exc()})
            return {"status": "error", "reason": f"invalid_instruction_format: {str(e)}"}
        
        # Format bulk prep steps
        bulk_prep_steps = validated_prep.bulk_prep_steps
        daily_tasks = validated_prep.daily_tasks
        
        # Format the steps by meal type
        steps_formatted = ""
        steps_by_meal_type = defaultdict(list)
        
        for step in bulk_prep_steps:
            steps_by_meal_type[step.meal_type].append(step)
        
        meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other']
        
        for meal_type in meal_types_order:
            steps = steps_by_meal_type.get(meal_type, [])
            if steps:
                # Filter out steps with empty descriptions before numbering
                non_empty_steps = [step for step in steps if step and step.description and step.description.strip()]
                if non_empty_steps:
                    steps_formatted += f"\n{meal_type} Prep:\n"
                    for i, step in enumerate(non_empty_steps, 1):
                        steps_formatted += f"{i}. {step.description}\n"
                        if step.notes:
                            steps_formatted += f"   Note: {step.notes}\n"
        
        # Format the daily tasks by day
        daily_tasks_formatted = ""
        tasks_by_day = defaultdict(list)
        
        for task in daily_tasks:
            tasks_by_day[task.day].append(task)
        
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        start_day_index = meal_plan.week_start_date.weekday()
        ordered_days = [(start_day_index + i) % 7 for i in range(7)]
        ordered_day_names = [day_names[i] for i in ordered_days]
        
        for day_name in ordered_day_names:
            daily_tasks_for_day = tasks_by_day.get(day_name, [])
            if daily_tasks_for_day:
                daily_tasks_formatted += f"\n{day_name}:\n"
                for daily_task in daily_tasks_for_day:
                    # Each daily_task has a list of task steps
                    for task_step in daily_task.tasks:
                        if task_step.description and task_step.description.strip():
                            daily_tasks_formatted += f"- {task_step.meal_type}: {task_step.description}\n"
                            if task_step.notes:
                                daily_tasks_formatted += f"  Note: {task_step.notes}\n"
        
        # Format the message for the assistant
        message_to_assistant = (
            f"I need to send bulk meal prep instructions to the user for the week of "
            f"{meal_plan.week_start_date.strftime('%B %d')} - {meal_plan.week_end_date.strftime('%B %d')}.\n\n"
            f"Here are the bulk preparation steps they should complete:\n{steps_formatted}\n\n"
            f"And here are the follow-up tasks for each day of the week:\n{daily_tasks_formatted}\n\n"
            f"Please format this information into a friendly email with clear and well-organized instructions. "
            f"Start with an introduction about how doing this bulk prep will save them time during the week. "
            f"Then organize the bulk prep steps clearly by meal type, followed by the daily tasks organized by day."
        )
        
        # Send via the assistant
        subject = f"Your Bulk Meal Prep Instructions for {meal_plan.week_start_date.strftime('%b %d')} - {meal_plan.week_end_date.strftime('%b %d')}"
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message_to_assistant,
            subject=subject
        )
        
        if result.get('status') == 'success':
            logger.info(f"Bulk prep instructions email sent via assistant for meal plan {meal_plan_id}")
        else:
            logger.error(f"Failed to send bulk prep instructions email for meal plan {meal_plan_id}: {result}")
            
        return result
            
    except MealPlan.DoesNotExist:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": "Meal plan with ID {meal_plan_id} not found", "source":"send_bulk_prep_instructions", "traceback": traceback.format_exc()})
        return {"status": "error", "reason": "meal_plan_not_found"}
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_bulk_prep_instructions", "traceback": traceback.format_exc()})
        traceback.print_exc()
        return {"status": "error", "reason": str(e)}

def format_follow_up_instructions(daily_task: DailyTask, user_name: str):
    from collections import defaultdict

    # Group tasks by meal_type
    tasks_by_meal_type = defaultdict(list)
    for task in daily_task.tasks:
        # Handle cases where task might not have meal_type attribute
        meal_type = getattr(task, 'meal_type', 'Other')
        tasks_by_meal_type[meal_type].append(task)

    # Define meal type order and colors
    meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack']
    meal_type_colors = {
        'Breakfast': '#F7D9AE',
        'Lunch': '#CDE4B9',
        'Dinner': '#B9D6E4',
        'Snack': '#E4B9D3'
    }

    meal_types_context = []
    for mt in meal_types_order:
        meal_types_context.append({
            'meal_type': mt,
            'bg_color': meal_type_colors.get(mt, '#f0f0f0'),
            'tasks': tasks_by_meal_type.get(mt, [])
        })

    # Return a context dictionary for the template
    context = {
        'user_name': user_name,
        'daily_task': daily_task,
        'meal_types': meal_types_context
    }
    return context

def send_follow_up_email(user, daily_task_context):
    from meals.meal_assistant_implementation import MealPlanningAssistant
    # Create a formatted message for the assistant
    daily_task = daily_task_context['daily_task']
    
    # Format tasks by meal type
    meal_types = daily_task_context['meal_types']
    tasks_formatted = ""
    
    for meal_type_info in meal_types:
        meal_type = meal_type_info['meal_type']
        tasks = meal_type_info['tasks']
        
        if tasks:
            tasks_formatted += f"\n{meal_type}:\n"
            for task in tasks:
                tasks_formatted += f"- {task.description}\n"
                if task.notes:
                    tasks_formatted += f"  Note: {task.notes}\n"
    
    # Format the message for the assistant
    message_to_assistant = (
        f"I need to send follow-up cooking instructions to the user for {daily_task.day}. Here are the tasks they need to complete:\n\n"
        f"{tasks_formatted}\n\n"
        f"Please format this information into a friendly email with clear and well-organized cooking instructions. "
        f"Feel free to add your own tips or suggestions to make the cooking process easier."
    )
    
    # Send via assistant
    subject = f"Your Follow-Up Instructions for {daily_task.day}"
    result = MealPlanningAssistant.send_notification_via_assistant(
        user_id=user.id,
        message_content=message_to_assistant,
        subject=subject
    )
    
    if result.get('status') == 'success':
        logger.info(f"Follow-up instructions email sent via assistant for user {user.id}")
    else:
        logger.error(f"Failed to send follow-up instructions email for user {user.id}: {result}")
        
    return result
        
@shared_task
@handle_task_failure
def send_follow_up_instructions(meal_plan_id):
    from django.utils import timezone
    from meals.models import MealPlanInstruction, MealPlan
    from meals.meal_assistant_implementation import MealPlanningAssistant
    meal_plan = MealPlan.objects.get(id=meal_plan_id)
    instructions = MealPlanInstruction.objects.filter(meal_plan=meal_plan, is_bulk_prep=False)
    user = meal_plan.user

    for instruction in instructions:
        instruction_text = instruction.instruction_text
        try:
            instruction_data = json.loads(instruction_text)
            daily_task = DailyTask.model_validate(instruction_data)
            
            # Format task details
            tasks_by_meal_type = defaultdict(list)
            for task in daily_task.tasks:
                # Handle cases where task might not have meal_type attribute
                meal_type = getattr(task, 'meal_type', 'Other')
                tasks_by_meal_type[meal_type].append(task)
            
            formatted_message = f"Follow-up instructions for {daily_task.day}:\n\n"
            meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack']
            
            for mt in meal_types_order:
                tasks = tasks_by_meal_type.get(mt, [])
                if tasks:
                    formatted_message += f"## {mt}\n"
                    for task in tasks:
                        formatted_message += f"- {task.description}\n"
                        if task.notes:
                            formatted_message += f"  Note: {task.notes}\n"
                    formatted_message += "\n"
            
            # Send directly via in-app assistant
            assistant = MealPlanningAssistant(user_id=user.id)
            result = MealPlanningAssistant.send_notification_via_assistant(
                user_id=user.id,
                message_content=formatted_message,
                subject=f"Follow-up instructions for {daily_task.day}"
            )
            if result:
                logger.info(f"Follow-up instructions sent to MealPlanningAssistant for user {user.id}")
            else:
                logger.error(f"Failed to send follow-up instructions to MealPlanningAssistant for user {user.id}")
            
        except Exception as e:
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            requests.post(n8n_traceback_url, json={"error": str(e), "source":"send_follow_up_instructions", "traceback": traceback.format_exc()})
            continue

def build_metadata_prompt_part(meal_plan_meals):
    """
    Collect lightweight, plan‑level metadata for the LLM.
    Returns a pretty‑printed JSON string or an empty string.
    """
    rollup = {
        "total_meals": len(meal_plan_meals),
        "meals_with_macro_data": 0,
        "meals_without_macro_data": 0,
        "macro_summary": {
            "protein": 0,
            "carbohydrates": 0,
            "fat": 0,
            "calories": 0,
        },
        "videos_present": False,
    }

    for mpm in meal_plan_meals:
        meal = mpm.meal
        # macro_info assumed to be JSON str → dict
        if meal.macro_info:
            try:
                macros = json.loads(meal.macro_info) if isinstance(meal.macro_info, str) else meal.macro_info
                # Use the correct field names from the MealMacroInfo schema
                rollup["macro_summary"]["protein"] += macros.get("protein", 0)
                rollup["macro_summary"]["carbohydrates"] += macros.get("carbohydrates", 0)
                rollup["macro_summary"]["fat"] += macros.get("fat", 0)
                rollup["macro_summary"]["calories"] += macros.get("calories", 0)
                rollup["meals_with_macro_data"] += 1
            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                logger.warning(f"Could not parse macro_info for meal {meal.id}: {e}")
                rollup["meals_without_macro_data"] += 1
                continue
        else:
            rollup["meals_without_macro_data"] += 1

        if meal.youtube_videos:
            rollup["videos_present"] = True

    # If no meals have macro data, indicate that clearly
    if rollup["meals_with_macro_data"] == 0:
        rollup["macro_summary"] = "No macro data available for any meals"
    elif rollup["meals_without_macro_data"] > 0:
        rollup["macro_summary"]["note"] = f"Summary based on {rollup['meals_with_macro_data']} of {rollup['total_meals']} meals"

    return json.dumps(rollup, ensure_ascii=False, indent=2)