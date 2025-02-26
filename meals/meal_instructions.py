"""
Focus: Generating and managing instructions for bulk prep and daily tasks.
"""
import os
import json
import logging
import re
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
from meals.models import MealPlanMeal, MealPlan, MealPlanInstruction
from meals.pydantic_models import Instructions as InstructionsSchema
from meals.serializers import MealPlanMealSerializer
from custom_auth.models import CustomUser
from shared.utils import generate_user_context
from meals.pantry_management import get_expiring_pantry_items
from meals.pydantic_models import BulkPrepInstructions, DailyTask
from django.template.loader import render_to_string
from collections import defaultdict

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)


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
                print(f'Daily meal plan for user {user.email} on {next_day_name}')
                if meal_plan_meals_for_next_day.exists():
                    # Get the IDs of the MealPlanMeals for the next day
                    meal_plan_meal_ids = list(meal_plan_meals_for_next_day.values_list('id', flat=True))
                    logger.debug(f"MealPlanMeal IDs for user {user.email} on {next_day_name}: {meal_plan_meal_ids}")
                    generate_instructions.delay(meal_plan_meal_ids)
            elif meal_plan.meal_prep_preference == 'one_day_prep':
                print(f'One day prep meal plan for user {user.email} on {next_day_name}')
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
    """
    if not isinstance(meal_plan_meal_ids, list):
        meal_plan_meal_ids = [meal_plan_meal_ids]  # Convert single ID to a list

    meal_plan_meals = MealPlanMeal.objects.filter(id__in=meal_plan_meal_ids).select_related('meal_plan__user', 'meal')
        
    if not meal_plan_meals.exists():
        logger.error(f"No MealPlanMeals found for IDs: {meal_plan_meal_ids}")
        return

    # Assuming all meals belong to the same user
    first_meal = meal_plan_meals.first()
    user = first_meal.meal_plan.user
    user_email = user.email
    user_name = user.username

    # Retrieve the user's preferred serving size
    try:
        preferred_servings = user.preferred_servings
    except AttributeError:
        logger.error(f"User {user_email} does not have a preferred serving size set.")
        preferred_servings = 1

    try:
        # Retrieve the user's pantry items and expiring items
        expiring_pantry_items = get_expiring_pantry_items(user)
        expiring_items_str = ', '.join(expiring_pantry_items) if expiring_pantry_items else 'None'
    except Exception as e:
        logger.error(f"Error retrieving pantry items for user {user.id}: {e}")
        expiring_items_str = 'None'

    # Generate the user context
    try:
        user_context = generate_user_context(user)
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = 'No additional user context provided.'
    user_preferred_language = user.preferred_language or 'English'

    instructions_list = []  # To store instructions for all meals

    for meal_plan_meal in meal_plan_meals:
        from meals.models import Instruction as InstructionModel
        # Serialize meal plan meal data
        serializer = MealPlanMealSerializer(meal_plan_meal)
        meal_plan_meal_data = serializer.data

        # Check if instructions already exist for this meal plan meal
        existing_instruction = InstructionModel.objects.filter(meal_plan_meal=meal_plan_meal).first()
        
        if existing_instruction:
            logger.info(f"Instructions already exist for MealPlanMeal ID {meal_plan_meal.id}. Using existing instructions.")
            instructions_content = existing_instruction.content
        else:
            # Generate instructions using OpenAI API
            try:
                meal_data_json = json.dumps(meal_plan_meal_data)
            except Exception as e:
                logger.error(f"Serialization error for MealPlanMeal ID {meal_plan_meal.id}: {e}")
                continue  # Skip this meal

            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"You are a helpful assistant that generates cooking instructions in {user_preferred_language}."
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Answering in the user's preferred language: {user_preferred_language}, "
                                f"except for all day names and meal types being in English. "
                                f"Generate detailed cooking instructions for the following meal: {meal_data_json}. "
                                f"The meals should be scaled to the user's preferred serving size of {preferred_servings} servings. "
                                f"The user has the following pantry items that are expiring soon: {expiring_items_str}. "
                                f"Ensure these expiring items are used in the cooking instructions if they are part of the meal, "
                                f"but understand that using an item decreases its quantity for other meals. "
                                f"The meal is described as follows: '{meal_plan_meal_data['meal']['description']}' and "
                                f"it adheres to the user's information: {user_context}."
                            )
                        }
                    ],
                    store=True,
                    metadata={'tag': 'meal_instructions'},
                    response_format={
                        'type': 'json_schema',
                        'json_schema': 
                            {
                                "name": "Instructions", 
                                "schema": InstructionsSchema.model_json_schema()
                            }
                        }
                )

                instructions_content = response.choices[0].message.content  # Use the parsed response

                # Save the instructions
                if hasattr(meal_plan_meal, 'instructions'):
                    meal_plan_meal.instructions.update_content(instructions_content)
                else:
                    InstructionModel.objects.create(meal_plan_meal=meal_plan_meal, content=instructions_content)

            except ValidationError as e:
                logger.error(f"Error parsing instructions for MealPlanMeal ID {meal_plan_meal.id}: {e}")
                continue  # Skip this meal
            except Exception as e:
                logger.error(f"Unexpected error generating instructions for MealPlanMeal ID {meal_plan_meal.id}: {e}")
                continue  # Skip this meal
    
        # Parse the instructions content
        try:
            instructions_dict = json.loads(instructions_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse instructions as JSON for MealPlanMeal ID {meal_plan_meal.id}: {e}")
            continue  # Skip this meal
        except AttributeError as e:
            logger.error(f"Instructions content not found for MealPlanMeal ID {meal_plan_meal.id}: {e}")
            continue  # Skip this meal

        # Format the instructions into HTML
        formatted_instructions = ""
        for step in instructions_dict.get("steps", []):
            step_number = step.get("step_number", "N/A")
            step_description = step.get("description", "No description provided.")
            duration = step.get("duration", "No specific time")
            formatted_instructions += f"""
            <tr>
                <td style="padding: 8px; font-weight: bold;">Step {step_number}:</td>
                <td style="padding: 8px;">{step_description}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-style: italic;">Estimated Time:</td>
                <td style="padding: 8px;">{duration}</td>
            </tr>
            <tr><td colspan="2" style="padding: 8px; border-bottom: 1px solid #ddd;"></td></tr>
            """

        # Compute meal date

        meal_date = meal_plan_meal.meal_date
        print(f'Generated instructions for MealPlanMeal ID {meal_plan_meal.id} on {meal_date}')
        # if day_number is not None:
        #     meal_date = meal_plan_meal.meal_plan.week_start_date + timedelta(days=day_number)
        # else:
        #     meal_date = None
        #     logger.error(f"Invalid day name '{day_name}' for MealPlanMeal ID {meal_plan_meal.id}")

        # Append the formatted instructions to the list
        instructions_list.append({
            'meal_name': meal_plan_meal.meal.name,
            'formatted_instructions': formatted_instructions,
            'meal_id': meal_plan_meal.id,
            'meal_plan_id': meal_plan_meal.meal_plan.id,
            'meal_type': meal_plan_meal.meal_type,
            'meal_date': meal_date,
        })

    if not instructions_list:
        logger.info(f"No instructions generated for user {user_email}")
        return


    meal_dates = set(item['meal_date'] for item in instructions_list if item['meal_date'] is not None)
    print(f'Meal Dates: {meal_dates}')
    # Determine the subject line based on the dates of the meals
    if len(meal_dates) == 1:
        # All meals are on the same date
        meal_date = meal_dates.pop()
        meal_day_of_week = meal_date.strftime('%A')  # e.g., 'Sunday'
        print(f'Meal Day of Week: {meal_day_of_week}')
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
    from meals.models import MealPlan, MealPlanInstruction
    meal_plan = MealPlan.objects.get(id=meal_plan_id)

    # Check if the meal plan preference is 'one_day_prep'
    if meal_plan.meal_prep_preference != 'one_day_prep':
        return  # No action needed

    # Fetch the meals associated with the meal plan
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')

    # Create the meals_list
    meals_list = []
    for meal in meal_plan_meals:
        meals_list.append({
            "meal_name": meal.meal.name,
            "meal_type": meal.meal_type,
            "day": meal.day,
            "description": meal.meal.description or "A delicious meal prepared for you.",
        })
    user = meal_plan.user
    user_context = generate_user_context(user) or 'No additional user context provided.'

    # Preferred serving size
    try:
        preferred_servings = user.preferred_servings
    except AttributeError:
        logger.error(f"User {user.email} does not have a preferred serving size set.")
        preferred_servings = 1

    # Prepare the assistant prompt
    assistant_prompt = (
        f"Given what you know about the user, {user_context}, "
        f"generate a comprehensive weekly meal prep plan in {user.preferred_language} for the following list of meals: {json.dumps(meals_list)}.\n\n"
        f"It is import to ensure the user's preferred serving size of {preferred_servings} is considered for each meal. "
        f"**Goal:** Create a single bulk preparation session on {meal_plan.week_start_date.strftime('%A')} that covers all the meals for the entire week, minimizing daily cooking time. "
        f"Then, provide daily follow-up tasks for each day of the week (e.g., Monday, Tuesday, Wednesday) to finalize each meal with minimal effort.\n\n"

        f"**Instructions Schema:**\n"
        f"Please produce a JSON object matching the schema exactly:\n"
        f"{{\n"
        f"  \"bulk_prep_steps\": [\n"
        f"    {{\n"
        f"      \"step_number\": int,\n"
        f"      \"meal_type\": \"Breakfast\"|\"Lunch\"|\"Dinner\",\n"
        f"      \"description\": str,\n"
        f"      \"duration\": str,\n"
        f"      \"ingredients\": List[str],\n"
        f"      \"cooking_temperature\": Optional[str],\n"
        f"      \"cooking_time\": Optional[str],\n"
        f"      \"notes\": Optional[str]\n"
        f"    }},\n"
        f"    ...\n"
        f"  ],\n"
        f"  \"daily_tasks\": [\n"
        f"    {{\n"
        f"      \"day\": str,\n"
        f"      \"step_number\": int,\n"
        f"      \"tasks\": [\n"
        f"        {{\n"
        f"          \"step_number\": int,\n"
        f"          \"meal_type\": \"Breakfast\"|\"Lunch\"|\"Dinner\",\n"
        f"          \"description\": str,\n"
        f"          \"duration\": str,\n"
        f"          \"ingredients\": List[str],\n"
        f"          \"cooking_temperature\": Optional[str],\n"
        f"          \"cooking_time\": Optional[str],\n"
        f"          \"notes\": Optional[str]\n"
        f"        }},\n"
        f"        ... (multiple tasks per day are allowed)\n"
        f"      ],\n"
        f"      \"total_estimated_time\": Optional[str]\n"
        f"    }},\n"
        f"    ... (include multiple days, such as Monday, Tuesday, Wednesday, each with multiple tasks)\n"
        f"  ]\n"
        f"}}\n\n"

        f"**Additional Requirements:**\n"
        f"- Only return the JSON structure described above—no additional explanations.\n"
        f"- Include cooking times, temperatures, and techniques.\n"
        f"- Avoid user allergens and adhere to dietary preferences.\n"
        f"- Bulk prep steps should be detailed and cover all meals for the entire week. Daily tasks should be minimal, relying on pre-prepped items.\n\n"

        f"**Example (Abbreviated):**\n"
        f"{{\n"
        f"  \"bulk_prep_steps\": [\n"
        f"    {{\n"
        f"      \"step_number\": 1,\n"
        f"      \"meal_type\": \"Breakfast\",\n"
        f"      \"description\": \"Rinse and slice 2 cups of fresh strawberries...\",\n"
        f"      \"duration\": \"15 minutes\",\n"
        f"      \"ingredients\": [\"strawberries\"],\n"
        f"      \"notes\": \"Store in an airtight container.\"\n"
        f"    }},\n"
        f"    ...\n"
        f"  ],\n"
        f"  \"daily_tasks\": [\n"
        f"    {{\n"
        f"      \"day\": \"Monday\",\n"
        f"      \"step_number\": 1,\n"
        f"      \"tasks\": [\n"
        f"        {{\n"
        f"          \"step_number\": 1,\n"
        f"          \"meal_type\": \"Breakfast\",\n"
        f"          \"description\": \"Top the pre-prepared quinoa with sliced strawberries...\",\n"
        f"          \"duration\": \"5 minutes\",\n"
        f"          \"ingredients\": [\"quinoa\", \"strawberries\"],\n"
        f"          \"notes\": \"Serve immediately.\"\n"
        f"        }},\n"
        f"        {{\n"
        f"          \"step_number\": 2,\n"
        f"          \"meal_type\": \"Breakfast\",\n"
        f"          \"description\": \"Drizzle honey on top...\",\n"
        f"          \"duration\": \"2 minutes\",\n"
        f"          \"ingredients\": [\"honey\"],\n"
        f"          \"notes\": \"Adjust sweetness as desired.\"\n"
        f"        }}\n"
        f"      ],\n"
        f"      \"total_estimated_time\": \"7 minutes\"\n"
        f"    }},\n"
        f"    {{\n"
        f"      \"day\": \"Tuesday\",\n"
        f"      \"step_number\": 1,\n"
        f"      \"tasks\": [ ... multiple tasks for Tuesday ... ],\n"
        f"      \"total_estimated_time\": \"...\"\n"
        f"    }},\n"
        f"    {{\n"
        f"      \"day\": \"Wednesday\",\n"
        f"      \"step_number\": 1,\n"
        f"      \"tasks\": [ ... multiple tasks for Wednesday ... ],\n"
        f"      \"total_estimated_time\": \"...\"\n"
        f"    }}\n"
        f"  ]\n"
        f"}}\n\n"

    )
    # Call OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a helpful assistant that generates comprehensive meal prep instructions. "
                        f"The user prefers to minimize daily cooking time by preparing as much as possible in one day. "
                        f"Ensure that all meals for the week are considered, and provide detailed instructions for both bulk prep and daily tasks. "
                        f"For meals that typically require fresh preparation, include bulk prep steps to reduce time spent during the day-of cooking."
                    )
                },
                {"role": "user", "content": assistant_prompt}
            ],
            store=True,
            metadata={'tag': 'bulk_prep_instructions'},
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    "name": "BulkPrepInstructions",
                    "schema": BulkPrepInstructions.model_json_schema()
                }
            }
        )
        instructions_content = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating bulk prep instructions: {e}")
        return

    # Parse and validate the instructions_content
    try:
        validated_prep = BulkPrepInstructions.model_validate_json(instructions_content)
    except ValidationError as e:
        logger.error(f"Instructions content validation error: {e}")
        return

    # Serialize the validated_prep to JSON
    instruction_text = validated_prep.model_dump_json()
    # Save bulk prep instructions for the meal plan (e.g., on Sunday)
    MealPlanInstruction.objects.update_or_create(
        meal_plan=meal_plan,
        date=meal_plan.week_start_date,  # Assuming bulk prep is done on the start date
        is_bulk_prep=True,
        defaults={'instruction_text': instruction_text}
    )

    # Save follow-up instructions for each day
    day_name_to_number = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6,
    }
    for daily_task in validated_prep.daily_tasks:
        day_name = daily_task.day
        day_number = day_name_to_number.get(day_name)
        if day_number is not None:
            instruction_date = meal_plan.week_start_date + timedelta(days=day_number)
        else:
            logger.error(f"Invalid day name '{day_name}' in daily tasks.")
            continue

        # Print the daily tasks before saving
        print(f"Daily tasks for {day_name} about to be saved:", daily_task.model_dump())

        instruction_text = json.dumps(daily_task.model_dump())

        MealPlanInstruction.objects.update_or_create(
            meal_plan=meal_plan,
            date=instruction_date,
            is_bulk_prep=False,
            defaults={'instruction_text': instruction_text}
        )

    # Send bulk prep instructions to the user
    try:
        send_bulk_prep_instructions.delay(meal_plan_id)
    except Exception as e:
        logger.error(f"Error sending bulk prep instructions: {e}")

@shared_task
def send_bulk_prep_instructions(meal_plan_id):
    from django.utils import timezone
    from meals.models import MealPlanInstruction, MealPlan

    meal_plan = MealPlan.objects.get(id=meal_plan_id)
    instructions = MealPlanInstruction.objects.filter(meal_plan=meal_plan, is_bulk_prep=True)
    approval_token = meal_plan.approval_token
    streamlit_url = os.getenv("STREAMLIT_URL")
    for instruction in instructions:
        user = meal_plan.user
        instruction_text = instruction.instruction_text
        # Deserialize the instruction_text
        try:
            validated_prep = BulkPrepInstructions.model_validate_json(instruction_text)
        except Exception as e:
            logger.error(f"Failed to parse bulk prep instructions for user {user.email}: {e}")
            continue

        bulk_prep_steps = validated_prep.bulk_prep_steps

        # Group by meal_type as before
        from collections import defaultdict
        steps_by_meal_type = defaultdict(list)
        for step in bulk_prep_steps:
            steps_by_meal_type[step.meal_type].append(step)
        
        # Define meal type order and colors
        meal_types_order = ['Breakfast', 'Lunch', 'Dinner', 'Snack']
        meal_type_colors = {
            'Breakfast': '#F7D9AE',
            'Lunch': '#CDE4B9',
            'Dinner': '#B9D6E4',
            'Snack': '#E4B9D3'
        }

        # Create a structure for the template
        meal_types = []
        for mt in meal_types_order:
            meal_types.append({
                'meal_type': mt,
                'bg_color': meal_type_colors.get(mt, '#f0f0f0'),
                'steps': steps_by_meal_type.get(mt, [])
            })

        context = {
            'user_name': user.username,
            'meal_types': meal_types,
            'meal_plan_id': meal_plan.id,
            'user_id': user.id,
            'approval_token': approval_token,
            'streamlit_url': streamlit_url,
        }

        # Render the template
        email_body_html = render_to_string('meals/bulk_prep_instructions.html', context)

        # Send email
        if not user.email_instruction_generation:
            return

        email_data = {
            'subject': "Your Bulk Meal Prep Instructions for This Week",
            'message': email_body_html,
            'to': user.email,
            'from': 'support@sautai.com',
            'html': True
        }

        try:
            n8n_url = os.getenv("N8N_SEND_BULK_PREP_EMAIL_URL")
            response = requests.post(n8n_url, json=email_data)
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