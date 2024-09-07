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
from meals.models import Meal, MealPlan, MealPlanMeal, Ingredient
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
from meals.pydantic_models import ShoppingList as ShoppingListSchema, Instructions as InstructionsSchema, MealOutputSchema, SanitySchema
from rest_framework.renderers import JSONRenderer
from meals.serializers import MealPlanSerializer, MealPlanMealSerializer
from django.utils.timezone import now
import requests
from collections import defaultdict
import numpy as np
from numpy.linalg import norm



logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

# Load configuration from config.json
with open('/etc/config.json') as config_file:
    config = json.load(config_file)

@shared_task
def test_email_task():
    email_data = {
        'subject': 'Test Email',
        'message': 'This is a test email.',
        'to': 'mleonjones@gmail.com',
        'from': 'support@sautai.com',
    }
    zap_url = config["ZAP_GENERATE_SHOPPING_LIST_URL"]
    requests.post(zap_url, json=email_data)

@shared_task
def create_meal_plan_for_new_user(user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        week_shift = user.week_shift
    except CustomUser.DoesNotExist:
        logger.error(f"User with id {user_id} does not exist.")
        return

    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    meal_plan, created = MealPlan.objects.get_or_create(
        user=user,
        week_start_date=start_of_week,
        week_end_date=end_of_week,
    )

    meal_types = ['Breakfast', 'Lunch', 'Dinner']

    # Fetch existing meals in the meal plan for context
    existing_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')

    # Create a set of meal names to avoid duplicates
    existing_meal_names = set(existing_meals.values_list('meal__name', flat=True))

    # Create a list of existing meal embeddings to avoid duplicates
    existing_meal_embeddings = list(existing_meals.values_list('meal__meal_embedding', flat=True))

    # Attempt to find similar meals already in the database before creating new ones
    for day_offset in range(7):  # 7 days in a week
        meal_date = start_of_week + timedelta(days=day_offset)
        for meal_type in meal_types:
            # Check if a meal for this day and meal type already exists
            if MealPlanMeal.objects.filter(meal_plan=meal_plan, day=meal_date.strftime('%A'), meal_type=meal_type).exists():
                continue  # Skip this meal type if it already exists for the day

            # Try finding a suitable existing meal from the database
            meal_found = find_existing_meal(user, meal_type, existing_meal_embeddings, existing_meal_names)

            if not meal_found:
                # Generate a new meal if no suitable meal is found
                meal_details = generate_meal_details(user, meal_type, existing_meal_names, existing_meal_embeddings)

                if meal_details:
                    meal_data = create_meal(
                        user_id=user_id,
                        name=meal_details.get('name'),
                        dietary_preference=meal_details.get('dietary_preference'),
                        description=meal_details.get('description'),
                        meal_type=meal_type,
                    )

                    if meal_data['status'] == 'success':
                        meal = Meal.objects.get(id=meal_data['meal']['id'])
                        
                        # Perform the OpenAI sanity check for generated meals
                        if perform_openai_sanity_check(meal, user):
                            MealPlanMeal.objects.create(
                                meal_plan=meal_plan,
                                meal=meal,
                                day=meal_date.strftime('%A'),
                                meal_type=meal_type,
                            )
                            # Add to the respective lists
                            existing_meal_names.add(meal.name)
                            existing_meal_embeddings.append(meal.meal_embedding)
                        else:
                            logger.warning(f"Generated meal {meal.name} contains allergens. Skipping.")
                    else:
                        logger.error(f"Failed to create a meal for user {user.username} on {meal_date}: {meal_data['message']}")
            elif meal_found.name and meal_found not in existing_meal_names:
                  # Perform the OpenAI sanity check on the found meal
                if perform_openai_sanity_check(meal_found, user):
                    # If the meal passes the sanity check, add it to the meal plan
                    MealPlanMeal.objects.create(
                        meal_plan=meal_plan,
                        meal=meal_found,
                        day=meal_date.strftime('%A'),
                        meal_type=meal_type,
                    )
                    existing_meal_names.add(meal_found.name)
                    existing_meal_embeddings.append(meal_found.meal_embedding)
                else:
                    logger.warning(f"Meal {meal_found.name} contains allergens. Skipping.")
    logger.info(f"Meal plan created successfully for user {user.username} for the week {start_of_week} to {end_of_week}")

def cosine_similarity(embedding1, embedding2):
    """Compute the cosine similarity between two embeddings."""
    return np.dot(embedding1, embedding2) / (norm(embedding1) * norm(embedding2))

def find_existing_meal(user, meal_type, existing_meal_embeddings, existing_meal_names, min_similarity=0.03):
    """
    Search for an existing meal that is sufficiently unique compared to existing embeddings
    and hasn't already been added to the current meal plan.
    """
    # Gather user's allergies
    user_allergies = user.allergies.split(',') if user.allergies else []
    custom_allergies = user.custom_allergies.split(',') if user.custom_allergies else []
    all_allergies = user_allergies + custom_allergies

    # Query the database for meals that match the user's dietary preferences, exclude meals with allergens
    potential_meals = Meal.objects.filter(
        dietary_preference=user.dietary_preference,
        custom_dietary_preference=user.custom_dietary_preference,
    ).exclude(
        meal_embedding__isnull=True
    ).exclude(
        name__in=existing_meal_names  # Exclude meals that have already been added to the plan
    ).exclude(
        dishes__ingredients__name__in=all_allergies  # Exclude meals with ingredients that match the user's allergens
    ).distinct()

    # If there are no existing embeddings, return any potential meal directly
    if not existing_meal_embeddings:
        if potential_meals.exists():
            return potential_meals.first()  # Return the first potential meal
        return None  # No existing meals

    # If there are existing embeddings, check for similarity
    for meal in potential_meals:
        for existing_embedding in existing_meal_embeddings:
            similarity = cosine_similarity(meal.meal_embedding, existing_embedding)
            if similarity < (1 - min_similarity):  # The closer the similarity is to 0, the more unique
                return meal  # Return the first sufficiently unique meal

    return None  # No sufficiently unique meal found

def perform_openai_sanity_check(meal, user):
    """
    Use OpenAI to generate missing ingredient data for meals and ensure allergens are avoided.
    """
    # Gather user's allergies
    user_allergies = user.allergies.split(',') if user.allergies else []
    custom_allergies = user.custom_allergies.split(',') if user.custom_allergies else []
    all_allergies = user_allergies + custom_allergies
    print(f"Checking meal: {meal.name} for user {user.username}")
    print(f"User allergies: {all_allergies}")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that checks whether a meal has the possibility of including a user's allergens and meets their preference. "
                        "If they do, you return 'False'. If they are allergen-free, you return 'True'."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"The meal is called '{meal.name}' and is described as: {meal.description}. "
                        f"The dietary preference is: {meal.dietary_preference} and/or {meal.custom_dietary_preference}. "
                        f"Please ensure none of the following allergens are present: {', '.join(all_allergies)}."
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
        print(f"GPT output: {gpt_output}")

        allergen_check = json.loads(gpt_output).get('allergen_check', False)

        if allergen_check:
            logger.info(f"Meal {meal.name} is allergen-free for user {user.username}.")
        else:
            logger.warning(f"Meal {meal.name} contains allergens for user {user.username}.")

        return allergen_check

    except Exception as e:
        logger.error(f"Error during OpenAI sanity check: {e}")
        return False  # Return False if an error occurs



def generate_meal_details(user, meal_type, existing_meal_names, existing_meal_embeddings, min_similarity=0.03):
    """
    Use GPT to generate meal details based on the user's preferences and meal type, while avoiding duplicates.
    Compare the new meal's embedding to existing meals to ensure sufficient uniqueness.
    """
    for attempt in range(5):  # Limit the number of attempts to avoid infinite loops
        try:
            # GPT API call to generate meal details
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that generates a meal, its description, and dietary preferences based on information about the user. "
                            f"The following meals have already been created: {', '.join(existing_meal_names)}. "
                            "Please ensure that the meal is unique and not similar to the existing meals."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Create a meal that meets the user's goals of {user.goal.goal_description}. "
                            f"It is meant to be served as a {meal_type} meal. "
                            f"Align it with the user's dietary preferences: {user.dietary_preference} and/or {user.custom_dietary_preference}. "
                            f"Avoid the following allergens: {user.allergies} and/or {user.custom_allergies}."
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

            gpt_output = response.choices[0].message.content
            meal_data = json.loads(gpt_output)

            meal_name = meal_data.get('meal', {}).get('name')
            description = meal_data.get('meal', {}).get('description')
            dietary_preference = meal_data.get('meal', {}).get('dietary_preference')

            # Generate the embedding for the new meal
            new_meal_embedding = get_embedding(f"{meal_name} {description} {dietary_preference}")

            # Check if a similar meal already exists based on embedding similarity
            similar_meal_found = False
            for existing_embedding in existing_meal_embeddings:
                similarity = cosine_similarity(new_meal_embedding, existing_embedding)
                if similarity > (1 - min_similarity):  # Cosine similarity closer to 1 indicates more similarity
                    similar_meal_found = True
                    break

            if similar_meal_found:
                logger.warning(f"Generated meal {meal_name} is too similar to an existing meal. Attempt {attempt + 1} of 5.")
            else:
                # Append the new embedding to the list of existing embeddings
                existing_meal_embeddings.append(new_meal_embedding)
                return {
                    'name': meal_name,
                    'description': description,
                    'dietary_preference': dietary_preference,
                    'meal_embedding': new_meal_embedding,
                }

        except Exception as e:
            logger.error(f"Unexpected error generating meal content: {e}")
            return None

    logger.error(f"Failed to generate a unique meal after 5 attempts.")
    return None




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
                            f"Answering in the user's preferred language: {user_info['preferred_language']},"
                            f"Generate a shopping list based on the following meals: {json.dumps(user_data_json)}. "
                            f"The user has the following dietary preferences: {user_info['dietary_preference']}, "
                            f"allergies: {user_info['allergies']}, custom allergies: {user_info['custom_allergies']}, "
                            f"and custom dietary preferences: {user_info['custom_dietary_preference']},"
                            
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

    # print(f"Formatted shopping list: {formatted_shopping_list}")
    
    # Prepare data for Zapier webhook
    email_data = {
        'subject': f'Your Curated Shopping List for {meal_plan.week_start_date} - {meal_plan.week_end_date}',
        'message': formatted_shopping_list,
        'to': user_email,
        'from': 'support@sautai.com',
    }

    # Send data to Zapier
    try:
        zap_url = config["ZAP_GENERATE_SHOPPING_LIST_URL"]
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
                            f"Answering in the user's preferred language: {user_preferred_language},"
                            f"Generate detailed cooking instructions for the following meal: {meal_data_json}. "
                            f"The meal is described as follows: '{meal_plan_meal_data['meal']['description']}' and "
                            f"it adheres to the dietary preference: {user_dietary_preference}."
                            f"allergies: {user_allergies}, custom allergies: {user_custom_allergies}."
                            f"and custom dietary preferences: {user_custom_dietary_preference},"
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
        zap_url = config["ZAP_GENERATE_INSTRUCTIONS_URL"]  
        requests.post(zap_url, json=email_data)
        logger.info(f"                zgrep -r 'instruction' .: {user_email}")
    except Exception as e:
        logger.error(f"Error sending cooking instructions to Zapier for: {user_email}, error: {str(e)}")

@shared_task
def generate_user_summary(user_id):
    print(f'Generating summary for user {user_id}')
    user = get_object_or_404(CustomUser, id=user_id)
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