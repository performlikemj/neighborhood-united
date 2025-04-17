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
from shared.utils import generate_user_context
from meals.pantry_management import get_expiring_pantry_items
from meals.pydantic_models import BulkPrepInstructions, DailyTask
from django.template.loader import render_to_string
from meals.macro_info_retrieval import get_meal_macro_information
from meals.youtube_api_search import find_youtube_cooking_videos

logger = logging.getLogger(__name__)

OPENAI_API_KEY = settings.OPENAI_KEY
client = OpenAI(api_key=OPENAI_API_KEY)


@shared_task
def send_daily_meal_instructions():
    from meals.models import MealPlanMeal, MealPlan, MealPlanInstruction

    # Get the current time in UTC
    current_utc_time = timezone.now()

    # Loop through all users who have email_daily_instructions enabled
    users = CustomUser.objects.filter(email_daily_instructions=True)

    for user in users:
        # Skip users who opted out of daily instructions
        if not user.email_daily_instructions:
            continue
        # Convert current UTC time to the user's time zone
        try:
            user_timezone = pytz.timezone(user.timezone)
        except pytz.UnknownTimeZoneError:
            logger.error(f"Unknown timezone for user {user.email}: {user.timezone}")
            continue

        user_time = current_utc_time.astimezone(user_timezone)

        # # # Check if it's 8 PM in the user's time zone
        # if user_time.hour == 20 and user_time.minute == 0:

        #     # Get the next day's date in the user's time zone
        #     next_day = user_time.date() + timedelta(days=1)
        #     next_day_name = next_day.strftime('%A')

        #     # Get the current week start and end dates
        #     week_start_date = next_day - timedelta(days=next_day.weekday())
        #     week_end_date = week_start_date + timedelta(days=6)


        #     # Filter MealPlanMeal instances for this user, day, and week
        #     meal_plan_meals_for_next_day = MealPlanMeal.objects.filter(
        #         meal_plan__user=user,
        #         day=next_day_name,
        #         meal_plan__week_start_date=week_start_date,
        #         meal_plan__week_end_date=week_end_date,
        #     )
            
        #     # Check one meal to see if meal plan is daily or bulk
        #     meal_plan = meal_plan_meals_for_next_day.first().meal_plan if meal_plan_meals_for_next_day.exists() else None
            
        #     if meal_plan is None:
        #         logger.info(f"No meal plan found for user {user.email} on {next_day_name}")
        #         continue
        #     if meal_plan.is_approved is False:
        #         logger.info(f"Meal plan for user {user.email} on {next_day_name} is not approved")
        #         continue
        #     if meal_plan.meal_prep_preference == 'daily':
        #         print(f'Daily meal plan for user {user.email} on {next_day_name}')
        #         if meal_plan_meals_for_next_day.exists():
        #             # Get the IDs of the MealPlanMeals for the next day
        #             meal_plan_meal_ids = list(meal_plan_meals_for_next_day.values_list('id', flat=True))
        #             logger.debug(f"MealPlanMeal IDs for user {user.email} on {next_day_name}: {meal_plan_meal_ids}")
        #             generate_instructions.delay(meal_plan_meal_ids)
        #     elif meal_plan.meal_prep_preference == 'one_day_prep':
        #         print(f'One day prep meal plan for user {user.email} on {next_day_name}')
        #         # Check for follow-up instructions scheduled for next_day
        #         follow_up_instruction = MealPlanInstruction.objects.filter(
        #             meal_plan=meal_plan,
        #             date=next_day,
        #             is_bulk_prep=False
        #         ).first()
            
        #         if follow_up_instruction:
        #             instruction_text = follow_up_instruction.instruction_text
            
        #             # Deserialize and validate the instruction_text
        #             try:
        #                 instruction_data = json.loads(instruction_text)
        #                 print(f"Instruction data: {instruction_data}")
        #                 # If instruction_data is a list, wrap it into a dictionary
        #                 if isinstance(instruction_data, list):
        #                     instruction_data = {
        #                         "day": next_day_name,
        #                         "tasks": instruction_data,
        #                         "total_estimated_time": None  # Set this appropriately if available
        #                     }
                        
        #                 daily_task = DailyTask.model_validate(instruction_data)
        #                 print(f"Daily task: {daily_task}")
        #             except Exception as e:
        #                 logger.error(f"Failed to parse follow-up instructions for user {user.email}: {e}")
        #                 continue
            
        #             formatted_instructions = format_follow_up_instructions(daily_task, user.username)
            
        #             send_follow_up_email(user, formatted_instructions)
        #         else:
        #             logger.info(f"No follow-up instructions for user {user.email} on {next_day} for meal plan {meal_plan.id}")
        #     else:
        #         logger.info(f"No meals found for user {user.email} on {next_day_name}")

        if user.username == 'ferris':
            print('User ferris')
            # Get the next day's date in the user's time zone
            next_day = user_time.date() + timedelta(days=1)
            next_day_name = next_day.strftime('%A')   # e.g. "Saturday"

            meal_plan_meals_for_next_day = MealPlanMeal.objects.filter(
                meal_plan__user=user,
                meal_plan__week_start_date__lte=next_day,
                meal_plan__week_end_date__gte=next_day,
                day=next_day_name
            )
            print(meal_plan_meals_for_next_day)
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
                    logger.debug(f"MealPlanMeal IDs for user {user.email} on {next_day_name}: {meal_plan_meal_ids}")
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
                        print(f"Instruction data: {instruction_data}")
                        # If instruction_data is a list, wrap it into a dictionary
                        if isinstance(instruction_data, list):
                            instruction_data = {
                                "day": next_day_name,
                                "tasks": instruction_data,
                                "total_estimated_time": None  # Set this appropriately if available
                            }
                        
                        daily_task = DailyTask.model_validate(instruction_data)
                        print(f"Daily task: {daily_task}")
                    except Exception as e:
                        logger.error(f"Failed to parse follow-up instructions for user {user.email}: {e}")
                        continue
            
                    formatted_instructions = format_follow_up_instructions(daily_task, user.username)
            
                    send_follow_up_email(user, formatted_instructions)
                else:
                    logger.info(f"No follow-up instructions for user {user.email} on {next_day} for meal plan {meal_plan.id}")
            else:
                logger.info(f"No meals found for user {user.email} on {next_day_name}")

@shared_task
def generate_instructions(meal_plan_meal_ids):
    """
    Generate cooking instructions for a list of MealPlanMeal IDs and send a consolidated email to the user.
    Includes fetching/generating macro and youtube video info using existing functions.
    """
    from meals.models import MealAllergenSafety
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
    preferred_servings = getattr(user, 'preferred_servings', 1)
    user_preferred_language = user.preferred_language or 'English'

    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        # Ensure expiring_pantry_items is a list of strings (names) if needed by the prompt later
        expiring_items_str = ', '.join([item['name'] for item in expiring_pantry_items]) if expiring_pantry_items else 'None'
    except Exception as e:
        logger.error(f"Error retrieving pantry items for user {user.id}: {e}")
        expiring_items_str = 'None'

    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
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
                logger.error(f"Error fetching macro info for meal {meal.id}: {e}", exc_info=True)

        # YouTube Videos
        if not meal.youtube_videos:
            logger.info(f"YouTube videos missing for meal {meal.id}. Attempting to fetch.")
            try:
                video_data = find_youtube_cooking_videos(meal) # Expects Meal object
                if video_data:
                    # Assuming the function returns a dict/Pydantic model, convert to JSON string for storage
                    meal.youtube_videos = json.dumps(video_data) if not isinstance(video_data, str) else video_data
                    metadata_updated = True
                    logger.info(f"Successfully fetched YouTube videos for meal {meal.id}.")
                else:
                    logger.info(f"No YouTube videos found/generated for meal {meal.id}.")
            except Exception as e:
                logger.error(f"Error fetching YouTube videos for meal {meal.id}: {e}", exc_info=True)

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
                logger.error(f"Serialization error for MealPlanMeal ID {meal_plan_meal.id}: {e}")
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

                if meal.youtube_videos:
                    try:
                        video_data = json.loads(meal.youtube_videos) if isinstance(meal.youtube_videos, str) else meal.youtube_videos
                        videos = video_data.get("videos", [])
                        if videos:
                            video_links = [f"{v.get('title', 'N/A')} ({v.get('url', 'N/A')})" for v in videos[:2]] # Max 2 videos
                            video_info_str = "; ".join(video_links)
                        else:
                             video_info_str = "None found."
                    except (json.JSONDecodeError, TypeError, AttributeError) as e:
                        logger.warning(f"Could not parse youtube_videos for prompt display (meal {meal.id}): {e}")
                        video_info_str = "Available but format unclear." # Or pass raw string: meal.youtube_videos
                metadata_prompt_part += f"\\\\n- Helpful Videos: {video_info_str}"
                # --- End Metadata Prompt ---

                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {
                            "role": "system",
                            "content": f"You are a helpful assistant that generates cooking instructions in {user_preferred_language} based on the provided meal data and user context. Output JSON conforming to the Instructions schema."
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Generate cooking instructions in {user_preferred_language} for the following meal: {meal_data_json}. "
                                f"The user's context is: {user_context}. "
                                f"The user has these pantry items expiring soon: {expiring_items_str}. Prioritize using these if applicable. "
                                f"{metadata_prompt_part}" # Include the metadata context here
                                f"\\\\n\\\\n{substitution_str}\\\\n"
                                f"{chef_note}\\\\n"
                                f"Provide clear, step-by-step instructions, including estimated times for each step. "
                                f"Focus on practical steps a home cook can follow. Do not repeat the nutrition/video info in the steps, it's just for context."
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
                    }
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
                logger.error(f"OpenAI API error generating instructions for MealPlanMeal ID {meal_plan_meal.id}: {e}")
                continue # Skip this meal
            except ValidationError as e:
                 logger.error(f"Pydantic validation error for generated instructions for meal {meal.id}: {e}")
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
                'youtube_videos': meal.youtube_videos, # Add raw youtube videos string
                'meal_id': meal_plan_meal.id, # Keep original meal_plan_meal id
                'meal_plan_id': meal_plan.id,
                'meal_type': meal_plan_meal.meal_type,
                'meal_date': meal_plan_meal.meal_date, # Use the date from MealPlanMeal
            })
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Error parsing or validating instructions JSON for MealPlanMeal ID {meal_plan_meal.id}: {e}. Raw content: {instructions_content}")
        except Exception as e:
            logger.error(f"Unexpected error formatting instructions for MealPlanMeal ID {meal_plan_meal.id}: {e}", exc_info=True)


    # --- Bulk update meals with new metadata ---
    if meals_to_update:
        try:
            # Ensure unique meals are updated if a meal appears multiple times in meal_plan_meals
            unique_meals_to_update = {m.id: m for m in meals_to_update}.values()
            Meal.objects.bulk_update(list(unique_meals_to_update), ['macro_info', 'youtube_videos'])
            logger.info(f"Bulk updated metadata for {len(unique_meals_to_update)} meals.")
        except Exception as e:
            logger.error(f"Error bulk updating meal metadata: {e}", exc_info=True)
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

    # Render the template
    email_body_html = render_to_string('meals/daily_instructions.html', context)
    if not user.email_instruction_generation:
        logger.info(f"User {user_email} has disabled email instruction generation.")
        return

    # Prepare data for the webhook
    email_data = {
        'subject': subject,
        'message': email_body_html,
        'to': user_email,
        'from': 'support@sautai.com',
    }

    # Send data to external service
    try:
        n8n_url = os.getenv("N8N_GENERATE_INSTRUCTIONS_URL")
        requests.post(n8n_url, email_data)
        logger.info(f"Cooking instructions sent to external service for: {user_email}")
    except Exception as e:
        logger.error(f"Error sending cooking instructions for {user_email}: {str(e)}")

@shared_task
def generate_bulk_prep_instructions(meal_plan_id):
    from meals.models import MealPlan, MealPlanInstruction, MealAllergenSafety, Ingredient, Meal, MealPlanMeal
    from meals.serializers import MealPlanSerializer
    # Import is_chef_meal function here to avoid circular imports
    from meals.meal_plan_service import is_chef_meal
    # Import metadata functions
    from meals.macro_info_retrieval import get_meal_macro_information
    from meals.youtube_api_search import find_youtube_cooking_videos

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
    preferred_servings = getattr(user, 'preferred_servings', 1)
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

        # YouTube Videos
        if not meal.youtube_videos:
            logger.info(f"YouTube videos missing for bulk prep meal {meal.id}. Attempting fetch.")
            try:
                video_data = find_youtube_cooking_videos(meal)
                if video_data:
                    meal.youtube_videos = json.dumps(video_data) if not isinstance(video_data, str) else video_data
                    metadata_updated = True
                    logger.info(f"Successfully fetched YouTube videos for bulk prep meal {meal.id}.")
            except Exception as e:
                logger.error(f"Error fetching YouTube videos for bulk prep meal {meal.id}: {e}", exc_info=True)

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
            "youtube_videos": meal.youtube_videos # Use the potentially updated field
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
            Meal.objects.bulk_update(list(unique_meals_to_update), ['macro_info', 'youtube_videos'])
            logger.info(f"Bulk updated metadata for {len(meals_to_update)} meals during bulk prep generation.")
        except Exception as e:
            logger.error(f"Error bulk updating meal metadata during bulk prep generation: {e}", exc_info=True)
    # --- End bulk update ---


    # Get expiring pantry items
    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        expiring_items_str = ', '.join(item['name'] for item in expiring_pantry_items) if expiring_pantry_items else 'None'
    except Exception as e:
        logger.error(f"Error retrieving expiring pantry items for user {user.id}: {e}")
        expiring_items_str = 'None'

    # Generate the user context
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = 'No additional user context provided.'

    try:
        # Format substitution information for prompt
        substitution_str = ""
        if substitution_info:
            substitution_str = "\\\\n\\\\nIngredient substitution information (apply ONLY to non-chef meals):\\\\n"
            # Use a set to avoid duplicate notes
            unique_notes = {sub['notes'] for sub in substitution_info}
            for note in unique_notes:
                substitution_str += f"- {note}\\\\n"

        # Add chef meal note if needed
        chef_note = ""
        if chef_meals_present:
            chef_note = "\\\\nIMPORTANT: Some meals in this plan are chef-created and MUST be prepared exactly as specified. Do not suggest substitutions for ANY ingredients in chef-created meals."

        # Serialize all meal data with metadata for the prompt
        # Need to handle potential parsing of JSON string fields (macro_info, youtube_videos) before sending to LLM
        # Or adjust the prompt to expect potentially stringified JSON.
        # For simplicity here, we send the potentially stringified JSON directly.
        all_meals_json_for_prompt = json.dumps(all_meals_data_for_prompt, indent=2)

        # Generate the bulk prep instructions using OpenAI
        response = client.responses.create(
            model="gpt-4.1-mini", # Or gpt-4-turbo if more complexity needed
            input=[
                {
                    "role": "system",
                    "content": f"You are an expert meal prep assistant. Generate efficient, step-by-step bulk meal prep instructions in {user_preferred_language}, outputting JSON conforming to the BulkPrepInstructions schema. Group instructions logically (e.g., chop all veggies, cook all grains). Include storage tips and instructions for final assembly/reheating on the day of eating."
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate a comprehensive bulk meal prep plan in {user_preferred_language} for the following weekly meals (nutrition/video info is context, may be JSON strings): {all_meals_json_for_prompt}. "
                        f"The plan is for {preferred_servings} servings per meal. Adjust quantities. "
                        f"User Context: {user_context}. "
                        f"Expiring Pantry Items (prioritize using these): {expiring_items_str}. "
                        f"Goal: Prepare as much as possible in one session (e.g., Sunday) for the week. "
                        f"Provide detailed steps for the main prep day, storage instructions (refrigerate/freeze), and simple daily tasks for reheating/assembly. "
                        f"Include estimated times. Be mindful of food safety (e.g., cool before storing). "
                        f"The JSON output should contain a list of 'bulk_prep_steps' for the main prep day and a list of 'daily_tasks' for the rest of the week." 
                        f"{substitution_str}" # Substitution info appended
                        f"{chef_note}" # Chef meal constraints appended
                        f"\\\\nREMINDER: Nutritional info and videos provided in the meal list are for context only; do not repeat them verbatim in the instructions."
                    )
                }
            ],
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
            
            # Send an email with the bulk prep instructions
            send_bulk_prep_instructions.delay(meal_plan_id)
        else:
            logger.error(f"Failed to generate bulk prep instructions for meal plan {meal_plan_id}")
    
    except Exception as e:
        logger.error(f"Error generating bulk prep instructions for meal plan {meal_plan_id}: {str(e)}")

@shared_task
def send_bulk_prep_instructions(meal_plan_id):
    from django.utils import timezone
    from meals.models import MealPlanInstruction, MealPlan, MealPlanMeal, Meal

    meal_plan = MealPlan.objects.get(id=meal_plan_id)
    instruction_obj = MealPlanInstruction.objects.filter(meal_plan=meal_plan, is_bulk_prep=True).first()
    approval_token = meal_plan.approval_token
    streamlit_url = os.getenv("STREAMLIT_URL")

    if not instruction_obj:
        logger.error(f"No bulk prep instruction object found for MealPlan ID: {meal_plan_id}. Cannot send email.")
        return

    user = meal_plan.user
    instruction_text = instruction_obj.instruction_text

    # Deserialize the main instruction text
    try:
        validated_prep = BulkPrepInstructions.model_validate_json(instruction_text)
    except ValidationError as e:
        logger.error(f"Failed to parse bulk prep instructions JSON for user {user.email} (MealPlan: {meal_plan_id}): {e}")
        return

    # --- Fetch Metadata for Meals in Plan --- 
    meal_metadata_map = {}
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
    for mpm in meal_plan_meals:
        meal = mpm.meal
        meal_metadata_map[meal.name] = { # Use meal name as key (ensure uniqueness or handle collisions)
            'macro_info': meal.macro_info,
            'youtube_videos': meal.youtube_videos
        }
    logger.debug(f"Fetched metadata map for {len(meal_metadata_map)} meals for bulk prep email.")
    # --- End Metadata Fetch --- 

    bulk_prep_steps = validated_prep.bulk_prep_steps
    daily_tasks = validated_prep.daily_tasks # Get daily tasks as well

    # Group bulk prep steps by meal_type as before
    from collections import defaultdict
    steps_by_meal_type = defaultdict(list)
    for step in bulk_prep_steps:
        # Add metadata to the step dictionary if available
        step_dict = step.model_dump() # Convert Pydantic model to dict
        # Attempt to find meal name (assuming it might be in notes or description)
        # This part is tricky and depends on how the LLM includes meal names in the steps.
        # A more robust approach might require modifying the BulkPrepStep schema to include meal_name.
        # For now, let's try a simple search in description/notes.
        step_meal_name = None
        # Heuristic: Find a key from meal_metadata_map within the description
        for name in meal_metadata_map.keys():
            if name.lower() in step.description.lower(): # Case-insensitive check
                step_meal_name = name
                break
        if step_meal_name and step_meal_name in meal_metadata_map:
            step_dict['metadata'] = meal_metadata_map[step_meal_name]
        else:
            step_dict['metadata'] = None # No metadata found for this step

        steps_by_meal_type[step.meal_type].append(step_dict) # Append the dictionary

    # Group daily tasks by day
    tasks_by_day = defaultdict(list)
    for task in daily_tasks:
        tasks_by_day[task.day].append(task.model_dump()) # Convert to dict

    # Define meal type order and colors
    meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Other'] # Added 'Other'
    meal_type_colors = {
        'Breakfast': '#F7D9AE',
        'Lunch': '#CDE4B9',
        'Dinner': '#B9D6E4',
        'Snack': '#E4B9D3',
        'Other': '#e0e0e0' # Color for Other/Misc
    }

    # Create structure for bulk prep steps in the template
    bulk_meal_types_context = []
    for mt in meal_types_order:
        steps = steps_by_meal_type.get(mt, [])
        if steps: # Only include if there are steps
            bulk_meal_types_context.append({
                'meal_type': mt,
                'bg_color': meal_type_colors.get(mt, '#f0f0f0'),
                'steps': steps # List of step dictionaries, potentially with metadata
            })

    # Create structure for daily tasks in the template
    # Order days starting from the meal plan start day
    start_day_index = meal_plan.week_start_date.weekday() # Monday is 0, Sunday is 6
    ordered_days = [(start_day_index + i) % 7 for i in range(7)]
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ordered_day_names = [day_names[i] for i in ordered_days]
    
    daily_tasks_context = []
    for day_name in ordered_day_names:
        tasks = tasks_by_day.get(day_name, [])
        if tasks:
            daily_tasks_context.append({
                 'day': day_name,
                 'tasks': tasks # List of task dictionaries
            })

    context = {
        'user_name': user.username,
        'bulk_prep_meal_types': bulk_meal_types_context,
        'daily_tasks_by_day': daily_tasks_context,
        'meal_plan_id': meal_plan.id,
        'user_id': user.id,
        'approval_token': approval_token,
        'streamlit_url': streamlit_url,
    }

    # Render the template
    try:
        email_body_html = render_to_string('meals/bulk_prep_instructions.html', context)
    except Exception as e:
        logger.error(f"Error rendering bulk prep instructions template for meal plan {meal_plan_id}: {e}", exc_info=True)
        return

    # Send email
    if not user.email_instruction_generation:
        logger.info(f"User {user.email} has disabled bulk prep email instruction generation.")
        return

    email_data = {
        'subject': f"Your Bulk Meal Prep Instructions for {meal_plan.week_start_date.strftime('%b %d')} - {meal_plan.week_end_date.strftime('%b %d')}",
        'html_message': email_body_html, # Use html_message key if n8n expects it
        'to': user.email,
        'from': 'support@sautai.com',
    }

    try:
        n8n_url = os.getenv("N8N_SEND_BULK_PREP_EMAIL_URL")
        if not n8n_url:
            logger.error("N8N_SEND_BULK_PREP_EMAIL_URL environment variable is not set.")
            return

        response = requests.post(n8n_url, json=email_data, timeout=30) # Added timeout
        response.raise_for_status() # Check for HTTP errors
        logger.info(f"Bulk prep instructions email sent to n8n for {user.email}")
    except Exception as e:
        logger.error(f"Error sending bulk prep instructions to n8n for {user.email}: {e}")


def format_follow_up_instructions(daily_task: DailyTask, user_name: str):
    from collections import defaultdict

    # Group tasks by meal_type
    tasks_by_meal_type = defaultdict(list)
    for task in daily_task.tasks:
        tasks_by_meal_type[task.meal_type].append(task)

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
    from django.template.loader import render_to_string
    import requests
    import os

    # Use the context returned by format_follow_up_instructions
    # daily_task_context is a dictionary containing 'user_name', 'daily_task', and 'meal_types'
    email_body_html = render_to_string('meals/follow_up_instructions.html', daily_task_context)

    email_subject = f"Your Follow-Up Instructions for {daily_task_context['daily_task'].day}"
    recipient_email = user.email

    email_data = {
        'subject': email_subject,
        'message': email_body_html,
        'to': recipient_email,
        'from': 'support@sautai.com',
        'html': True
    }

    if not user.email_instruction_generation:
        # The user opted out of email instructions
        return

    try:
        n8n_url = os.getenv("N8N_SEND_FOLLOW_UP_EMAIL_URL")
        response = requests.post(n8n_url, json=email_data)
        logger.info(f"Follow-up instructions email sent to n8n for {user.email}")
    except Exception as e:
        logger.error(f"Error sending follow-up instructions to n8n for {user.email}: {e}")

@shared_task
def send_follow_up_instructions(meal_plan_id):
    from django.utils import timezone
    from meals.models import MealPlanInstruction, MealPlan

    meal_plan = MealPlan.objects.get(id=meal_plan_id)
    instructions = MealPlanInstruction.objects.filter(meal_plan=meal_plan, is_bulk_prep=False)
    user = meal_plan.user

    for instruction in instructions:
        instruction_text = instruction.instruction_text
        try:
            instruction_data = json.loads(instruction_text)
            daily_task = DailyTask.model_validate(instruction_data)
        except Exception as e:
            logger.error(f"Failed to parse follow-up instructions for user {user.email}: {e}")
            continue

        # Prepare the context for the template
        context = format_follow_up_instructions(daily_task, user.username)
        send_follow_up_email(user, context)