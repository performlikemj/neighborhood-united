# might have to move this to the root or the shared folder
import asyncio
import json
import os
import textwrap
import uuid
from celery import shared_task
from django.shortcuts import get_object_or_404
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
from django.conf import settings
from meals.models import Meal, MealPlan, MealPlanMeal, Ingredient, MealPlanThread, DietaryPreference, CustomDietaryPreference
from custom_auth.models import CustomUser
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, UserSummary, UserMessage, ChatThread
from django.utils import timezone
from datetime import timedelta
from shared.utils import (get_user_info, post_review, update_review, delete_review, replace_meal_in_plan, 
                          remove_meal_from_plan, list_upcoming_meals, get_date, create_meal_plan, 
                          add_meal_to_plan, auth_get_meal_plan, auth_search_chefs, auth_search_dishes, 
                          approve_meal_plan, auth_search_ingredients, auth_search_meals_excluding_ingredient, 
                          search_meal_ingredients, suggest_alternative_meals,guest_search_ingredients ,
                          guest_get_meal_plan, guest_search_chefs, guest_search_dishes, 
                          generate_review_summary, access_past_orders, get_goal, 
                          update_goal, adjust_week_shift, get_unupdated_health_metrics, 
                          update_health_metrics, check_allergy_alert, provide_nutrition_advice, 
                          recommend_follow_up, find_nearby_supermarkets,
                          search_healthy_meal_options, provide_healthy_meal_suggestions, 
                          understand_dietary_choices, is_question_relevant, create_meal, cosine_similarity, 
                          get_embedding, generate_user_context, append_dietary_preference_to_json, get_dietary_preference_info)
from local_chefs.views import chef_service_areas, service_area_chefs
from rest_framework.response import Response
import re
import time
import pytz
from datetime import datetime
import logging
from openai import OpenAIError, BadRequestError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from pydantic import BaseModel, Field, ValidationError
from typing import List, Set, Optional, Tuple
from meals.pydantic_models import (ShoppingList as ShoppingListSchema, Instructions as InstructionsSchema, 
                                   MealOutputSchema, SanitySchema, MealPlanSchema, MealsToReplaceSchema, 
                                    DietaryPreferencesSchema, DietaryPreferenceDetail, ReplenishItemsSchema, MealPlanApprovalEmailSchema)
from rest_framework.renderers import JSONRenderer
from meals.serializers import MealPlanSerializer, MealPlanMealSerializer
from django.utils.timezone import now
import requests
from collections import defaultdict
from customer_dashboard.views import functions
from customer_dashboard.models import ToolCall
from types import SimpleNamespace
import traceback
import numpy as np
from numpy.linalg import norm
import random
from random import shuffle
from django.db.models import Q

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)


# Constants
MIN_SIMILARITY = 0.6  # Adjusted similarity threshold
MAX_ATTEMPTS = 5      # Max attempts to find or generate a meal per meal type per day
EXPECTED_EMBEDDING_SIZE = 1536  # Example size, adjust based on your embedding model

def get_user_pantry_items(user):
    """
    Retrieve a list of pantry items for a user.
    """
    pantry_items = user.pantry_items.all()
    return [item.item_name.lower() for item in pantry_items]

def get_expiring_pantry_items(user, days_threshold=7):
    """
    Retrieve pantry items that are expiring within the next `days_threshold` days.
    """
    today = timezone.now().date()
    expiring_date = today + timedelta(days=days_threshold)
    expiring_items = user.pantry_items.filter(
        expiration_date__gt=today,  # Exclude expired items
        expiration_date__lte=expiring_date  # Include items expiring soon
    )
    return [item.item_name.lower() for item in expiring_items]

def determine_items_to_replenish(user):
    """
    Determine which items need to be replenished to meet the user's emergency supply goals.
    """
    # Step 1: Get user context
    user_context = generate_user_context(user)
    
    # Step 2: Fetch current pantry items
    pantry_items = user.pantry_items.all()
    pantry_items_dict = {item.item_name.lower(): item.quantity for item in pantry_items}
    pantry_items_str = ', '.join([f"{item.item_name} (x{item.quantity})" for item in pantry_items]) or "None"
    
    # Step 3: Get emergency supply goal
    emergency_supply_goal_days = user.emergency_supply_goal or 0  # Default to 0 if not set
    
    if emergency_supply_goal_days == 0:
        logger.info(f"User {user.username} has no emergency supply goal set.")
        return []  # No items to replenish
    
    # Step 4: Create GPT prompt
    prompt_system = (
        "You are a helpful assistant that, given the user's context, current pantry items, and emergency supply goal, "
        "recommends a list of dried or canned goods the user should replenish to meet their emergency supply goal. "
        "Ensure that the recommendations align with the user's dietary preferences, allergies, and goals."
    )
    
    prompt_user = (
        f"The user has an emergency supply goal of {emergency_supply_goal_days} days.\n"
        f"User Context:\n{user_context}\n"
        f"Current Pantry Items:\n{pantry_items_str}\n"
        "Based on the above information, provide a list of items to replenish in JSON format, following this schema:\n"
        "{\n"
        "  \"items_to_replenish\": [\n"
        "    {\"item_name\": \"string\", \"quantity\": int, \"unit\": \"string\"},\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "Please ensure the items are suitable for long-term storage, align with the user's dietary preferences and allergies, "
        "and help the user meet their emergency supply goal."
    )
    
    # Step 5: Define expected response format using Pydantic
    # (Already defined above with ReplenishItemsSchema)
    
    # Step 6: Call OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user},
            ],
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    'name': 'ReplenishItems',
                    'schema': ReplenishItemsSchema.model_json_schema()
                }
            }
        )
        assistant_message = response.choices[0].message.content
        
        # Step 7: Parse and validate GPT response
        try:
            parsed_response = json.loads(assistant_message)
            replenish_items = ReplenishItemsSchema.model_validate(parsed_response)
            return replenish_items.items_to_replenish
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Error parsing GPT response: {e}")
            logger.error(f"Assistant message: {assistant_message}")
            return []
        
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return []

@shared_task
def send_meal_plan_approval_email(meal_plan_id):
    from meals.models import MealPlan, MealPlanMeal
    from shared.utils import generate_user_context
    import uuid
    from django.utils import timezone
    import json
    from jinja2 import Environment, FileSystemLoader
    from django.conf import settings
    import os

    try:
        # Start a database transaction
        with transaction.atomic():
            meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)
            
            # Assign approval_token if not present
            if not meal_plan.approval_token:
                meal_plan.approval_token = uuid.uuid4()
                meal_plan.token_created_at = timezone.now()
                meal_plan.save()
            
            # Retrieve the full user object
            user = meal_plan.user
            user_name = user.username
            user_email = user.email

            # **Check if the user has opted in to receive meal plan emails**
            if not user.email_meal_plan_saved:
                logger.info(f"User {user.username} has opted out of meal plan emails.")
                return  # Do not send the email

        # Proceed with external calls after the transaction is successful
        try:
            user_context = generate_user_context(user)
        except Exception as e:
            logger.error(f"Error generating user context: {e}")
            user_context = "User context not available."

        try:
            preferred_language = user.preferred_language
        except Exception as e:
            logger.error(f"Error fetching preferred language for user {user.username}: {e}")
            preferred_language = "English"

        # Generate the approval link with query parameter
        full_approval_url = f"{os.getenv('STREAMLIT_URL')}/meal_plans?approval_token={meal_plan.approval_token}"

        # Serialize the meal plan data for the `meals` field
        # Fetch the meals associated with the meal plan
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')

        # Create the meals_list
        meals_list = []
        for meal in meal_plan_meals:
            meals_list.append({
                "meal_name": meal.meal.name,
                "meal_type": meal.meal_type,
                "day": meal.day,
                "description": meal.meal.description or "A delicious meal prepared for you."
            })

        # Sort the meals_list by day and meal type
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        meal_type_order = ['Breakfast', 'Lunch', 'Dinner']
        day_order_map = {day: index for index, day in enumerate(day_order)}
        meal_type_order_map = {meal_type: index for index, meal_type in enumerate(meal_type_order)}
        meals_list.sort(key=lambda x: (
            day_order_map.get(x['day'], 7),
            meal_type_order_map.get(x['meal_type'], 3)
        ))

        # Call OpenAI to generate the email content
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates meal plan approval emails."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate an email in {preferred_language}, given what you know about the user: {user_context}, that includes the following:\n\n"
                            f"1. Greet the user by their name: {user_name}.\n"
                            f"2. Inform them that their meal plan for the week {meal_plan.week_start_date} to {meal_plan.week_end_date} has been created.\n"
                            f"3. Include a well-formatted and high-level summary of the following list of meals in their plan:\n{meals_list}. Make the summary enticing and engaging with newlines where necessary to avoid a cramped description."
                        )
                    }
                ],
                response_format={
                    'type': 'json_schema',
                    'json_schema': 
                        {
                            "name": "ApprovalEmail",
                            "schema": MealPlanApprovalEmailSchema.model_json_schema()
                        }
                    }
            )

            response_content = response.choices[0].message.content
            email_data_dict = json.loads(response_content)

            # Modify summary_text to support bold text and newlines
            if 'summary_text' in email_data_dict:
                summary_text = email_data_dict['summary_text']
                # Replace **text** with <strong>text</strong>
                summary_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', summary_text)
                # Replace newlines with <br>
                summary_text = summary_text.replace('\n', '<br>')
                email_data_dict['summary_text'] = summary_text

            email_model = MealPlanApprovalEmailSchema(**email_data_dict)

            # Set up Jinja2 environment
            project_dir = settings.BASE_DIR
            env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
            template = env.get_template('meals/meal_plan_email.html')

            # Generate the profile URL
            profile_url = f"{os.getenv('STREAMLIT_URL')}/profile"

            # Render the template with data from the Pydantic model
            email_body_html = template.render(
                user_name=email_model.user_name,
                meal_plan_week_start=email_model.meal_plan_week_start,
                meal_plan_week_end=email_model.meal_plan_week_end,
                approval_link=full_approval_url,
                meals_list=meals_list,
                summary_text=email_model.summary_text,
                profile_url=profile_url
            )

            email_data = {
                'subject': f'Your Meal Plan for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
                'html_message': email_body_html,
                'to': user_email,
                'from': 'support@sautai.com',
            }

            try:
                logger.debug(f"Sending approval email to n8n for: {user_email}")
                n8n_url = os.getenv("N8N_GENERATE_APPROVAL_EMAIL_URL")
                response = requests.post(n8n_url, json=email_data)
            except Exception as e:
                logger.error(f"Error sending approval email to n8n for: {user_email}, error: {str(e)}")
                traceback.print_exc()


            logger.info(f"Approval email sent to n8n for: {user_email}")

        except Exception as e:
            logger.error(f"Error generating or sending approval email: {e}")
            # Optionally, re-raise the exception if needed
            # raise

    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        # Handle exception as needed

@shared_task
def generate_meal_embedding(meal_id):
    """
    Generate a comprehensive embedding for the meal, including its name, description,
    dietary preferences, dishes, reviews, and other attributes.
    """
    meal = Meal.objects.get(id=meal_id)
    meal_attributes = []

    # Include meal name and description
    meal_attributes.append(meal.name)
    meal_attributes.append(meal.description)

    # Include predefined dietary preferences
    dietary_prefs = [pref.name for pref in meal.dietary_preferences.all()]
    if dietary_prefs:
        meal_attributes.append(f"Dietary Preferences: {', '.join(dietary_prefs)}")

    # Include custom dietary preferences
    custom_diet_prefs = [pref.name for pref in meal.custom_dietary_preferences.all()]
    if custom_diet_prefs:
        meal_attributes.append(f"Custom Dietary Preferences: {', '.join(custom_diet_prefs)}")

    # Other attributes like meal type, dishes, etc.
    meal_attributes.append(f"Meal Type: {meal.meal_type}")
    if meal.dishes.exists():
        dish_names = [dish.name for dish in meal.dishes.all()]
        meal_attributes.append(f"Dishes: {', '.join(dish_names)}")

    if meal.review_summary:
        meal_attributes.append(f"Review Summary: {meal.review_summary}")
    if meal.chef:
        meal_attributes.append(f"Chef: {meal.chef.name}")

    # Combine all meal attributes into a single string
    meal_representation = " | ".join(meal_attributes)

    # Generate the embedding using the combined representation
    return get_embedding(meal_representation)

@shared_task
def handle_custom_dietary_preference(custom_prefs):
    """
    Handles the addition of a custom dietary preference.
    If it doesn't exist, generate its structure using OpenAI and append to JSON.
    """
    for custom_pref in custom_prefs:
        if custom_pref and not get_dietary_preference_info(custom_pref):
            try:
                # Step 4: Use OpenAI to generate structured JSON
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an assistant that helps define new dietary preferences."
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Provide a structured JSON definition for the following dietary preference, matching the existing format:\n\n"
                                f"Preference Name: {custom_pref}"
                            )
                        }
                    ],
                    response_format={
                        'type': 'json_schema',
                        'json_schema': 
                            {
                                "name": "CustomDietaryPreference",
                                "schema": DietaryPreferenceDetail.model_json_schema()
                            }
                        }
                    )


                # Parse GPT response
                gpt_output = response.choices[0].message.content
                new_pref_data = json.loads(gpt_output)
                # Validate the structure using Pydantic
                validated_pref = DietaryPreferenceDetail.model_validate(new_pref_data)
                # Step 5: Append to dietary_preferences.json
                append_dietary_preference_to_json(
                    preference_name=custom_pref,
                    definition=validated_pref.description,
                    allowed=validated_pref.allowed,
                    excluded=validated_pref.excluded
                )

                # Create the CustomDietaryPreference object in the database
                CustomDietaryPreference.objects.get_or_create(
                    name=custom_pref,
                    defaults={
                        'description': validated_pref.description,
                        'allowed': validated_pref.allowed,
                        'excluded': validated_pref.excluded,
                    }
                )

                logger.info(f"Custom dietary preference '{custom_pref}' added successfully.")

            except (OpenAIError, json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Error generating or appending dietary preference '{custom_pref}': {e}")
                logger.error(traceback.format_exc())
                return False
    return True  # If preference exists, nothing to do

@shared_task
def assign_dietary_preferences(meal_id):
    """
    Use OpenAI API to determine dietary preferences based on meal details.
    Returns a list of dietary preferences.
    """
    try:
        meal = Meal.objects.get(id=meal_id)
        messages = meal.generate_messages()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={
                'type': 'json_schema',
                'json_schema': 
                    {
                        "name": "Preferences",
                        "schema": DietaryPreferencesSchema.model_json_schema()
                    }
                }
        )  

        assistant_message_content = response.choices[0].message.content.strip()

        dietary_prefs = meal.parse_dietary_preferences(assistant_message_content)

        if not dietary_prefs:
            logger.warning(f"No dietary preferences returned by OpenAI for '{meal.name}'.")
            return

        # Assign the dietary preferences to the meal
        for pref_name in dietary_prefs:
            pref, created = DietaryPreference.objects.get_or_create(name=pref_name)
            meal.dietary_preferences.add(pref)

        logger.info(f"Assigned dietary preferences for '{meal.name}': {dietary_prefs}")

    except Meal.DoesNotExist:
        logger.error(f"Meal with ID {meal_id} does not exist.")
        return

    except ValidationError as ve:
        logger.error(f"Pydantic validation error for Meal '{meal.name}': {ve}")
        return

    except json.JSONDecodeError as je:
        logger.error(f"JSON decoding error for Meal '{meal.name}': {je}")
        logger.error(f"Response content: {assistant_message_content}")
        return

    except OpenAIError as oe:
        logger.error(f"OpenAI API error while assigning dietary preferences for Meal '{meal.name}': {oe}")
        return

    except Exception as e:
        logger.error(f"Unexpected error while assigning dietary preferences for Meal '{meal.name}': {e}")
        logger.error(traceback.format_exc())
        return

from django.db import transaction

def send_meal_plan_approval_email(meal_plan_id):
    from meals.models import MealPlan, MealPlanMeal
    from shared.utils import generate_user_context
    import uuid
    from django.utils import timezone
    import json
    from jinja2 import Environment, FileSystemLoader
    from django.conf import settings
    import os

    try:
        # Start a database transaction
        with transaction.atomic():
            meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)
            
            # Assign approval_token if not present
            if not meal_plan.approval_token:
                meal_plan.approval_token = uuid.uuid4()
                meal_plan.token_created_at = timezone.now()
                meal_plan.save()
            
            # Retrieve the full user object
            user = meal_plan.user
            user_name = user.username
            user_email = user.email

            # **Check if the user has opted in to receive meal plan emails**
            if not user.email_meal_plan_saved:
                logger.info(f"User {user.username} has opted out of meal plan emails.")
                return  # Do not send the email

        # Proceed with external calls after the transaction is successful
        try:
            user_context = generate_user_context(user)
        except Exception as e:
            logger.error(f"Error generating user context: {e}")
            user_context = "User context not available."

        try:
            preferred_language = user.preferred_language
        except Exception as e:
            logger.error(f"Error fetching preferred language for user {user.username}: {e}")
            preferred_language = "English"

        # Generate the approval link with query parameter
        full_approval_url = f"{os.getenv('STREAMLIT_URL')}/meal_plans?approval_token={meal_plan.approval_token}"

        # Serialize the meal plan data
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
        meals_list = [
            f"{meal.meal.name} for {meal.meal_type} on {meal.day}" for meal in meal_plan_meals
        ]
        meal_plan_content = "\n".join(meals_list)

        # Call OpenAI to generate the email content
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates meal plan approval emails."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate an email in {preferred_language}, given what you know about the user: {user_context}, that includes the following:\n\n"
                            f"1. Greet the user by their name: {user_name}.\n"
                            f"2. Inform them that their meal plan for the week {meal_plan.week_start_date} to {meal_plan.week_end_date} has been created.\n"
                            f"3. Include the approval link: {full_approval_url}.\n"
                            f"4. Encourage them to click the link to approve their meal plan.\n"
                            f"5. Include a summary of the following list of meals in their plan:\n{meal_plan_content}. Make the summary enticing and engaging."
                        )
                    }
                ],
                response_format={
                    'type': 'json_schema',
                    'json_schema': 
                        {
                            "name": "ApprovalEmail",
                            "schema": MealPlanApprovalEmailSchema.model_json_schema()
                        }
                    }
            )

            response_content = response.choices[0].message.content
            email_data_dict = json.loads(response_content)
            email_model = MealPlanApprovalEmailSchema(**email_data_dict)

            # Set up Jinja2 environment
            project_dir = settings.BASE_DIR
            env = Environment(loader=FileSystemLoader(os.path.join(project_dir, 'meals', 'templates')))
            template = env.get_template('meals/meal_plan_email.html')

            # Generate the profile URL
            profile_url = f"{os.getenv('STREAMLIT_URL')}/profile"

            # Render the template with data from the Pydantic model
            email_body_html = template.render(
                user_name=email_model.user_name,
                meal_plan_week_start=email_model.meal_plan_week_start,
                meal_plan_week_end=email_model.meal_plan_week_end,
                approval_link=email_model.approval_link,
                meals=email_model.meals,
                summary_text=email_model.summary_text,
                profile_url=profile_url
            )

            email_data = {
                'subject': f'Your Meal Plan for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
                'html_message': email_body_html,
                'to': user_email,
                'from': 'support@sautai.com',
            }

            # Send data to Zapier
            try:
                logger.debug(f"Sending approval email to Zapier for: {user_email}")
                zap_url = os.getenv("ZAP_GENERATE_APPROVAL_EMAIL_URL")  # Replace with your Zapier webhook URL
                response = requests.post(zap_url, json=email_data)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Error sending approval email to Zapier for: {user_email}, error: {str(e)}")

            logger.info(f"Approval email sent to Zapier for: {user_email}")

        except Exception as e:
            logger.error(f"Error generating or sending approval email: {e}")
            # Optionally, re-raise the exception if needed
            # raise

    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        # Handle exception as needed

        
@shared_task
def create_meal_plan_for_new_user(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        create_meal_plan_for_user(user, start_of_week, end_of_week)
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

def create_meal_plan_for_user(user, start_of_week=None, end_of_week=None):
    existing_meals = MealPlanMeal.objects.filter(
        meal_plan__user=user,
        meal_plan__week_start_date=start_of_week,
        meal_plan__week_end_date=end_of_week,
    )

    user_id = user.id   
    if existing_meals.exists():
        logger.info(f"User {user.username} already has meals for the week. Skipping.")
        return

    # Create a new meal plan if no existing plan
    meal_plan, created = MealPlan.objects.get_or_create(
        user=user,
        week_start_date=start_of_week,
        week_end_date=end_of_week,
    )
    if created:
        logger.info(f"Created new meal plan for user {user.username} for the week {start_of_week} to {end_of_week}")
    else:
        logger.info(f"Meal plan already exists for user {user.username} for the week {start_of_week} to {end_of_week}")

    meal_types = ['Breakfast', 'Lunch', 'Dinner']

    # Fetch existing meals in the meal plan for context
    existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')

    # Create a set of meal names to avoid duplicates
    existing_meal_names = set(existing_meals.values_list('meal__name', flat=True))

    # Fetch embeddings
    existing_meal_embeddings = list(
        existing_meals.values_list('meal__meal_embedding', flat=True)
    )
    # Keep track of skipped meals by their ID
    skipped_meal_ids = set()

    # Iterate over each day and meal type
    for day_offset in range(7):  # 7 days in a week
        meal_date = start_of_week + timedelta(days=day_offset)
        day_name = meal_date.strftime('%A')
        for meal_type in meal_types:
            # Check if a meal for this day and meal type already exists
            if MealPlanMeal.objects.filter(
                meal_plan=meal_plan, 
                day=day_name, 
                meal_type=meal_type
            ).exists():
                continue  # Skip this meal type if it already exists for the day

            attempt = 0
            meal_added = False

            while attempt < MAX_ATTEMPTS and not meal_added:
                attempt += 1

                # Try finding a suitable existing meal from the database
                meal_found = find_existing_meal(
                    user, 
                    meal_type, 
                    existing_meal_embeddings, 
                    existing_meal_names, 
                    skipped_meal_ids
                )

                if meal_found is None:
                    # No existing meal found, generate and create a new meal
                    result = generate_and_create_meal(
                        user=user,
                        meal_plan=meal_plan,  # Pass the meal plan object
                        meal_type=meal_type,
                        existing_meal_names=existing_meal_names,
                        existing_meal_embeddings=existing_meal_embeddings,
                        user_id=user_id,
                        day_name=day_name
                    )

                    if result['status'] == 'success':
                        meal = result['meal']
                        meal_added = True
                    else:
                        logger.warning(f"Attempt {attempt}: {result['message']}")
                        continue  # Retry if meal creation failed
                else:
                    # Meal was found, perform sanity check
                    if perform_openai_sanity_check(meal_found, user):
                        try:
                            MealPlanMeal.objects.create(
                                meal_plan=meal_plan,
                                meal=meal_found,
                                day=day_name,
                                meal_type=meal_type,
                            )
                            # Add the found meal to the lists so it doesn't get reused
                            existing_meal_names.add(meal_found.name)
                            existing_meal_embeddings.append(meal_found.meal_embedding)
                            logger.info(f"Added existing meal '{meal_found.name}' for {day_name} {meal_type}.")
                            meal_added = True
                        except Exception as e:
                            logger.error(f"Error adding meal '{meal_found.name}' to meal plan: {e}")
                            skipped_meal_ids.add(meal_found.id)
                    else:
                        logger.warning(f"Meal '{meal_found.name}' contains allergens or fails sanity check. Skipping.")
                        skipped_meal_ids.add(meal_found.id)
                        meal_found = None  # Trigger another attempt

                if attempt >= MAX_ATTEMPTS and not meal_added:
                    logger.error(f"Failed to add a meal for {meal_type} on {day_name} after {MAX_ATTEMPTS} attempts.")

    logger.info(f"Meal plan created successfully for user {user.username} for the week {start_of_week} to {end_of_week}")

    analyze_and_replace_meals(user, meal_plan, meal_types)

    return meal_plan

def analyze_and_replace_meals(user, meal_plan, meal_types):
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
                        logger.info(f"Removed meal {old_meal_id} from {day} ({meal_type})")  

                        # Fallback: Create a new meal
                        result = generate_and_create_meal(
                            user=user,
                            meal_plan=meal_plan,  # Pass the meal plan object
                            meal_type=meal_type,
                            existing_meal_names=set(),
                            existing_meal_embeddings=[],
                            user_id=user.id,
                            day_name=day
                        )
                    else:
                        logger.error(f"Failed to create a fallback meal for {meal_type} on {day}: {result['message']}")
                    
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
                        logger.info(f"Replacing meal ID {old_meal_id} with meal ID {new_meal_id} for {meal_type} on {day}")

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
                            logger.info(f"Successfully replaced meal {old_meal_id} with {new_meal_id} on {day} ({meal_type})")
                            replacement_found = True
                        else:
                            logger.error(f"Failed to replace meal {old_meal_id} on {day} ({meal_type}): {result['message']}")
                            traceback.print_exc()
                    else:
                        logger.warning(f"Meal '{new_meal.name}' failed sanity check. Trying next possible replacement.")

                if not replacement_found:
                    logger.error(f"Could not find a suitable replacement for meal ID {old_meal_id} on {day} ({meal_type}).")

    except Exception as e:
        logger.error(f"Error during meal plan analysis and replacement: {e}")
        traceback.print_exc()
        return

def generate_and_create_meal(user, meal_plan, meal_type, existing_meal_names, existing_meal_embeddings, user_id, day_name, max_attempts=3):
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Attempt {attempt} to generate and create meal for {meal_type} on {day_name}.")

        # Generate meal details
        meal_details = generate_meal_details(
            user,
            meal_type,
            existing_meal_names,
            existing_meal_embeddings
        )
        if not meal_details:
            logger.error(f"Attempt {attempt}: Failed to generate meal details for {meal_type} on {day_name}.")
            continue  # Retry

        # Create meal
        meal_data = create_meal(
            user_id=user_id,
            name=meal_details.get('name'),
            dietary_preference=meal_details.get('dietary_preference'),
            description=meal_details.get('description'),
            meal_type=meal_type,
        )

        # Handle the case where a similar meal already exists
        if meal_data['status'] == 'info' and 'similar_meal_id' in meal_data:
            similar_meal_id = meal_data['similar_meal_id']
            try:
                meal = Meal.objects.get(id=similar_meal_id)
                logger.info(f"Similar meal '{meal.name}' already exists. Adding to meal plan.")
                
                # Add similar meal to meal plan
                MealPlanMeal.objects.create(
                    meal_plan=meal_plan,
                    meal=meal,
                    day=day_name,
                    meal_type=meal_type,
                )
                existing_meal_names.add(meal.name)
                existing_meal_embeddings.append(meal.meal_embedding)
                
                # Return the similar meal and stop further attempts
                return {
                    'status': 'success',
                    'message': f'Similar meal found and added: {meal.name}.',
                    'meal': meal
                }
            except Meal.DoesNotExist:
                logger.error(f"Similar meal with ID {similar_meal_id} does not exist.")
                continue  # Retry

        # Handle meal creation failure
        if meal_data['status'] != 'success':
            logger.error(f"Attempt {attempt}: Failed to create meal: {meal_data.get('message')}")
            continue  # Retry

        # Verify meal creation
        try:
            meal_id = meal_data['meal']['id']
            meal = Meal.objects.get(id=meal_id)
        except Meal.DoesNotExist:
            logger.error(f"Meal with ID {meal_id} does not exist after creation.")
            continue  # Retry

        # Perform sanity check
        if perform_openai_sanity_check(meal, user):
            MealPlanMeal.objects.create(
                meal_plan=meal_plan,
                meal=meal,
                day=day_name,
                meal_type=meal_type,
            )
            existing_meal_names.add(meal.name)
            existing_meal_embeddings.append(meal.meal_embedding)
            logger.info(f"Added new meal '{meal.name}' for {day_name} {meal_type}.")
            return {'status': 'success', 'message': 'Meal created and added successfully.', 'meal': meal}
        else:
            logger.warning(f"Attempt {attempt}: Generated meal '{meal.name}' failed sanity check.")
            continue  # Retry

    logger.error(f"Failed to generate and create meal for {meal_type} on {day_name} after {max_attempts} attempts.")
    return {'status': 'error', 'message': f'Failed to create meal after {max_attempts} attempts.'}



def format_meal_plan(meal_plan_meals):
    return '\n'.join([
        f"{meal.meal.id}: {meal.meal.name} on {meal.day} ({meal.meal_type})" 
        for meal in meal_plan_meals
    ])

def get_possible_replacement_meals(user, meal_type, existing_meal_ids):
    # Retrieve user allergies
    user_allergies = [
        a.strip() for a in (user.allergies or '').split(',') + 
        (user.custom_allergies or '').split(',') if a.strip()
    ]
    
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
    min_similarity: float = 0.8
) -> Optional[Meal]:
    # Convert existing meal names to lowercase for consistency
    existing_meal_names_lower = {name.lower() for name in existing_meal_names}
    
    # Collect regular dietary preferences
    regular_dietary_prefs = list(user.dietary_preferences.all())
    
    # Collect custom dietary preferences
    custom_dietary_prefs = list(user.custom_dietary_preferences.all())
    
    
    # Handle the "Everything" dietary preference
    everything_pref = next((pref for pref in regular_dietary_prefs if pref.name == "Everything"), None)
    
    # If "Everything" is the only preference, ignore the filter
    if everything_pref and len(regular_dietary_prefs) == 1 and not custom_dietary_prefs:
        print(f"Preference: {everything_pref}")
        potential_meals = Meal.objects.filter(
            meal_type=meal_type,    # Desired meal type
            creator_id=user.id      # Meals created by the user
        ).exclude(
            id__in=skipped_meal_ids  # Exclude skipped meals
        ).exclude(
            name__in=existing_meal_names_lower  # Exclude existing meal names
        ).distinct()
    else:
        # If "Everything" exists alongside other preferences, exclude it from the filter
        if everything_pref:
            regular_dietary_prefs.remove(everything_pref)
        
        # Build Q filters separately for regular and custom dietary preferences
        regular_prefs_filter = Q()
        for pref in regular_dietary_prefs:
            regular_prefs_filter |= Q(dietary_preferences=pref)
        
        custom_prefs_filter = Q()
        for custom_pref in custom_dietary_prefs:
            custom_prefs_filter |= Q(custom_dietary_preferences=custom_pref)
        
        # Combine both filters using OR
        combined_filter = regular_prefs_filter | custom_prefs_filter
        print(f"Combined filter: {combined_filter}")
        # Query the database for potential meals that match the user's dietary preferences
        potential_meals = Meal.objects.filter(
            combined_filter,        # Combined dietary preferences
            meal_type=meal_type,    # Desired meal type
            creator_id=user.id      # Meals created by the user
        ).exclude(
            id__in=skipped_meal_ids  # Exclude skipped meals
        ).exclude(
            name__in=existing_meal_names_lower  # Exclude existing meal names
        ).distinct()

    
    potential_meal_count = potential_meals.count()
    
    if not potential_meals.exists():
        print(f"No potential meals found for user {user.username} and meal type {meal_type}.")
        return None  # No suitable meals available
    
    # If there are no existing embeddings, return any potential meal directly
    if not existing_meal_embeddings:
        selected_meal = potential_meals.first()
        return selected_meal
    
    # Iterate over potential meals and find the first sufficiently unique meal
    for meal in potential_meals:
        if meal.meal_embedding is None or len(meal.meal_embedding) == 0:
            continue  # Skip if no embedding available
        
        # Compare with existing embeddings
        is_unique = True
        for existing_embedding in existing_meal_embeddings:
            try:
                similarity = cosine_similarity(meal.meal_embedding, existing_embedding)
                if similarity >= min_similarity:
                    is_unique = False
                    break  # Exit the inner loop if similarity threshold is met
            except Exception as e:
                # logger.error(f"Error computing similarity for meal '{meal.name}': {e}")
                is_unique = False
                break  # Exit on error to skip this meal
        
        if is_unique:
            return meal  # Return the first sufficiently unique meal
    
    return None  # No sufficiently unique meal found


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
    # Retrieve primary and custom allergies; default to empty strings if None
    primary_allergies = user.allergies or ''
    custom_allergies = user.custom_allergies or ''

    # Combine both allergy strings
    combined_allergies = f"{primary_allergies},{custom_allergies}" if custom_allergies else primary_allergies

    # Split the combined string into individual allergies, strip whitespace, and convert to lowercase
    all_allergies = [
        allergy.strip().lower() 
        for allergy in combined_allergies.split(',') 
        if allergy.strip()
    ]

    return all_allergies

def perform_openai_sanity_check(meal, user):
    """
    Use OpenAI to generate missing ingredient data for meals and ensure allergens are avoided.
    """
    user_context = generate_user_context(user)
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
                        f"Given the following user preferences: {user_context}."
                        f"The meal is called '{meal.name}' and is described as: {meal.description}. "
                        f"The dietary information about the meal are: {meal.dietary_preferences.all()} and/or {meal.custom_dietary_preferences.all()}. "
                    )
                }
            ],
            response_format={
                'type': 'json_schema',
                'json_schema': 
                    {
                        "name": "Sanity",
                        "schema": SanitySchema.model_json_schema()
                    }
                }
            )

        gpt_output = response.choices[0].message.content

        allergen_check = json.loads(gpt_output).get('allergen_check', False)

        # if allergen_check:
        #     # logger.info(f"Meal {meal.name} is allergen-free for user {user.username}.")
        # else:
        #     # logger.warning(f"Meal {meal.name} contains allergens for user {user.username}.")

        return allergen_check

    except Exception as e:
        logger.error(f"Error during OpenAI sanity check: {e}")
        return False  # Return False if an error occurs

def generate_meal_details(user, meal_type, existing_meal_names, existing_meal_embeddings, min_similarity=0.1, max_attempts=5):
    """
    Use GPT to generate meal details based on the user's preferences and meal type, while avoiding duplicates.
    Compare the new meal's embedding to existing meals to ensure sufficient uniqueness.
    """
    # Fetch the user's previous week's meal plan
    previous_week_start = timezone.now().date() - timedelta(days=timezone.now().weekday() + 7)
    previous_week_end = previous_week_start + timedelta(days=6)

    expiring_pantry_items = get_expiring_pantry_items(user)
    expiring_items_str = ', '.join(expiring_pantry_items) if expiring_pantry_items else 'None'

    previous_meals = MealPlanMeal.objects.filter(
        meal_plan__user=user,
        meal_plan__week_start_date=previous_week_start,
        meal_plan__week_end_date=previous_week_end
    ).select_related('meal')

    # Add previous meals to existing meal names and embeddings to avoid repetition
    previous_meal_names = set(previous_meals.values_list('meal__name', flat=True))
    previous_meal_embeddings = list(previous_meals.values_list('meal__meal_embedding', flat=True))

    # Combine the current and previous meals for duplication checks
    combined_meal_names = existing_meal_names.union(previous_meal_names)

    # Validate that each embedding is a valid flat list
    combined_meal_embeddings = []
    for emb in existing_meal_embeddings + previous_meal_embeddings:

        # If the embedding is a numpy array, convert it to a list
        if isinstance(emb, np.ndarray):
            emb = emb.tolist()

        # Ensure the embedding is valid (list of floats/ints of length 1536)
        if isinstance(emb, list) and all(isinstance(x, (float, int)) for x in emb) and len(emb) == 1536:
            combined_meal_embeddings.append(emb)
        else:
            # Convert numpy arrays to a string representation for logging
            logger.error(f"Invalid or malformed embedding: {emb}")
            continue  # Skip this embedding

    for attempt in range(max_attempts):  # Limit the number of attempts to avoid infinite loops
        try:
            logger.info(f"Attempt {attempt+1} to generate meal details for {meal_type}")

            # GPT API call to generate meal details
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Ensure this is the correct model name
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates a meal, its description, and dietary preferences based on information about the user. "
                            "Please ensure that the meal is unique and not similar to the existing meals, including meals from the previous week."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"The following meals have already been created: {', '.join(combined_meal_names)}. Try to create something different. "
                            f"Create a meal that meets the user's goals of {user.goal.goal_description}. "
                            f"It is meant to be served as a {meal_type} meal. "
                            f"The user has the following pantry items that are expiring soon: {expiring_items_str}. "
                            f"Please try to include these expiring items in the meal. "
                            f"Align it with the user's preferences: {generate_user_context(user)}. "
                        )
                    }
                ],
                response_format={
                    'type': 'json_schema',
                    'json_schema': {
                        "name": "Meal",
                        "schema": MealOutputSchema.model_json_schema()
                    }
                }
            )

            # Parse GPT response
            gpt_output = response.choices[0].message.content
            meal_data = json.loads(gpt_output)
            # Extract meal details
            meal_name = meal_data.get('meal', {}).get('name')
            description = meal_data.get('meal', {}).get('description')
            dietary_preference = meal_data.get('meal', {}).get('dietary_preference')
            generated_meal_type = meal_data.get('meal', {}).get('meal_type')

            # Validate extracted data
            if not meal_name or not description or not dietary_preference:
                logger.error(f"Meal data incomplete: {meal_data}. Skipping.")
                continue

            # Generate the embedding for the new meal
            meal_representation = f"Name: {meal_name}, Description: {description}, Dietary Preference: {dietary_preference}, " \
                                  f"Meal Type: {meal_type}, Chef: {user.username}, Price: 'N/A'"

            new_meal_embedding = get_embedding(meal_representation)

            # Check if a similar meal already exists based on embedding similarity
            similar_meal_found = False
            for existing_embedding in combined_meal_embeddings:
                similarity = cosine_similarity(new_meal_embedding, existing_embedding)

                if similarity > (1 - min_similarity):  # Cosine similarity closer to 1 indicates more similarity
                    similar_meal_found = True
                    logger.info(f"Similar meal found with similarity: {similarity:.2f}")
                    break  # Exit the loop if a similar meal is found

            if similar_meal_found:
                continue  # Try generating a new meal
            else:
                return {
                    'name': meal_name,
                    'description': description,
                    'dietary_preference': dietary_preference,
                    'meal_embedding': new_meal_embedding,
                }

        except Exception as e:
            logger.error(f"Unexpected error generating meal content: {e}")
            return None

    logger.error(f"Failed to generate a unique meal after {max_attempts} attempts.")
    return None


@shared_task
def update_chef_embeddings():    
    from chefs.models import Chef  # Adjust the import path based on your project structure
    for chef in Chef.objects.filter(chef_embedding__isnull=True):
        chef_str = str(chef)  # Generate the string representation for the chef
        chef.chef_embedding = get_embedding(chef_str)  # Generate and assign the new embedding
        chef.save()  # Save the updated chef

@shared_task
def update_embeddings():
    from meals.models import Meal, Dish, Ingredient  # Adjust the import path based on your project structure

    # Update meal embeddings using the comprehensive embedding function
    for meal in Meal.objects.filter(meal_embedding__isnull=True):
        meal_embedding = generate_meal_embedding(meal.id)
        if meal_embedding:
            meal.meal_embedding = meal_embedding
            meal.save()
            logger.info(f"Updated embedding for Meal ID {meal.id}")

    # Update dish embeddings (you may want to create a similar embedding function for Dish if necessary)
    for dish in Dish.objects.filter(dish_embedding__isnull=True):
        dish_embedding = get_embedding(str(dish))
        if dish_embedding:
            dish.dish_embedding = dish_embedding
            dish.save()
            logger.info(f"Updated embedding for Dish ID {dish.id}")

    # Update ingredient embeddings (again, you may want a similar embedding function for Ingredients if needed)
    for ingredient in Ingredient.objects.filter(ingredient_embedding__isnull=True):
        ingredient_embedding = get_embedding(str(ingredient))
        if ingredient_embedding:
            ingredient.ingredient_embedding = ingredient_embedding
            ingredient.save()
            logger.info(f"Updated embedding for Ingredient ID {ingredient.id}")

def serialize_data(data):
    """ Helper function to serialize data into JSON-compatible format """
    try:
        print(f"Attempting to serialize data: {data}")
        serialized_data = JSONRenderer().render(data)
        print(f"Serialized Data: {serialized_data}")
        return json.loads(serialized_data)
    except Exception as e:
        logger.error(f"Error serializing data: {e}")
        raise

@shared_task
def generate_shopping_list(meal_plan_id):
    from meals.models import MealPlan, ShoppingList as ShoppingListModel
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)

    # Serialize the meal plan data
    serializer = MealPlanSerializer(meal_plan)
    meal_plan_data = serializer.data

    # Extract user information
    user_info = meal_plan_data.get('user', {})
    user_email = user_info.get('email')
    user_name = user_info.get('username')

    # Retrieve the full user object
    user_id = meal_plan_data.get('user', {}).get('id')
    if not user_id:
        logger.error(f"User not found for MealPlan ID {meal_plan_id}.")
        return

    user = CustomUser.objects.get(id=user_id)
    
    try:
        user_pantry_items = get_user_pantry_items(user)
    except Exception as e:
        logger.error(f"Error retrieving pantry items for user {user.id}: {e}")
        user_pantry_items = []

    try:
        expiring_pantry_items = get_expiring_pantry_items(user)
        expiring_items_str = ', '.join(expiring_pantry_items) if expiring_pantry_items else 'None'
    except Exception as e:
        logger.error(f"Error retrieving expiring pantry items for user {user.id}: {e}")
        expiring_pantry_items = []

    try:
        emergency_supply_goal = user.emergency_supply_goal
    except Exception as e:
        logger.error(f"Error retrieving emergency supply goal for user {user.id}: {e}")
        emergency_supply_goal = 0

    # Determine items needed to replenish emergency supplies
    try:
        items_to_replenish = determine_items_to_replenish(user)
    except Exception as e:
        logger.error(f"Error determining items to replenish for user {user.id}: {e}")
        items_to_replenish = []

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist.")
        return

    # Generate the user context safely
    try:
        user_context = generate_user_context(user) or 'No additional user context provided.'
    except Exception as e:
        logger.error(f"Error generating user context: {e}")
        user_context = 'No additional user context provided.'

    # Initialize shopping_list variable
    shopping_list = None

    # Check if a shopping list already exists for this meal plan
    existing_shopping_list = ShoppingListModel.objects.filter(meal_plan=meal_plan).first()


    if existing_shopping_list:
        logger.info(f"Shopping list already exists for MealPlan ID {meal_plan_id}. Sending existing list.")
        shopping_list = existing_shopping_list.items
    else:
        # Generate shopping list if it doesn't exist
        try:
            user_data_json = serialize_data(meal_plan_data)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            return

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates shopping lists in JSON format."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Answering in the user's preferred language: {user_info['preferred_language']},"
                            f"Generate a shopping list based on the following meals: {json.dumps(user_data_json)}. "
                            f"The user information is as follows: {user_context}."
                            f"The user has the following items in their pantry: {', '.join(user_pantry_items)}."
                            f"The user has the following pantry items expiring soon: {expiring_items_str}."
                            f"Do not include these pantry items in the shopping list unless they need to be replenished. "
                            f"The user aims to maintain an emergency food supply for {emergency_supply_goal} days of dry and canned foods. "
                            f"Items needed to replenish the emergency supply: {', '.join(items_to_replenish)}. "                          
                        )
                    }
                ],
                response_format={
                    'type': 'json_schema',
                    'json_schema': 
                        {
                            "name":"ShoppingList", 
                            "schema": ShoppingListSchema.model_json_schema()
                        }
                    }
            )

            shopping_list = response.choices[0].message.content  # Use the parsed response

            if hasattr(meal_plan, 'shopping_list'):
                meal_plan.shopping_list.update_items(shopping_list)
            else:
                ShoppingListModel.objects.create(meal_plan=meal_plan, items=shopping_list)

        except ValidationError as e:
            logger.error(f"Error parsing shopping list: {e}")
        except Exception as e:
            logger.error(f"Unexpected error generating shopping list for meal plan {meal_plan_id}: {e}")

    try:
        shopping_list_dict = json.loads(shopping_list)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse shopping list as JSON: {e}")
        return

    # Group items by category and aggregate quantities
    categorized_items = defaultdict(lambda: defaultdict(lambda: {'quantity': 0, 'unit': '', 'notes': []}))

    for item in shopping_list_dict.get("items", []):
        logger.info(f"Shopping list item: {item}")
        category = item.get("category", "Miscellaneous")
        ingredient = item.get("ingredient")
        quantity_str = item.get("quantity", "")
        unit = item.get("unit", "")
        meal_name = item.get("meal_name", "")
        notes = item.get("notes", "")

        # Handle fractional quantities
        try:
            if '/' in quantity_str:
                numerator, denominator = quantity_str.split('/')
                quantity = float(numerator) / float(denominator)
            else:
                quantity = float(quantity_str)
        except ValueError:
            # For non-numeric quantities like "To taste", set quantity to None
            quantity = None
            logger.info(f"Non-numeric quantity '{quantity_str}' for ingredient '{ingredient}'")

        if quantity is not None:
            # Aggregate the quantities if it's a valid numeric quantity
            if categorized_items[category][ingredient]['unit'] == unit or not categorized_items[category][ingredient]['unit']:
                categorized_items[category][ingredient]['quantity'] += quantity
                categorized_items[category][ingredient]['unit'] = unit
            else:
                # If units differ, treat them as separate entries
                if categorized_items[category][ingredient]['unit']:
                    logger.warning(f"Conflicting units for {ingredient} in {category}: {categorized_items[category][ingredient]['unit']} vs {unit}")
                categorized_items[category][ingredient]['quantity'] += quantity
                categorized_items[category][ingredient]['unit'] += f" and {quantity} {unit}"

        # Add a special case for non-numeric quantities (e.g., "To taste")
        else:
            if not categorized_items[category][ingredient]['unit']:
                categorized_items[category][ingredient]['quantity'] = quantity_str  # Store the non-numeric quantity
                categorized_items[category][ingredient]['unit'] = unit  # Still keep track of the unit

        # Only add notes if they do not contain 'none' and are not None
        if notes is not None and 'none' not in notes.lower():
            categorized_items[category][ingredient]['notes'].append(f"{meal_name}: {notes} ({quantity_str} {unit})")



    # Format the shopping list into a more readable format
    formatted_shopping_list = f"""
    <html>
    <body>
        <div style="text-align: center;">
            <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
        </div>
        <h2 style="color: #333;">Your Personalized Shopping List</h2>
        <p>Dear {user_name},</p>
        <p>We're excited to help you prepare for the week ahead! Below is your personalized shopping list, thoughtfully curated to complement the delicious meals you've planned.</p>
    """

    for category, items in categorized_items.items():
        formatted_shopping_list += f"<h3 style='color: #555;'>{category}</h3>"
        formatted_shopping_list += """
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left;">Ingredient</th>
                    <th style="padding: 8px; text-align: left;">Total Quantity</th>
                    <th style="padding: 8px; text-align: left;">Notes</th>
                </tr>
            </thead>
            <tbody>
        """

        for ingredient, details in items.items():
            total_quantity = details['quantity']
            unit = details['unit']
            notes = "; ".join(details['notes'])

            formatted_shopping_list += f"""
            <tr>
                <td style="padding: 8px;">{ingredient}</td>
                <td style="padding: 8px;">{total_quantity} {unit}</td>
                <td style="padding: 8px;">{notes}</td>
            </tr>
            """

        formatted_shopping_list += """
            </tbody>
        </table>
        """

    formatted_shopping_list += """
        <p style="color: #555;">We hope this makes your shopping experience smoother and more enjoyable. If you have any questions or need further assistance, we're here to help.</p>
        <p style="color: #555;">Happy cooking!</p>
        <p style="color: #555;">Warm regards,<br>The SautAI Team</p>
    </body>
    </html>
    """

    # Add the footer with the button
    formatted_shopping_list += f"""
        <div style="text-align: center; margin-top: 40px;">
            <p style="color: #777;">You are receiving this email because you opted in for shopping list emails.</p>
            <a href="{os.getenv("STREAMLITY_URL")}/profile" style="
                display: inline-block;
                background-color: #007BFF;
                color: #fff;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-size: 16px;
                margin-top: 10px;
            ">Manage Your Email Preferences</a>
        </div>
    </body>
    </html>
    """

    if not user.email_meal_plan_saved:
        return
    
    if not shopping_list:
        logger.error(f"Failed to generate shopping list for MealPlan ID {meal_plan_id}.")
        return
    
    # Prepare data for Zapier webhook
    email_data = {
        'subject': f'Your Curated Shopping List for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
        'message': formatted_shopping_list,
        'to': user_email,
        'from': 'support@sautai.com',
    }

    # Send data to Zapier
    try:
        print(f"Sending shopping list: {email_data}")
        # zap_url = os.getenv("ZAP_GENERATE_SHOPPING_LIST_URL")  
        # requests.post(zap_url, json=email_data)
        logger.info(f"Shopping list sent to Zapier for: {user_email}")
    except Exception as e:
        logger.error(f"Error sending shopping list to Zapier for: {user_email}, error: {str(e)}")

@shared_task
def send_daily_meal_instructions():
    from meals.models import MealPlanMeal

    # Get the current time in UTC
    current_utc_time = timezone.now()

    # Loop through all users who have email_daily_instructions enabled
    users = CustomUser.objects.filter(email_daily_instructions=True)
    
    for user in users:
        # Convert current UTC time to the user's time zone
        user_timezone = pytz.timezone(user.timezone)
        user_time = current_utc_time.astimezone(user_timezone)

        # Check if it's midnight in the user's time zone
        if user_time.hour == 0:
            # Get the current day in the user's time zone
            current_day = user_time.strftime('%A')
            
            # Get the current week start and end dates
            week_start_date = user_time - timedelta(days=user_time.weekday())
            week_end_date = week_start_date + timedelta(days=6)

            # Filter MealPlanMeal instances for this user, day, and week
            meal_plan_meals_for_today = MealPlanMeal.objects.filter(
                meal_plan__user=user,
                day=current_day,
                meal_plan__week_start_date=week_start_date.date(),
                meal_plan__week_end_date=week_end_date.date(),
            )

            if user.email_daily_instructions:
                meal_plan_meal_ids = list(meal_plan_meals_for_today.values_list('id', flat=True))
                logger.debug(f"MealPlanMeal IDs for user {user.email} on {current_day}: {meal_plan_meal_ids}")
                if meal_plan_meal_ids:  # Ensure the list is not empty
                    generate_instructions.delay(meal_plan_meal_ids)
                else:
                    logger.info(f"No meals found for user {user.email} on {current_day}")


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

    # Map day names to day numbers
    day_name_to_number = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6,
    }

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
                                f"Generate detailed cooking instructions for the following meal: {meal_data_json}. "
                                f"The user has the following pantry items that are expiring soon: {expiring_items_str}. "
                                f"Ensure these expiring items are used in the cooking instructions if they are part of the meal, "
                                f"but understand that using an item decreases its quantity for other meals. "
                                f"The meal is described as follows: '{meal_plan_meal_data['meal']['description']}' and "
                                f"it adheres to the user's information: {user_context}."
                            )
                        }
                    ],
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
        day_name = meal_plan_meal.day
        day_number = day_name_to_number.get(day_name)
        if day_number is not None:
            meal_date = meal_plan_meal.meal_plan.week_start_date + timedelta(days=day_number)
        else:
            meal_date = None
            logger.error(f"Invalid day name '{day_name}' for MealPlanMeal ID {meal_plan_meal.id}")

        # Append the formatted instructions to the list
        instructions_list.append({
            'meal_name': meal_plan_meal.meal.name,
            'formatted_instructions': formatted_instructions,
            'meal_id': meal_plan_meal.id,
            'meal_type': meal_plan_meal.meal_type,
            'meal_date': meal_date,
        })

    if not instructions_list:
        logger.info(f"No instructions generated for user {user_email}")
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

    # Build the 'Meals Included' section
    meals_included = ''
    for meal_type in meal_types_order:
        if meal_type in grouped_instructions:
            meals_included += f"<li><strong>{meal_type}</strong></li><ul>"
            for item in grouped_instructions[meal_type]:
                meals_included += f"<li>{item['meal_name']}</li>"
            meals_included += "</ul>"

    # Build the 'Meals Instructions' section
    meals_content = ''
    for meal_type in meal_types_order:
        if meal_type in grouped_instructions:
            meals_content += f"<h2 style='color: #333;'>{meal_type}</h2>"
            for item in grouped_instructions[meal_type]:
                meals_content += f"""
                <h3 style="color: #333;">{item['meal_name']}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    {item['formatted_instructions']}
                </table>
                <br/>
                """


    # Final HTML Email Body
    email_body = textwrap.dedent(f"""
        <html>
        <body>
            <!-- Logo -->
            <div style="text-align: center;">
                <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
            </div>
            
            <!-- Greeting -->
            <h2 style="color: #333;">{subject}</h2>
            <p>Dear {user_name},</p>
            <p>Here are your cooking instructions for today:</p>
            
            <!-- Meals Included -->
            <h3>Meals Included</h3>
            <ul>
                {meals_included}
            </ul>
            
            <!-- Meals Instructions -->
            {meals_content}
            
            <!-- Footer -->
            <p style="color: #555;">We hope you enjoy every bite. If you need any help or have questions, feel free to reach out!</p>
            <p style="color: #555;">Bon appétit!</p>
            <p style="color: #555;">Warm regards,<br>The SautAI Team</p>
        </body>
        </html>
    """)

    email_body += """
        <div style="text-align: center; margin-top: 40px;">
            <p style="color: #777;">You are receiving this email because you opted in for cooking instructions emails.</p>
            <a href="https://sautai.com/profile" style="
                display: inline-block;
                background-color: #007BFF;
                color: #fff;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-size: 16px;
                margin-top: 10px;
            ">Manage Your Email Preferences</a>
        </div>
    </body>
    </html>
    """


    # Prepare data for Zapier webhook
    email_data = {
        'subject': subject,
        'message': email_body,
        'to': user_email,
        'from': 'support@sautai.com',
    }

    # Check if the user has disabled email instruction generation to bypass the rest of the process
    if not user.email_instruction_generation:
        logger.info(f"User {user_email} has disabled email instruction generation.")
        return
    
    # Send data to Zapier
    try:
        print(f"Sending instructions: {email_data}")
        # zap_url = os.getenv("ZAP_GENERATE_INSTRUCTIONS_URL")  
        # requests.post(zap_url, json=email_data)
        n8n_url = os.getenv("N8N_GENERATE_INSTRUCTIONS_URL")
        requests.post(n8n_url, email_data)
        logger.info(f"Cooking instructions sent to Zapier for: {user_email}")
    except Exception as e:
        logger.error(f"Error sending cooking instructions to Zapier for: {user_email}, error: {str(e)}")

@shared_task
def generate_user_summary(user_id):
    print(f'Generating summary for user {user_id}')
    from shared.utils import generate_user_context
    user = get_object_or_404(CustomUser, id=user_id)
    user_context = generate_user_context(user)
    user_summary_obj, created = UserSummary.objects.get_or_create(user=user)

    # Set status to 'pending'
    user_summary_obj.status = 'pending'
    user_summary_obj.save()

    # Calculate the date one month ago
    one_month_ago = timezone.now() - timedelta(days=30)

    # Query the models for records related to the user and within the past month, except for goals
    goal_tracking = GoalTracking.objects.filter(user=user)
    user_health_metrics = UserHealthMetrics.objects.filter(user=user, date_recorded__gte=one_month_ago)
    calorie_intake = CalorieIntake.objects.filter(user=user, date_recorded__gte=one_month_ago)

    # Format the queried data
    formatted_data = {
        "User Information": {user_context},
        "Goal Tracking": [f"Goal: {goal.goal_name}, Description: {goal.goal_description}" for goal in goal_tracking] if goal_tracking else ["No goals found."],
        "User Health Metrics": [
            f"Date: {metric.date_recorded}, Weight: {metric.weight} kg ({float(metric.weight) * 2.20462} lbs), BMI: {metric.bmi}, Mood: {metric.mood}, Energy Level: {metric.energy_level}" 
            for metric in user_health_metrics
        ] if user_health_metrics else ["No health metrics found."],
        "Calorie Intake": [f"Meal: {intake.meal_name}, Description: {intake.meal_description}, Portion Size: {intake.portion_size}, Date: {intake.date_recorded}" for intake in calorie_intake] if calorie_intake else ["No calorie intake data found."],
        "Meal Plan Approval Status": "If the user's meal plan is not approved, gently remind them to submit their meal plan for approval."
    }
    
    # Define the message for no data
    message = "No data found for the past month."

    # Initialize OpenAI client
    client = OpenAI(api_key=settings.OPENAI_KEY)
    
    # Define the language prompt based on user's preferred language
    language_prompt = {
        'en': 'English',
        'ja': 'Japanese',
        'es': 'Spanish',
        'fr': 'French',
    }
    preferred_language = language_prompt.get(user.preferred_language, 'English')
    print(f'Preferred language: {preferred_language}')
    print(f'User\'s preferred language: {user.preferred_language}')
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", 
                 "content": f"Answering in {preferred_language}, Generate a detailed summary based on the following data that gives the user a high-level view of their goals, health data, and how their caloric intake relates to those goals. Start the response off with a friendly welcoming tone. If there is no data, please respond with the following message: {message}\n\n{formatted_data}"
                 },
            ],
        )
        summary_text = response.choices[0].message.content
        user_summary_obj.summary = summary_text
        user_summary_obj.status = 'completed'
    except Exception as e:
        user_summary_obj.status = 'error'
        user_summary_obj.summary = f"An error occurred: {str(e)}"

    user_summary_obj.save()