# might have to move this to the root or the shared folder
import asyncio
import json
import os
from celery import shared_task
from django.shortcuts import get_object_or_404
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler, OpenAI
from django.conf import settings
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
                          understand_dietary_choices, is_question_relevant, create_meal)
from local_chefs.views import chef_service_areas, service_area_chefs
from rest_framework.response import Response
import re
import time
import pytz
from datetime import datetime
import logging
from openai import OpenAIError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from pydantic import BaseModel, Field, ValidationError
from typing import List
from meals.pydantic_models import ShoppingList as ShoppingListSchema, Instructions as InstructionsSchema
from rest_framework.renderers import JSONRenderer
from meals.serializers import MealPlanSerializer, MealPlanMealSerializer
from django.utils.timezone import now
import requests



logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    response = client.embeddings.create(input=[text], model=model)
    return response.data[0].embedding if response.data else None

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
    for meal in Meal.objects.filter(meal_embedding__isnull=True):
        meal.meal_embedding = get_embedding(str(meal))
        meal.save()

    for dish in Dish.objects.filter(dish_embedding__isnull=True):
        dish.dish_embedding = get_embedding(str(dish))
        dish.save()

    for ingredient in Ingredient.objects.filter(ingredient_embedding__isnull=True):
        ingredient.ingredient_embedding = get_embedding(str(ingredient))
        ingredient.save()

def serialize_data(data):
    """ Helper function to serialize data into JSON-compatible format """
    try:
        print(f"Attempting to serialize data: {data}")
        serialized_data = JSONRenderer().render(data)
        print(f"Serialized Data: {serialized_data}")
        return json.loads(serialized_data)
    except Exception as e:
        print(f"Error serializing data: {e}")
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
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates shopping lists in JSON format."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate a shopping list based on the following meals: {json.dumps(user_data_json)}. "
                            f"The user has the following dietary preferences: {user_info['user']['dietary_preference']}, "
                            f"allergies: {user_info['user']['allergies']}, custom allergies: {user_info['user']['custom_allergies']}, "
                            f"and custom dietary preferences: {user_info['user']['custom_dietary_preference']}."
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

    user = meal_plan.user
    if not user.email_meal_plan_saved:
        return

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
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left;">Meal</th>
                    <th style="padding: 8px; text-align: left;">Ingredient</th>
                    <th style="padding: 8px; text-align: left;">Quantity</th>
                    <th style="padding: 8px; text-align: left;">Notes</th>
                </tr>
            </thead>
            <tbody>
    """

    for item in shopping_list_dict.get("items", []):
        meal_name = item.get("meal_name", "General Items")
        ingredient = item.get("ingredient", "Unknown Ingredient")
        quantity = item.get("quantity", "Unknown Quantity")
        unit = item.get("unit", "")
        notes = item.get("notes", "")

        formatted_shopping_list += f"""
        <tr>
            <td style="padding: 8px;">{meal_name}</td>
            <td style="padding: 8px;">{ingredient}</td>
            <td style="padding: 8px;">{quantity} {unit}</td>
            <td style="padding: 8px;">{notes}</td>
        </tr>
        """

        logger.info(f"Meal: {meal_name}, Ingredient: {ingredient}, Quantity: {quantity} {unit}, Notes: {notes}")

    formatted_shopping_list += """
            </tbody>
        </table>
        <p style="color: #555;">We hope this makes your shopping experience smoother and more enjoyable. If you have any questions or need further assistance, we're here to help.</p>
        <p style="color: #555;">Happy cooking!</p>
        <p style="color: #555;">Warm regards,<br>The SautAI Team</p>
    </body>
    </html>
    """

    print(f"Formatted shopping list: {formatted_shopping_list}")
    
    # Prepare data for Zapier webhook
    email_data = {
        'subject': f'Your Curated Shopping List for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
        'message': formatted_shopping_list,
        'to': user_email,
        'from': 'support@sautai.com',
    }

    # Send data to Zapier
    try:
        zap_url = os.getenv("ZAP_GENERATE_SHOPPING_LIST_URL")  
        requests.post(zap_url, json=email_data)
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
            
            # Filter all MealPlanMeal instances scheduled for the current day for this user
            meal_plan_meals_for_today = MealPlanMeal.objects.filter(
                meal_plan__user=user,
                day=current_day
            )

            # Loop through each meal and send instructions
            for meal_plan_meal in meal_plan_meals_for_today:
                if user.email_daily_instructions:
                    generate_instructions.delay(meal_plan_meal.id)

@shared_task
def generate_instructions(meal_plan_meal_id):
    from meals.models import MealPlanMeal, Instruction as InstructionModel
    meal_plan_meal = get_object_or_404(MealPlanMeal, id=meal_plan_meal_id)

    # Extract user information from meal_plan_meal_data
    serializer = MealPlanMealSerializer(meal_plan_meal)
    meal_plan_meal_data = serializer.data
    user_info = meal_plan_meal_data.get('user', {})
    user_email = user_info.get('email')
    user_name = user_info.get('username')

    # Check if instructions already exist for this meal plan meal
    existing_instruction = InstructionModel.objects.filter(meal_plan_meal=meal_plan_meal).first()
    
    if existing_instruction:
        logger.info(f"Instructions already exist for MealPlanMeal ID {meal_plan_meal_id}. Sending existing instructions.")
        instructions = existing_instruction.content
    else:
        # If instructions don't exist, generate them
        user_dietary_preference = user_info.get('dietary_preference', 'Unknown')
        user_allergies = user_info.get('allergies', 'None')
        user_custom_allergies = user_info.get('custom_allergies', 'None')
        user_custom_dietary_preference = user_info.get('custom_dietary_preference', 'None')
        user_preferred_language = user_info.get('preferred_language', 'English')
        try:
            meal_data_json = json.dumps(meal_plan_meal_data)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            return

        try:
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant that generates cooking instructions in {user_preferred_language}."
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate detailed cooking instructions for the following meal: {meal_data_json}. "
                            f"The meal is described as follows: '{meal_plan_meal_data['meal']['description']}' and "
                            f"it adheres to the dietary preference: {user_dietary_preference}."
                            f"allergies: {user_allergies}, custom allergies: {user_custom_allergies}."
                            f"and custom dietary preferences: {user_custom_dietary_preference}."
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

            instructions = response.choices[0].message.content  # Use the parsed response

            if hasattr(meal_plan_meal, 'instructions'):
                meal_plan_meal.instructions.update_content(instructions)
            else:
                InstructionModel.objects.create(meal_plan_meal=meal_plan_meal, content=instructions)

        except ValidationError as e:
            logger.error(f"Error parsing instructions: {e}")
        except Exception as e:
            logger.error(f"Unexpected error generating instructions for meal plan {meal_plan_meal_id}: {e}")

    try:
        instructions_dict = json.loads(meal_plan_meal.instructions.content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse instructions as JSON: {e}")
        return
    except AttributeError as e:
        logger.error(f"Instructions content not found: {e}")
        return

    user = meal_plan_meal.meal_plan.user
    if not user.email_instruction_generation:
        return
    # Format the instructions into a more readable format
    formatted_instructions = ""
    for step in instructions_dict.get("steps", []):
        step_description = step["description"]
        duration = step.get("duration", "No specific time")
        formatted_instructions += f"""
        <tr>
            <td style="padding: 8px; font-weight: bold;">Step {step['step_number']}:</td>
            <td style="padding: 8px;">{step_description}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-style: italic;">Estimated Time:</td>
            <td style="padding: 8px;">{duration}</td>
        </tr>
        <tr><td colspan="2" style="padding: 8px; border-bottom: 1px solid #ddd;"></td></tr>
        """

    # HTML Email Body
    email_body = f"""
    <html>
    <body>
        <div style="text-align: center;">
            <img src="https://live.staticflickr.com/65535/53937452345_f4e9251155_z.jpg" alt="sautAI Logo" style="width: 200px; height: auto; margin-bottom: 20px;">
        </div>
        <h2 style="color: #333;">Step-by-Step Cooking Instructions for {meal_plan_meal.meal.name}</h2>
        <p>Dear {user_name},</p>
        <p>Get ready to cook up something delicious! Here are your step-by-step instructions:</p>
        <table style="width: 100%; border-collapse: collapse;">
            {formatted_instructions}
        </table>
        <p style="color: #555;">We hope you enjoy every bite. If you need any help or have questions, feel free to reach out!</p>
        <p style="color: #555;">Bon appétit!</p>
        <p style="color: #555;">Warm regards,<br>The SautAI Team</p>
    </body>
    </html>
    """

    # Prepare data for Zapier webhook
    email_data = {
        'subject': f'Your Cooking Instructions for {meal_plan_meal.meal.name}',
        'message': email_body,
        'to': user_email,
        'from': 'support@sautai.com',
    }
    # Send data to Zapier
    try:
        zap_url = os.getenv("ZAP_GENERATE_INSTRUCTIONS_URL")  
        requests.post(zap_url, json=email_data)
        logger.info(f"Cooking instructions sent to Zapier for: {user_email}")
    except Exception as e:
        logger.error(f"Error sending cooking instructions to Zapier for: {user_email}, error: {str(e)}")

@shared_task
def generate_user_summary(user_id):
    user = get_object_or_404(CustomUser, id=user_id)

    # Calculate the date one month ago
    one_month_ago = timezone.now() - timedelta(days=30)

    # Query the models for records related to the user and within the past month, except for goals
    goal_tracking = GoalTracking.objects.filter(user=user)
    user_health_metrics = UserHealthMetrics.objects.filter(user=user, date_recorded__gte=one_month_ago)
    calorie_intake = CalorieIntake.objects.filter(user=user, date_recorded__gte=one_month_ago)

    # Format the queried data
    formatted_data = {
        "Goal Tracking": [f"Goal: {goal.goal_name}, Description: {goal.goal_description}" for goal in goal_tracking] if goal_tracking else ["No goals found."],
        "User Health Metrics": [
            f"Date: {metric.date_recorded}, Weight: {metric.weight} kg ({float(metric.weight) * 2.20462} lbs), BMI: {metric.bmi}, Mood: {metric.mood}, Energy Level: {metric.energy_level}" 
            for metric in user_health_metrics
        ] if user_health_metrics else ["No health metrics found."],
        "Calorie Intake": [f"Meal: {intake.meal_name}, Description: {intake.meal_description}, Portion Size: {intake.portion_size}, Date: {intake.date_recorded}" for intake in calorie_intake] if calorie_intake else ["No calorie intake data found."],
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

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", 
                 "content": f"Generate a detailed summary based on the following data that gives the user a high-level view of their goals, health data, and how their caloric intake relates to those goals. Start the response off with a friendly welcoming tone. Respond in {preferred_language}. If there is no data, please respond with the following message: {message}\n\n{formatted_data}"
                 },
            ],
        )
        summary_text = response.choices[0].message.content
    except Exception as e:
        # Handle exceptions or log errors
        return {"message": f"An error occurred: {str(e)}"}

    UserSummary.objects.update_or_create(user=user, defaults={'summary': summary_text})

    return {"message": "Summary generated successfully."}