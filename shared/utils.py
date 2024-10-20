import json
import traceback
from django.shortcuts import render, redirect
from django.urls import reverse
import pytz
from qa_app.models import FoodQA
from meals.models import CustomDietaryPreference, Dish, MealType, Meal, MealPlan, MealPlanMeal, Order, OrderMeal, Ingredient, DietaryPreference
from meals.pydantic_models import MealOutputSchema, RelevantSchema
from local_chefs.models import ChefPostalCode, PostalCode
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta, datetime
from django.db.models import Q, F
from pgvector.django import CosineDistance
from reviews.models import Review
from custom_auth.models import CustomUser, UserRole
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from local_chefs.views import chef_service_areas, service_area_chefs
import os
import openai
from openai import OpenAI
from openai import OpenAIError
from django.utils import timezone
from django.utils.formats import date_format
from django.forms.models import model_to_dict
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError
import base64
import os
import requests
import logging
import numpy as np 

with open('/etc/config.json') as config_file:
    config = json.load(config_file)


logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_dietary_preferences():
    """Loads dietary preferences from a JSON file."""
    file_path = os.path.join(settings.BASE_DIR, 'shared', 'dietary_preferences.json')
    try:
        with open(file_path, 'r') as f:
            dietary_prefs = json.load(f)
        logger.info("Dietary preferences loaded successfully.")
        return dietary_prefs
    except FileNotFoundError:
        logger.error(f"Dietary preferences file not found at {file_path}.")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding dietary preferences JSON: {e}")
        return {}

# Load dietary preferences once at startup
DIETARY_PREFERENCES = load_dietary_preferences()

def get_dietary_preference_info(preference_name):
    """Retrieve the definition and details for a given dietary preference."""
    return DIETARY_PREFERENCES.get(preference_name, None)

# shared/utils.py

def append_dietary_preference_to_json(preference_name, definition, allowed, excluded):
    """
    Appends a new dietary preference to the dietary_preferences.json file.
    """
    file_path = os.path.join(settings.BASE_DIR, 'shared', 'dietary_preferences.json')
    try:
        with open(file_path, 'r+') as f:
            data = json.load(f)
            if preference_name in data:
                logger.info(f"Dietary preference '{preference_name}' already exists in JSON.")
                return
            # Add the new preference
            data[preference_name] = {
                "description": definition,
                "allowed": allowed,
                "excluded": excluded
            }
            # Move the file pointer to the beginning and overwrite
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        logger.info(f"Dietary preference '{preference_name}' appended to dietary_preferences.json.")
    except FileNotFoundError:
        logger.error(f"Dietary preferences file not found at {file_path}.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding dietary preferences JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while appending dietary preference: {e}")

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    try:
        # Fetch the response from the embedding API
        response = client.embeddings.create(input=[text], model=model)
        
        # Log the entire response to understand what's being returned
        # logger.info(f"Embedding API response: {response}")


        embedding = response.data[0].embedding  # Access the embedding attribute

        # Log the length and type of the embedding for debugging purposes
        logger.info(f"Generated embedding type: {type(embedding)}, length: {len(embedding)}")

        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        return embedding if is_valid_embedding(embedding) else None
    except OpenAIError as e:
        logger.error(f"Error generating embedding: {e}")
        return None


    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None
    
# Kroger API
def get_base64_encoded_credentials(client_id, client_secret):
    credentials = f"{client_id}:{client_secret}"
    return base64.b64encode(credentials.encode()).decode()

def get_access_token(client_id, client_secret):
    url = "https://api-ce.kroger.com/v1/connect/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {get_base64_encoded_credentials(client_id, client_secret)}"
    }
    data = {
        "grant_type": "client_credentials",
        "scope": "product.compact"  # Adjust the scope as needed
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        # Handle error
        return None

def find_nearby_supermarkets(request, postal_code):
    url = "https://api-ce.kroger.com/v1/locations"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {get_access_token(client_id=config['KROGER_CLIENT_ID'], client_secret=config['KROGER_CLIENT_SECRET'])}"
    }
    params = {
        "filter.zipCode.near": postal_code,
        # You can adjust the radius and limit as needed
        "filter.radiusInMiles": 10,
        "filter.limit": 10
    }
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle errors
        return None


# sautAI functions
def get_week_date_range(date):
    """
    Given a date, return the start (Monday) and end (Sunday) dates of that week.
    """
    start_of_week = date - timedelta(days=date.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)       # Sunday
    return start_of_week, end_of_week

def generate_user_context(user):
    """Creates a detailed user context prompt with location, timezone, and language."""
    
    # Convert predefined dietary preferences QuerySet to a comma-separated string
    predefined_dietary_preferences = ', '.join([pref.name for pref in user.dietary_preferences.all()]) if user.dietary_preferences.exists() else "None"
    
    # Handle multiple custom dietary preferences (ManyToManyField)
    custom_preferences = user.custom_dietary_preferences.all()
    
    custom_preferences_info = []
    allowed_foods_list = []
    excluded_foods_list = []
    
    if custom_preferences.exists():
        for custom_pref in custom_preferences:
            dietary_pref_info = get_dietary_preference_info(custom_pref.name)
            if dietary_pref_info:
                custom_preferences_info.append(f"{custom_pref.name}: {dietary_pref_info['description']}")
                allowed_foods_list.extend(dietary_pref_info["allowed"])
                excluded_foods_list.extend(dietary_pref_info["excluded"])
            else:
                custom_preferences_info.append(f"Custom preference '{custom_pref.name}' is being researched and will be added soon.")
    else:
        custom_preferences_info.append("None")
    
    # Combine dietary preferences into a string
    custom_dietary_preference_str = ', '.join(custom_preferences_info)
    
    # Combine allowed and excluded foods
    allowed_foods_str = ', '.join(allowed_foods_list) if allowed_foods_list else "None"
    excluded_foods_str = ', '.join(excluded_foods_list) if excluded_foods_list else "None"
    
    # Combine allergies and custom allergies into a comma-separated string
    allergies = ', '.join(user.allergies) if user.allergies else "None"
    custom_allergies = user.custom_allergies if user.custom_allergies else "None"
    
    # Combine allergies
    combined_allergies = f"{allergies}" if custom_allergies == "None" else f"{allergies}, {custom_allergies}"
    
    # Get user goals
    goals = user.goal.goal_description if hasattr(user, 'goal') and user.goal else "None"
    
    # Get user location details from the Address model
    if hasattr(user, 'address') and user.address:
        address = user.address
        city = address.city if address.city else "Unknown City"
        state = address.state if address.state else "Unknown State"
        country = address.country.name if address.country else "Unknown Country"
    else:
        city = "Unknown City"
        state = "Unknown State"
        country = "Unknown Country"
    
    # Get user's timezone
    timezone = user.timezone if user.timezone else "UTC"
    
    # Get user's preferred language
    preferred_language = dict(CustomUser.LANGUAGE_CHOICES).get(user.preferred_language, "English")
    
    # Prepare the meals string separately using lazy imports
    try:
        from meals.models import MealPlan, MealPlanMeal
        from django.utils import timezone as django_timezone
    except ImportError as e:
        # Handle the import error if necessary
        meals_str = '\n- No current or upcoming meal plans.'
    else:
        # Get current date in user's timezone
        user_timezone = pytz.timezone(user.timezone) if user.timezone else pytz.UTC
        current_date = django_timezone.now().astimezone(user_timezone).date()
        
        # Get current week range
        current_week_start, current_week_end = get_week_date_range(current_date)
        
        # Get next week range
        next_week_start, next_week_end = get_week_date_range(current_date + timedelta(weeks=1))
        
        # Fetch MealPlan for the current week
        try:
            meal_plan = MealPlan.objects.get(
                user=user,
                week_start_date=current_week_start,
                week_end_date=current_week_end
            )
            # Check if the meal plan is approved
            approval_status = "approved" if meal_plan.is_approved else "not approved"
            
            # Fetch all MealPlanMeal instances for this MealPlan
            meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
            
            # Organize meals by day
            meals_by_day = defaultdict(list)
            for meal_plan_meal in meal_plan_meals:
                day = meal_plan_meal.day
                meal_type = meal_plan_meal.meal_type
                meal_name = meal_plan_meal.meal.name if meal_plan_meal.meal else "Unknown Meal"
                meals_by_day[day].append(f"{meal_type}: {meal_name}")
            
            # Format meals by day
            meals_info = [f"\nCurrent Week Meal Plan ({approval_status}):"]
            for day, meals in meals_by_day.items():
                meals_str_day = "; ".join(meals)
                meals_info.append(f"  - {day}: {meals_str_day}")
            
            meals_str = ''.join(meals_info)
            print(f"User meals planned for the current week: {meals_str}")
        except MealPlan.DoesNotExist:
            meals_str = '\n- No meal plan found for the current week.'
    
    # Combine all information into a structured context
    user_preferences = (
        f"User Preferences:\n"
        f"- Predefined Dietary Preferences: {predefined_dietary_preferences}\n"
        f"- Custom Dietary Preferences: {custom_dietary_preference_str}\n"
        f"- Allowed Foods: {allowed_foods_str}\n"
        f"- Excluded Foods: {excluded_foods_str}\n"
        f"- Allergies: {combined_allergies}\n"
        f"- Goals: {goals}\n"
        f"- Meals Accessible in Location: {city}, {state}, {country}\n"
        f"- Timezone: {timezone}\n"
        f"- Preferred Language: {preferred_language}\n"
        f"- User's meals planned for the current week: {meals_str}"
    )
    
    return user_preferences

def understand_dietary_choices(request):
    # Fetch all dietary preferences related to the meals
    dietary_choices = Meal.objects.values_list('dietary_preferences__name', flat=True).distinct()
    
    # Convert to a list to make it JSON-serializable
    return list(dietary_choices)

def provide_healthy_meal_suggestions(request, user_id):
    user = CustomUser.objects.get(id=user_id)

    user_info = {
        'goal_name': user.goal.goal_name,
        'goal_description': user.goal.goal_description,
        'dietary_preference': list(user.dietary_preferences.values('name'))
    }

    return user_info

def search_healthy_meal_options(request, search_term, location_id, limit=10, start=0):
    url = "https://api-ce.kroger.com/v1/products"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {get_access_token(client_id=config['KROGER_CLIENT_ID'], client_secret=config['KROGER_CLIENT_SECRET'])}"
    }
    params = {
        "filter.term": search_term,
        "filter.locationId": location_id,
        "filter.limit": limit,
        "filter.start": start
    }
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle errors
        return None

def is_question_relevant(question):
    """
    Determine if a question is relevant to the application's functionality, specifically considering health, nutrition, and diet.

    :param question: A string representing the user's question.
    :return: A boolean indicating whether the question is relevant.
    """
    print("From is_question_relevant")

    # Define application's functionalities and domains for the model to consider
    app_context = """
    The application focuses on food delivery, meal planning, health, nutrition, and diet. It allows users to:
    - Communicate with their personal AI powered dietary assistant. 
    - Create meal plans with meals geared towards their goals.
    - Search for dishes and ingredients.
    - Get personalized meal plans based on dietary preferences and nutritional goals.
    - Find chefs and meal delivery options catering to specific dietary needs.
    - Track calorie intake and provide nutrition advice.
    - Access information on healthy meal options and ingredients.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"given the {app_context} and the following question: {question}, determine if the question is relevant to the application's functionalities by returning a 'True' if relevant and 'False' if not."
            },
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': 
                {
                    "name": "Instructions", 
                    "schema": RelevantSchema.model_json_schema()
                }
            }
        )

    # Interpret the model's response
    response_content = response.choices[0].message.content
    print(f'Is Question Relevant Response: {response_content}')
    relevant = json.loads(response_content).get('relevant', False)
    return relevant

def recommend_follow_up(request, context):
    """
    Recommend follow-up prompts based on the user's interaction context.

    :param context: A string representing the user's last few interactions or context.
    :return: A list of recommended follow-up prompts or actions.
    """
    from shared.pydantic_models import FollowUpList as FollowUpSchema
    from meals.tasks import generate_user_context
    if request.data.get('user_id'):
        user_id = request.data.get('user_id')
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            user = None
    else:
        user = None

    # Set a default language
    preferred_language = 'English'  # You can choose any default language you prefer

    user_context = "The user is a guest and does not have any context, but would like to understand the basic functionalities of the application."
    if user and user.is_authenticated:
        # Update preferred_language if the user has one set
        if hasattr(user, 'preferred_language') and user.preferred_language:
            preferred_language = user.preferred_language

        user_context = generate_user_context(user)
        functions = """
            "auth_search_dishes: Search dishes in the database",
            "auth_search_chefs: Search chefs in the database and get their info",
            "auth_get_meal_plan: Get a meal plan for the current week or a future week",
            "create_meal_plan: Create a new meal plan for the user",
            "chef_service_areas: Retrieve service areas for a specified chef",
            "service_area_chefs: Search for chefs serving a user's postal code area",
            "approve_meal_plan: Approve the meal plan and proceed to payment",
            "auth_search_ingredients: Search for ingredients in the database",
            "auth_search_meals_excluding_ingredient: Search for meals excluding an ingredient",
            "search_meal_ingredients: Search the database for a meal's ingredients",
            "suggest_alternative_meals: Suggest alternative meals based on meal IDs and days of the week",
            "add_meal_to_plan: Add a meal to a specified day in the meal plan",
            "get_date: Get the current date and time",
            "list_upcoming_meals: List upcoming meals for the current week",
            "remove_meal_from_plan: Remove a meal from a specified day in the meal plan",
            "replace_meal_in_plan: Replace a meal with another on a specified day in the meal plan",
            "post_review: Post a review for a meal or a chef",
            "update_review: Update an existing review",
            "delete_review: Delete a review",
            "generate_review_summary: Generate a summary of all reviews for a meal or chef",
            "access_past_orders: Retrieve past orders for a user",
            "get_user_info: Retrieve essential information about the user",
            "get_goal: Retrieve the user's goal",
            "update_goal: Update the user's goal",
            "adjust_week_shift: Adjust the week shift forward for meal planning",
            "check_allergy_alert: Check for potential allergens in a meal",
            "track_calorie_intake: Track and log the user's daily calorie intake",
            "provide_nutrition_advice: Offer personalized nutrition advice",
            "find_nearby_supermarkets: Find nearby supermarkets based on the user's postal code",
            "search_healthy_meal_options: Search for healthy meal options at a specified supermarket location",
            "provide_healthy_meal_suggestions: Provide healthy meal suggestions based on the user's dietary preferences and health goals"
    """
    else:
        functions = """
            "guest_search_dishes: Search dishes in the database",
            "guest_search_chefs: Search chefs in the database and get their info",
            "guest_get_meal_plan: Get a meal plan for the current week",
            "guest_search_ingredients: Search ingredients used in dishes and get their info"
        """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides the user with the next prompt they should write based on given context and functions."
                },
                {
                    "role": "user",
                    "content": (
                        f"Given the following context: {context} and functions: {functions}, "
                        f"Answering in the user's language of {preferred_language},"
                        f"what prompt should a user write next? Output ONLY the recommended prompt in the first person and in a natural sentence,"
                        f"without using the function name, without quotations, and without starting the output with 'the user should write' or anything similar,"
                        f"Considering the following information about the user: {user_context},"
                    )
                }
            ],
            response_format={
                'type': 'json_schema',
                'json_schema': 
                    {
                        "name": "Recommendations", 
                        "schema": FollowUpSchema.model_json_schema()
                    }
                }
            )
        # Correct way to access the response content
        response_content = response.choices[0].message.content
        return response_content.strip().split('\n')

    except Exception as e:
        return f"An error occurred: {str(e)}"

def provide_nutrition_advice(request, user_id, **kwargs):
    try:
        print("Fetching user...")
        user = CustomUser.objects.get(id=user_id)
        print("Fetching user role...")
        user_role = UserRole.objects.get(user=user)

        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        # Fetch the user's goal
        try:
            print("Fetching goal tracking...")
            goal_tracking = GoalTracking.objects.get(user=user)
            goal_info = {
                'goal_name': goal_tracking.goal_name,
                'goal_description': goal_tracking.goal_description
            }
        except GoalTracking.DoesNotExist:
            goal_info = {'goal_name': 'None', 'goal_description': 'No goal set'}

        # Fetch the user's latest health metrics
        try:
            print("Fetching latest metrics...")
            latest_metrics = UserHealthMetrics.objects.filter(user=user).latest('date_recorded')
            health_metrics = {
                'weight': float(latest_metrics.weight) if latest_metrics.weight else None,
                'bmi': float(latest_metrics.bmi) if latest_metrics.bmi else None,
                'mood': latest_metrics.mood,
                'energy_level': latest_metrics.energy_level
            }
        except UserHealthMetrics.DoesNotExist:
            health_metrics = {'weight': 'None', 'bmi': 'None', 'mood': 'None', 'energy_level': 'None'}

        
        return {
            'status': 'success',
            'goal_info': goal_info,
            'health_metrics': health_metrics,
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except CustomUser.DoesNotExist:
        print("User does not exist.")
        return {'status': 'error', 'message': 'User not found.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        return {'status': 'error', 'message': f'An unexpected error occurred: {e}', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

#TODO: Create function to add allergies if user mentions it

def check_allergy_alert(request, user_id, **kwargs):
    print("From check_allergy_alert")
    try:
        user = CustomUser.objects.get(id=user_id)
        user_role = UserRole.objects.get(user=user)
        
        # Check if the user's current role is 'chef' and restrict access
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        # Directly return the list of allergies. Since 'user.allergies' is an ArrayField, it's already a list.
        return {'Allergens': user.allergies}
    except CustomUser.DoesNotExist:
        return "User not found."
    except UserRole.DoesNotExist:
        return "User role not found."
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return f"An unexpected error occurred: {e}"


def update_health_metrics(request, user_id, weight=None, bmi=None, mood=None, energy_level=None, **kwargs):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    try:
        # Get the latest health metrics for the user
        latest_metrics = UserHealthMetrics.objects.filter(user_id=user_id).latest('date_recorded')

        # Update the fields with the new metrics
        if weight is not None:
            latest_metrics.weight = weight
        if bmi is not None:
            latest_metrics.bmi = bmi
        if mood is not None:
            latest_metrics.mood = mood
        if energy_level is not None:
            latest_metrics.energy_level = energy_level

        # Save the updated health metrics
        latest_metrics.save()

        return "Health metrics updated successfully."
    except ObjectDoesNotExist:
        return "No health metrics found for this user."

def get_unupdated_health_metrics(request, user_id, **kwargs):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        one_week_ago = timezone.now().date() - timedelta(days=7)
        try:
            latest_metrics = UserHealthMetrics.objects.filter(
                user_id=user_id,
                date_recorded__gte=one_week_ago
            ).latest('date_recorded')

            # Check which fields are not updated
            fields_to_update = []
            if latest_metrics.weight is None:
                fields_to_update.append('weight')
            if latest_metrics.bmi is None:
                fields_to_update.append('bmi')
            if latest_metrics.mood is None:
                fields_to_update.append('mood')
            if latest_metrics.energy_level is None:
                fields_to_update.append('energy level')

            if fields_to_update:
                return f"Please update the following health metrics: {', '.join(fields_to_update)}."
            else:
                return "All health metrics are up to date for this week."
        except UserHealthMetrics.DoesNotExist:
            return "No health metrics recorded. Please update your health metrics."
    except CustomUser.DoesNotExist:
        return "User not found."
    except UserRole.DoesNotExist:
        return "User role not found."
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return f"An unexpected error occurred: {e}"

def adjust_week_shift(request, week_shift_increment, **kwargs):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        # Update the user's week shift, ensuring it doesn't go below 0
        new_week_shift = user.week_shift + week_shift_increment
        if new_week_shift < 0:
            return {'status': 'error', 'message': 'Week shift cannot be negative.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
        else:
            user.week_shift = new_week_shift
            user.save()

        return {
            'status': 'success',
            'message': f'Week shift adjusted to {new_week_shift} weeks.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except CustomUser.DoesNotExist:
        return {
            'status': 'error',
            'message': 'User not found.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'An unexpected error occurred: {e}',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def update_goal(request, goal_name, goal_description, **kwargs):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        print(f'From update_goal: {goal_name}, {goal_description}')
        # Ensure goal_name and goal_description are not empty
        if not goal_name or not goal_description:
            return {
                'status': 'error', 
                'message': 'Both goal name and description are required.',
                'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        # Get the current user's GoalTracking object or create a new one if it doesn't exist
        goal, created = GoalTracking.objects.get_or_create(user=user)

        # Update goal details
        goal.goal_name = goal_name
        goal.goal_description = goal_description
        goal.save()

        return {
            'status': 'success', 
            'message': 'Goal updated successfully.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    except CustomUser.DoesNotExist:
        return {
            'status': 'error', 
            'message': 'User not found.', 
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {
            'status': 'error', 
            'message': f'An unexpected error occurred: {e}',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }


def get_goal(request, **kwargs):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        goal = user.goal
        return {
            'status': 'success',
            'goal': model_to_dict(goal),
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except CustomUser.DoesNotExist:
        return {
            'status': 'error',
            'message': 'User not found.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except ObjectDoesNotExist:
        return {
            'status': 'error',
            'message': 'No goal set for this user.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    

def get_user_info(request, **kwargs):
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        address = Address.objects.get(user=user)
        postal_code = address.input_postalcode if address.input_postalcode else 'Not provided'
        if isinstance(postal_code, str) and postal_code.isdigit():
            postal_code = int(postal_code)

        allergies = user.allergies if user.allergies != [{}] else []

        user_info = {
            'user_id': user.id,
            'dietary_preference': list(user.dietary_preferences.values('name')),
            'week_shift': user.week_shift,
            'user_goal': user.goal.goal_description if hasattr(user, 'goal') and user.goal else 'None',
            'postal_code': postal_code,
            'allergies': allergies,  
        }
        print(f'User Info: {user_info}')
        return {'status': 'success', 'user_info': user_info, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Address.DoesNotExist:
        return {'status': 'error', 'message': 'Address not found for user.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def access_past_orders(request, user_id, **kwargs):
    try:
        # Check user authorization
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

        # Find meal plans within the week range with specific order statuses
        meal_plans = MealPlan.objects.filter(
            user_id=user_id,
            order__status__in=['Completed', 'Cancelled', 'Refunded']
        )

        # If no meal plans are found, return a message
        if not meal_plans.exists():
            return {'status': 'info', 'message': "No meal plans found for the current week.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        # Retrieve orders associated with the meal plans
        orders = Order.objects.filter(meal_plan__in=meal_plans)

        # If no orders are found, return a message indicating this
        if not orders.exists():
            return {'status': 'info', 'message': "No past orders found.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        # Prepare order data
        orders_data = []
        for order in orders:
            order_meals = order.ordermeal_set.all()
            if not order_meals:
                continue
            meals_data = [{'meal_id': om.meal.id, 'quantity': om.quantity} for om in order_meals]
            order_data = {
                'order_id': order.id,
                'order_date': order.order_date.strftime('%Y-%m-%d'),
                'status': order.status,
                'total_price': order.total_price() if order.total_price() is not None else 0,
                'meals': meals_data
            }
            orders_data.append(order_data)
        return {'orders': orders_data, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except KeyError as e:
        return {'status': 'error', 'message': f"Missing parameter: {str(e)}"}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': "User not found."}
    except UserRole.DoesNotExist:
        return {'status': 'error', 'message': "User role not found."}
    except Exception as e:
        return {'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"}    

def post_review(request, user_id, content, rating, item_id, item_type):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})
    
    # Find the content type based on item_type
    if item_type == 'chef':
        content_type = ContentType.objects.get_for_model(Chef)
        # Check if the user has purchased a meal from the chef
        if not Meal.objects.filter(chef__id=item_id, ordermeal__order__customer_id=user_id).exists():
            return {'status': 'error', 'message': 'You have not purchased a meal from this chef.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    elif item_type == 'meal':
        content_type = ContentType.objects.get_for_model(Meal)
        # Check if the order status for the reviewed item is either 'Completed', 'Cancelled', or 'Refunded'
        if not OrderMeal.objects.filter(meal_id=item_id, order__customer_id=user_id, order__status__in=['Completed', 'Cancelled', 'Refunded']).exists():
            return {'status': 'error', 'message': 'You have not completed an order for this meal.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    else:
        return {'status': 'error', 'message': 'Only meals and chefs can be reviewed.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Create and save the review
    review = Review(
        user_id=user_id, 
        content=content, 
        rating=rating, 
        content_type=content_type, 
        object_id=item_id
    )
    review.save()

    return {'status': 'success', 'message': 'Review posted successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def update_review(request, review_id, updated_content, updated_rating):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    if user.id != Review.objects.get(id=review_id).user.id:
        return {'status': 'error', 'message': 'You are not authorized to update this review.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    review = Review.objects.get(id=review_id)
    review.content = updated_content
    review.rating = updated_rating
    review.save()

    return {'status': 'success', 'message': 'Review updated successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def delete_review(request, review_id):
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    if user.id != Review.objects.get(id=review_id).user.id:
        return {'status': 'error', 'message': 'You are not authorized to delete this review.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    review_id = request.POST.get('review_id')

    review = Review.objects.get(id=review_id)
    review.delete()

    return {'status': 'success', 'message': 'Review deleted successfully', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

#TODO: turn this into a celery task coupled with a signal
def generate_review_summary(object_id, category):
    # Step 1: Fetch all the review summaries for a specific chef or meal
    content_type = ContentType.objects.get(model=category)
    model_class = content_type.model_class()
    reviews = Review.objects.filter(content_type=content_type, object_id=object_id)

    if not reviews.exists():
        return {"message": "No reviews found.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Step 2: Format the summaries naturally
    formatted_summaries = "Review summaries:\n"
    for review in reviews:
        formatted_summaries += f" - {review.content}\n"

    # Step 3: Feed the formatted string into GPT-3.5-turbo-1106 to generate the overall summary
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": formatted_summaries}],
        )
        overall_summary = response['choices'][0]['message']['content']
    except OpenAIError as e:
        return {"message": f"An error occurred: {str(e)}", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Step 4: Store the overall summary in the database
    obj = model_class.objects.get(id=object_id)
    obj.review_summary = overall_summary
    obj.save()

    
    # Step 5: Return the overall summary
    return {"overall_summary": overall_summary, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

# Function to generate a summarized title
def generate_summary_title(question):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates concise titles for chat conversations."
                },
                {
                    "role": "user",
                    "content": f"Summarize this question for a chat title: {question}"
                }
            ],
        )
        summary = response.choices[0].message.content
        return summary
    except OpenAIError as e:
        print(f"Error generating summary: {str(e)}")
        return question[:254]  # Fallback to truncating the question if an error occurs


def list_upcoming_meals(request, **kwargs):
    print(f'From list_upcoming_meals: {request.data.get("user_id")}')
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    # Calculate the current week's start and end dates based on week_shift
    week_shift = max(int(user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = current_date - timedelta(days=current_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Filter meals by dietary preferences, postal code, and current week
    dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date__range=[start_of_week, end_of_week])
    postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date__range=[start_of_week, end_of_week])

    # Combine both filters
    filtered_meals = dietary_filtered_meals & postal_filtered_meals

    # Compile meal details
    meal_details = [
        {
            "meal_id": meal.id,
            "name": meal.name,
            "start_date": meal.start_date.strftime('%Y-%m-%d') if meal.start_date else 'N/A',
            "is_available": meal.can_be_ordered(),
            "chef": meal.chef.user.username if meal.chef else 'User Created Meal',
            "meal_type": meal.mealplanmeal_set.first().meal_type if meal.mealplanmeal_set.first() else 'N/A',
            # Add more details as needed
        } for meal in filtered_meals
    ]

    # Return a dictionary instead of JsonResponse
    return {
        "upcoming_meals": meal_details,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def create_meal_plan(request, **kwargs):
    print("From create_meal_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Calculate the week's date range which also works if user shifts week
    week_shift = max(int(user.week_shift), 0)  # Ensure week_shift is not negative
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)


    # Check if a MealPlan already exists for the specified week
    if not MealPlan.objects.filter(user=user, week_start_date=start_of_week, week_end_date=end_of_week).exists():
        # Create a new MealPlan for the remaining days in the week
        meal_plan = MealPlan.objects.create(
            user=user,
            week_start_date=start_of_week,
            week_end_date=end_of_week,
            created_date=timezone.now()
        )
        return {'status': 'success', 'message': 'Created new meal plan. It is currently empty.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {'status': 'error', 'message': 'A meal plan already exists for this week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def replace_meal_in_plan(request, meal_plan_id, old_meal_id, new_meal_id, day, meal_type, **kwargs):
    logger.info("Initiating meal replacement process for user.")
    
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
    except CustomUser.DoesNotExist:
        logger.error(f"User with ID {request.data.get('user_id')} not found.")
        return {'status': 'error', 'message': 'User not found.'}
    
    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        logger.error(f"Meal plan with ID {meal_plan_id} not found for user {user.username}.")
        return {'status': 'error', 'message': 'Meal plan not found.'}
    
    # Validate old and new meals
    try:
        old_meal = Meal.objects.get(id=old_meal_id)
        new_meal = Meal.objects.get(id=new_meal_id)
    except Meal.DoesNotExist as e:
        logger.error(f"Meal not found: {str(e)}")
        return {'status': 'error', 'message': f'Meal not found: {str(e)}'}
    
    # Validate day and meal type
    if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
        logger.error(f"Invalid day: {day}.")
        return {'status': 'error', 'message': f'Invalid day: {day}. Accepted days are: {", ".join(dict(MealPlanMeal.DAYS_OF_WEEK).keys())}'}
    
    if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
        logger.error(f"Invalid meal type: {meal_type}.")
        return {'status': 'error', 'message': f'Invalid meal type (BREAKFAST, LUNCH, DINNER): {meal_type}. Accepted types are: {", ".join(dict(MealPlanMeal.MEAL_TYPE_CHOICES).keys())}'}
    
    # Transaction block to ensure atomicity
    try:
        with transaction.atomic():
            # Use update_or_create to atomically update or create the MealPlanMeal
            meal_plan_meal, created = MealPlanMeal.objects.update_or_create(
                meal_plan=meal_plan,
                day=day,
                meal_type=meal_type,
                defaults={'meal': new_meal}
            )
            
            if created:
                logger.info(f"Created new MealPlanMeal: {meal_plan_meal}")
            else:
                logger.info(f"Updated existing MealPlanMeal: {meal_plan_meal}")
            
            logger.info(f"Replaced meal '{old_meal.name}' with '{new_meal.name}' for {meal_type} on {day}.")
    
    except IntegrityError as e:
        logger.error(f"IntegrityError while replacing meal: {e}")
        logger.error(traceback.format_exc())
        return {'status': 'error', 'message': 'A meal for this day and meal type already exists.'}
    
    except Exception as e:
        logger.error(f"Unexpected error while replacing meal: {e}")
        logger.error(traceback.format_exc())
        return {'status': 'error', 'message': 'An unexpected error occurred during meal replacement.'}
    
    return {
        'status': 'success',
        'message': 'Meal replaced successfully.',
        'replaced_meal': {
            'old_meal': old_meal.name,
            'new_meal': new_meal.name,
            'day': day,
            'meal_type': meal_type
        }
    }


def remove_meal_from_plan(request, meal_plan_id, meal_id, day, meal_type, **kwargs):
    print("From remove_meal_from_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))

    # Retrieve the specified MealPlan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    # Retrieve the specified Meal
    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

    # Validate the day
    if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
        return {'status': 'error', 'message': f'Invalid day: {day}'}
    
    # Validate the meal type
    if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
        return {'status': 'error', 'message': f'Invalid meal type: {meal_type}'}

    # Check if the meal is scheduled for the specified day and meal type in the meal plan
    logger.info(f"Checking if meal is scheduled for the specified day and meal type in the meal plan query: {MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type).query}")
    meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type).first()
    if not meal_plan_meal:
        return {'status': 'error', 'message': 'Meal not scheduled on the specified day and meal type.'}

    # Remove the meal from the meal plan
    meal_plan_meal.delete()
    return {'status': 'success', 'message': 'Meal removed from the plan.'}


def cosine_similarity(vec1, vec2):
    """
    Calculate the cosine similarity between two vectors (lists of floats).
    Uses numpy for the calculation but expects the input vectors as plain lists. 
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    if vec1.shape != vec2.shape:
        raise ValueError("Vectors must have the same length to compute cosine similarity.")
    
    dot_product = np.dot(vec1, vec2)
    magnitude_vec1 = np.linalg.norm(vec1)
    magnitude_vec2 = np.linalg.norm(vec2)
    
    if magnitude_vec1 == 0 or magnitude_vec2 == 0:
        return 0.0
    
    return dot_product / (magnitude_vec1 * magnitude_vec2)


def is_valid_embedding(embedding, expected_length=1536):
    """
    Validate that the embedding is a flat list of floats with the expected length.
    """
    if not isinstance(embedding, list):
        logger.error(f"Embedding is not a list. Type: {type(embedding)}")
        logger.error("Embedding is not a list.")
        return False
    if len(embedding) != expected_length:
        logger.error(f"Embedding length {len(embedding)} does not match expected {expected_length}.")
        return False
    if not all(isinstance(x, float) for x in embedding):
        logger.error("Embedding contains non-float elements.")
        return False
    return True

def create_meal(request=None, user_id=None, name=None, dietary_preference=None, description=None, meal_type=None, max_attempts=3, **kwargs):
    from meals.tasks import assign_dietary_preferences
    attempt = 0
    while attempt < max_attempts:
        try:
            # Step 1: Retrieve the user
            if request:
                try:
                    user = CustomUser.objects.get(id=request.data.get('user_id'))
                    user_context = generate_user_context(user)
                except CustomUser.DoesNotExist:
                    logger.error(f"User with id {request.data.get('user_id')} does not exist.")
                    return {'status': 'error', 'message': 'User does not exist'}
            elif user_id:
                try:
                    user = CustomUser.objects.get(id=user_id)
                    # Generate the user context here
                    user_context = generate_user_context(user)
                except CustomUser.DoesNotExist:
                    logger.error(f"User with id {user_id} does not exist.")
                    return {'status': 'error', 'message': 'User does not exist'}
            else:
                logger.error("Either request or user_id must be provided.")
                return {'status': 'error', 'message': 'User identification is missing'}

            with transaction.atomic():
                # Step 2: Check for existing meal
                if name:
                    existing_meal = Meal.objects.filter(creator=user, name=name).first()
                    if existing_meal:
                        return {
                            'meal': {
                                'id': existing_meal.id,
                                'name': existing_meal.name,
                                'dietary_preferences': [pref.name for pref in existing_meal.dietary_preferences.all()],
                                'description': existing_meal.description,
                                'created_date': existing_meal.created_date.isoformat(),
                            },
                            'status': 'info',
                            'message': 'A similar meal already exists.',
                            'similar_meal_id': existing_meal.id
                        }


                # Step 3: Generate meal details using GPT, including user context
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant that generates a meal, its description, and dietary preferences based on information about the user."
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"Create the meal {name}, that meets the user's goals of {user.goal.goal_description}. "
                                    f"It is meant to be served as a {meal_type} meal. "
                                    f"{user_context} "
                                )
                            }
                        ],
                        response_format={
                            'type': 'json_schema',
                            'json_schema': 
                                {
                                    "name": "Meal", 
                                    "schema": MealOutputSchema.model_json_schema()
                                }
                        }
                    )

                    # Parse GPT response
                    gpt_output = response.choices[0].message.content
                    meal_data = json.loads(gpt_output)
                    logger.info(f"Generated meal data: {meal_data}")

                    # Extract meal details
                    meal_name = meal_data.get('meal', {}).get('name', 'Meal Placeholder')
                    description = meal_data.get('meal', {}).get('description', 'Placeholder description')
                    dietary_preference = meal_data.get('meal', {}).get('dietary_preference', "None")
                    generated_meal_type = meal_data.get('meal', {}).get('meal_type', 'Dinner')

                except Exception as e:
                    logger.error(f"Error generating meal content: {e}")
                    meal_name = "Fallback Meal Name"
                    description = "Fallback Description"
                    generated_meal_type = 'Dinner'
                    dietary_preference = "None"

                # Step 4: Create the Meal instance without dietary preferences
                meal = Meal(
                    name=meal_name,
                    creator=user,
                    description=description,
                    meal_type=generated_meal_type,
                    created_date=timezone.now(),
                )
                meal.save()
                logger.info(f"Meal '{meal.name}' saved successfully with ID {meal.id}.")

                # Step 5: Assign dietary preferences
                # Fetch and assign the regular dietary preferences
                if dietary_preference != "None":
                    assign_dietary_preferences(meal.id)
                    meal.save()

                # Fetch and assign the custom dietary preferences
                custom_prefs = user.custom_dietary_preferences.all()
                if custom_prefs.exists():
                    meal.custom_dietary_preferences.add(*custom_prefs)
                    logger.info(f"Assigned custom dietary preferences: {[cp.name for cp in custom_prefs]}")


                # Step 6: Generate and assign the embedding
                meal_representation = (
                    f"Name: {meal.name}, Description: {meal.description}, Dietary Preference: {dietary_preference}, "
                    f"Meal Type: {meal.meal_type}, Chef: {user.username}, Price: {meal.price if meal.price else 'N/A'}"
                )
                meal_embedding = get_embedding(meal_representation)

                if isinstance(meal_embedding, list) and len(meal_embedding) == 1536:
                    meal.meal_embedding = meal_embedding
                    meal.save(update_fields=['meal_embedding'])
                    logger.info(f"Meal embedding assigned successfully for '{meal.name}'.")
                else:
                    logger.error(f"Invalid embedding generated for meal '{meal.name}'. Expected list of length 1536.")
                    attempt += 1
                    continue  # Retry


                # Step 8: Prepare the response
                meal_dict = {
                    'id': meal.id,
                    'name': meal.name,
                    'dietary_preferences': [pref.name for pref in meal.dietary_preferences.all()] or [cp.name for cp in meal.custom_dietary_preferences.all()],
                    'description': meal.description,
                    'meal_type': meal.meal_type,
                    'created_date': meal.created_date.isoformat(),
                }
                return {
                    'meal': meal_dict,
                    'status': 'success',
                    'message': 'Meal created successfully',
                    'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                }

        except IntegrityError as e:
            logger.error(f"IntegrityError during meal creation: {e}")
            attempt += 1  # Increment attempt count and retry
        except Exception as e:
            logger.error(f"Unexpected error during meal creation: {e}")
            traceback.print_exc()
            return {'status': 'error', 'message': 'An unexpected error occurred during meal creation.'}

    return {'status': 'error', 'message': 'Maximum attempts reached. Could not create a unique meal.'}


def add_meal_to_plan(request, meal_plan_id, meal_id, day, meal_type, allow_duplicates=False, **kwargs):
    print("From add_meal_to_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

    # Check if the meal can be ordered
    if meal.chef and not meal.can_be_ordered():
        message = (
            f'Meal "{meal.name}" cannot be ordered as it starts tomorrow or earlier. '
            'To avoid food waste, chefs need at least 24 hours to plan and prepare the meals.'
        )
        return {'status': 'error', 'message': message}

    # Check if the meal's start date falls within the meal plan's week
    if meal.chef and (meal.start_date < meal_plan.week_start_date or meal.start_date > meal_plan.week_end_date):
        return {'status': 'error', 'message': 'Meal not available in the selected week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check if the day is within the meal plan's week
    day_of_week_number = datetime.strptime(day, '%A').weekday()
    target_date = meal_plan.week_start_date + timedelta(days=day_of_week_number)
    if target_date < meal_plan.week_start_date or target_date > meal_plan.week_end_date:
        return {'status': 'error', 'message': 'Invalid day for the meal plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check for existing meals on the same day, and of the same type
    existing_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day, meal_type=meal_type).first()
    if existing_meal and not allow_duplicates:
        return {
            'status': 'prompt',
            'message': 'This day already has a meal scheduled. Would you like to replace it?',
            'existing_meal': {
                'meal_id': existing_meal.meal.id,
                'name': existing_meal.meal.name,
                'chef': existing_meal.meal.chef.user.username if existing_meal.meal.chef else 'User Created Meal'
            }
        }

    # Prevent any duplicate meals within the same meal plan week, regardless of day/meal type
    week_duplicate_meal = MealPlanMeal.objects.filter(
        meal_plan=meal_plan, 
        meal=meal
    ).exists()
    if week_duplicate_meal and not allow_duplicates:
        return {
            'status': 'error',
            'message': f'This meal "{meal.name}" is already included in the meal plan for this week.',
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    # Add the meal to the plan if no duplicates are found, or duplicates are allowed
    MealPlanMeal.objects.create(meal_plan=meal_plan, meal=meal, day=day, meal_type=meal_type)
    
    return {'status': 'success', 'action': 'added', 'new_meal': meal.name, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def suggest_alternative_meals(request, meal_ids, days_of_week, meal_types, **kwargs):
    print(f'From suggest_alternative_meals: {meal_ids}, {days_of_week}, {meal_types}')
    """
    Suggest alternative meals based on a list of meal IDs, corresponding days of the week, and meal types.
    """
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

    alternative_meals = []
    week_shift = max(int(user.week_shift), 0)  # User's ability to plan for future weeks

    today = timezone.now().date() + timedelta(weeks=week_shift)  # Adjust today's date based on week_shift
    current_weekday = today.weekday()

    # Map of day names to numbers
    day_to_number = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    for meal_id, day_of_week, meal_type in zip(meal_ids, days_of_week, meal_types):

        # Get the day number from the map
        day_of_week_number = day_to_number.get(day_of_week)
        if day_of_week_number is None:
            continue

        days_until_target = (day_of_week_number - current_weekday + 7) % 7
        target_date = today + timedelta(days=days_until_target)

        # Filter meals by dietary preferences, postal code, current week, and meal type
        dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date=target_date, mealplanmeal__meal_type=meal_type).exclude(id=meal_id)
        postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date=target_date, mealplanmeal__meal_type=meal_type).exclude(id=meal_id)

        # Combine both filters
        available_meals = dietary_filtered_meals & postal_filtered_meals

        # Compile meal details
        for meal in available_meals:
            meal_details = {
                "meal_id": meal.id,
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.can_be_ordered(),
                "chef": meal.chef.user.username,
                "meal_type": meal_type  # Include meal type
            }
            alternative_meals.append(meal_details)

    return {"alternative_meals": alternative_meals}

def replace_meal_based_on_preferences(request, meal_plan_id, old_meal_ids, days_of_week, meal_types, **kwargs):
    logging.info(f"Starting meal replacement for MealPlan ID: {meal_plan_id}")
    
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    
    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        logging.error(f"Meal plan with ID {meal_plan_id} not found for user {user.id}.")
        return {'status': 'error', 'message': 'Meal plan not found.'}

    # Check if the meal plan is linked to a placed order
    if meal_plan.order:
        logging.error(f"Meal plan with ID {meal_plan_id} is associated with a placed order and cannot be modified.")
        return {'status': 'error', 'message': 'Cannot modify a meal plan associated with an order.'}

    replaced_meals = []
    errors = []

    for old_meal_id, day, meal_type in zip(old_meal_ids, days_of_week, meal_types):
        try:
            # Log the current meal being processed
            logging.info(f"Processing meal with ID: {old_meal_id} for {day} - {meal_type}")

            # Validate the existing meal
            old_meal = Meal.objects.get(id=old_meal_id)

            # Validate day and meal type
            if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
                errors.append(f'Invalid day: {day} for meal ID {old_meal_id}')
                continue
            if meal_type not in dict(MealPlanMeal.MEAL_TYPE_CHOICES):
                errors.append(f'Invalid meal type: {meal_type} for meal ID {old_meal_id}')
                continue

            # Check if the meal is scheduled for the specified day and meal type
            meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=old_meal, day=day, meal_type=meal_type).first()
            if not meal_plan_meal:
                errors.append(f'The initial meal with ID {old_meal_id} is not scheduled on {day} and {meal_type}.')
                continue

            # Suggest alternatives or create a new meal based on user preferences and restrictions
            suggested_meals_response = suggest_alternative_meals(request, [old_meal_id], [day], [meal_type])

            if suggested_meals_response['alternative_meals']:
                # If alternatives are found, select the first one as the replacement
                new_meal_id = suggested_meals_response['alternative_meals'][0]['meal_id']
            else:
                # If no alternatives found, create a new meal
                new_meal_response = create_meal(request, name=None, dietary_preference=user.dietary_preferences, description=None, meal_type=meal_type)
                new_meal_id = new_meal_response['meal']['id']

            # Remove the old meal from the plan
            remove_meal_response = remove_meal_from_plan(request, meal_plan_id, old_meal_id, day, meal_type)
            if remove_meal_response['status'] != 'success':
                errors.append(f'Failed to remove the old meal with ID {old_meal_id}.')
                continue

            # Add the new meal to the plan
            add_meal_response = add_meal_to_plan(request, meal_plan_id, new_meal_id, day, meal_type)
            if add_meal_response['status'] != 'success':
                errors.append(f'Failed to add the new meal for {day} and {meal_type}.')
                continue

            # Collect information about the replaced meal
            replaced_meals.append({
                'old_meal': old_meal.name,
                'new_meal_id': new_meal_id,
                'day': day,
                'meal_type': meal_type
            })

        except Meal.DoesNotExist:
            logging.error(f"Old meal with ID {old_meal_id} not found.")
            errors.append(f'Old meal with ID {old_meal_id} not found.')
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing meal with ID {old_meal_id}: {str(e)}")
            errors.append(f'An unexpected error occurred while processing meal with ID {old_meal_id}.')

    if errors:
        return {
            'status': 'error',
            'message': 'Some meals could not be replaced.',
            'errors': errors,
            'replaced_meals': replaced_meals
        }
    else:
        return {
            'status': 'success',
            'message': 'All meals replaced successfully.',
            'replaced_meals': replaced_meals
        }

def find_similar_meals(query_vector, threshold=0.1):
    # Find meals with similar embeddings using cosine similarity
    similar_meals = Meal.objects.annotate(
        similarity=CosineDistance(F('meal_embedding'), query_vector)
    ).filter(similarity__lt=threshold)  # Adjust the threshold according to your needs
    
    return similar_meals

def search_meal_ingredients(request, query, **kwargs):
    print("From search_meal_ingredients")
    print(f"Query: {query}")
    
    # Check if the query is valid
    if not query or not isinstance(query, str):
        return {'status': 'error', 'message': 'Invalid search query.'}

    try:
        # Generate the embedding for the search query
        query_vector = get_embedding(query)
    except Exception as e:
        return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

    
    # Find meals with similar embeddings using cosine similarity
    similar_meals = Meal.objects.annotate(
        similarity=CosineDistance(F('meal_embedding'), query_vector)
    ).filter(similarity__lt=0.1)  # Adjust the threshold according to your needs

    if not similar_meals.exists():
        return {"error": "No meals found matching the query.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    result = []
    for meal in similar_meals:
        meal_ingredients = {
            "meal_id": meal.id,
            "meal_name": meal.name,
            "similarity": meal.similarity,  # Include similarity score in the response
            "dishes": []
        }
        print(f"Meal: {meal}")
        for dish in meal.dishes.all():
            dish_detail = {
                "dish_name": dish.name,
                "ingredients": [ingredient.name for ingredient in dish.ingredients.all()]
            }

            meal_ingredients["dishes"].append(dish_detail)

        result.append(meal_ingredients)

    return {
        "result": result
    }

def auth_search_meals_excluding_ingredient(request, query, **kwargs):
    print("From auth_search_meals_excluding_ingredient")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})

    
        # Determine the current date
        week_shift = max(int(user.week_shift), 0)  # Ensure week_shift is not negative
        current_date = timezone.now().date() + timedelta(weeks=week_shift)

        # Find dishes containing the excluded ingredient
        dishes_with_excluded_ingredient = Dish.objects.filter(
            ingredients__name__icontains=query
        ).distinct()

        # Filter meals available for the current week and for the user, excluding those with the unwanted ingredient
        meal_filter_conditions = Q(start_date__gte=current_date)

        # Filter meals by dietary preferences, postal code, and current week
        dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(meal_filter_conditions)
        postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(meal_filter_conditions)

        # Combine both filters
        available_meals = dietary_filtered_meals & postal_filtered_meals
        available_meals = available_meals.exclude(dishes__in=dishes_with_excluded_ingredient)

        # Compile meal details
        meal_details = []
        for meal in available_meals:
            meal_detail = {
                "meal_id": meal.id,
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.can_be_ordered(),
                "chef": {
                    "id": meal.chef.id,
                    "name": meal.chef.user.username
                },
                "dishes": [{"id": dish.id, "name": dish.name} for dish in meal.dishes.all()]
            }
            meal_details.append(meal_detail)

        if not meal_details:
            return {
                "message": "No meals found without the specified ingredient for this week.",
                "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        return {
            "result": meal_details,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred'}

def auth_search_ingredients(request, query, **kwargs):
    print("From auth_search_ingredients")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)

        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        # Find similar ingredients based on cosine similarity
        similar_ingredients = Ingredient.objects.annotate(
            similarity=CosineDistance(F('ingredient_embedding'), query_vector)
        ).filter(similarity__lt=0.1)  # Adjust the threshold based on your needs

        # Get IDs of similar ingredients
        similar_ingredient_ids = similar_ingredients.values_list('id', flat=True)

        # Find dishes containing similar ingredients
        dishes_with_similar_ingredients = Dish.objects.filter(ingredients__in=similar_ingredient_ids).distinct()

        # Find meals containing those dishes
        meals_with_similar_ingredients = Meal.objects.filter(dishes__in=dishes_with_similar_ingredients)

        # Prepare the result
        result = []
        for meal in meals_with_similar_ingredients:
            meal_info = {
                'meal_id': meal.id,
                'name': meal.name,
                'start_date': meal.start_date.strftime('%Y-%m-%d'),
                'is_available': meal.can_be_ordered(),
                'chefs': list(meal.chef.values('id', 'user__username')),
                'dishes': list(meal.dishes.values('id', 'name', 'ingredients__id', 'ingredients__name')),
            }
            result.append(meal_info)

        if not result:
            return {
                "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
                "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        return {
            "result": result,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def guest_search_ingredients(request, query, meal_ids=None, **kwargs):
    print("From guest_search_ingredients")
    try:
        current_date = timezone.now().date()
        available_meals = Meal.objects.filter(start_date__gte=current_date)

        if meal_ids:
            available_meals = available_meals.filter(id__in=meal_ids)
        
        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        # Find similar ingredients based on cosine similarity
        similar_ingredients = Ingredient.objects.annotate(
            similarity=CosineDistance(F('ingredient_embedding'), query_vector)
        ).filter(similarity__lt=0.1)  # Adjust the threshold based on your needs

        # Get IDs of similar ingredients
        similar_ingredient_ids = similar_ingredients.values_list('id', flat=True)

        # Find dishes containing similar ingredients
        dishes_with_similar_ingredients = Dish.objects.filter(ingredients__in=similar_ingredient_ids).distinct()

        # Find meals containing those dishes
        meals_with_similar_ingredients = Meal.objects.filter(dishes__in=dishes_with_similar_ingredients)

        # Prepare the result
        result = []
        for meal in meals_with_similar_ingredients:
            meal_info = {
                'meal_id': meal.id,
                'name': meal.name,
                'start_date': meal.start_date.strftime('%Y-%m-%d'),
                'is_available': meal.can_be_ordered(),
                'chefs': list(meal.chef.values('id', 'user__username')),
                'dishes': list(meal.dishes.values('id', 'name', 'ingredients__id', 'ingredients__name')),
            }
            result.append(meal_info)

        if not result:
            return {
                "message": "No meals found containing the queried ingredient(s) in the available meals for this week.",
                "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        return {
            "result": result,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def auth_search_chefs(request, query, **kwargs):
    print("From auth_search_chefs")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        # Retrieve user's primary postal code from Address model
        user_addresses = Address.objects.filter(user=user.id)
        user_postal_code = user_addresses[0].input_postalcode if user_addresses.exists() else None
        
        # Retrieve chefs based on cosine similarity with the query embedding
        similar_chefs = Chef.objects.annotate(
            similarity=CosineDistance(F('chef_embedding'), query_vector)
        ).filter(similarity__lt=0.1)  # Adjust threshold based on your needs
        # Add additional filters based on user's preferences and location
        if user.dietary_preference:
            similar_chefs = similar_chefs.filter(meals__dietary_preference=user.dietary_preference)
        if user_postal_code:
            similar_chefs = similar_chefs.filter(serving_postalcodes__code=user_postal_code)
        
        similar_chefs = similar_chefs.distinct()

        auth_chef_result = []
        for chef in similar_chefs:
            featured_dishes = []
            # Retrieve service areas for each chef
            postal_codes_served = chef.serving_postalcodes.values_list('code', flat=True)

            # Check if chef serves user's area
            serves_user_area = user_postal_code in postal_codes_served if user_postal_code else False

            for dish in chef.featured_dishes.all():
                dish_meals = Meal.objects.filter(dishes__id=dish.id)
                dish_info = {
                    "id": dish.id,
                    "name": dish.name,
                    "meals": [
                        {
                            "meal_id": meal.id,
                            "meal_name": meal.name,
                            "start_date": meal.start_date.strftime('%Y-%m-%d'),
                            "is_available": meal.can_be_ordered()
                        }
                        for meal in dish_meals
                    ]
                }
                featured_dishes.append(dish_info)

            chef_info = {
                "chef_id": chef.id,
                "name": chef.user.username,
                "experience": chef.experience,
                "bio": chef.bio,
                "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
                "featured_dishes": featured_dishes,
                'service_postal_codes': list(postal_codes_served),
                'serves_user_area': serves_user_area,
            }


            auth_chef_result.append(chef_info)

        # # Fetch a suggested meal plan based on the query
        # suggested_meal_plan = auth_get_meal_plan(request, query, 'chef')

        if not auth_chef_result:
            return {
                "message": "No chefs found that match your search.",
                "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                # "suggested_meal_plan": suggested_meal_plan
            }
        return {
            "auth_chef_result": auth_chef_result,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            # "suggested_meal_plan": suggested_meal_plan
        }
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def guest_search_chefs(request, query, **kwargs):
    print("From guest_search_chefs")
    try:
        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        # Retrieve chefs based on cosine similarity with the query embedding
        similar_chefs = Chef.objects.annotate(
            similarity=CosineDistance(F('chef_embedding'), query_vector)
        ).filter(similarity__lt=0.1).distinct()  # Adjust threshold based on your needs

        guest_chef_result = []
        for chef in similar_chefs:
            featured_dishes = []
            for dish in chef.featured_dishes.all():
                dish_meals = Meal.objects.filter(dishes__id=dish.id)
                dish_info = {
                    "id": dish.id,
                    "name": dish.name,
                    "meals": [
                        {
                            "meal_id": meal.id,
                            "meal_name": meal.name,
                            "start_date": meal.start_date.strftime('%Y-%m-%d'),
                            "is_available": meal.can_be_ordered()
                        } for meal in dish_meals
                    ]
                }
                featured_dishes.append(dish_info)

            chef_info = {
                "chef_id": chef.id,
                "name": chef.user.username,
                "experience": chef.experience,
                "bio": chef.bio,
                "profile_pic": str(chef.profile_pic.url) if chef.profile_pic else None,
                "featured_dishes": featured_dishes
            }

            # Retrieve service areas for each chef
            postal_codes_served = chef.serving_postalcodes.values_list('code', flat=True)
            chef_info['service_postal_codes'] = list(postal_codes_served)

            guest_chef_result.append(chef_info)

        if not guest_chef_result:
            return {
                "message": "No chefs found matching the query.",
                "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            }

        return {
            "guest_chef_result": guest_chef_result,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def auth_search_dishes(request, query, **kwargs):
    print("From auth_search_dishes")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        
        # Query meals based on postal code and dietary preferences
        week_shift = max(int(user.week_shift), 0)
        current_date = timezone.now().date() + timedelta(weeks=week_shift)
        dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date__gte=current_date)
        postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date__gte=current_date)
        base_meals = dietary_filtered_meals & postal_filtered_meals
        
        # Retrieve dishes based on cosine similarity with the query embedding
        similar_dishes = Dish.objects.annotate(
            similarity=CosineDistance(F('dish_embedding'), query_vector)
        ).filter(meal__in=base_meals, similarity__lt=0.1).distinct()  # Adjust the threshold based on your needs

        auth_dish_result = []
        for dish in similar_dishes:
            meals_with_dish = set(dish.meal_set.filter(start_date__gte=current_date))
            for meal in meals_with_dish:
                meal_detail = {
                    'meal_id': meal.id,
                    'name': meal.name,
                    'start_date': meal.start_date.strftime('%Y-%m-%d'),
                    'is_available': meal.can_be_ordered(),
                    'image_url': meal.image.url if meal.image else None,
                    'chefs': [{'id': dish.chef.id, 'name': dish.chef.user.username}],
                    'dishes': [{'id': dish.id, 'name': dish.name, 'similarity': dish.similarity}],
                }
                auth_dish_result.append(meal_detail)

        if not auth_dish_result:
            return {"message": "No dishes found that match your search.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        return {"auth_dish_result": auth_dish_result, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def guest_search_dishes(request, query, **kwargs):
    print("From guest_search_dishes")
    try:
        # Check if the query is valid
        if not query or not isinstance(query, str):
            return {'status': 'error', 'message': 'Invalid search query.'}

        try:
            # Generate the embedding for the search query
            query_vector = get_embedding(query)
        except Exception as e:
            return {'status': 'error', 'message': f'Error generating embedding: {str(e)}'}

        
        # Retrieve dishes based on cosine similarity with the query embedding
        current_date = timezone.now().date()
        similar_dishes = Dish.objects.annotate(
            similarity=CosineDistance(F('dish_embedding'), query_vector)
        ).filter(similarity__lt=0.1).distinct()  # Adjust threshold based on your needs

        meal_details = defaultdict(lambda: {'name': '', 'chefs': [], 'dishes': []})
        for dish in similar_dishes:
            meals_with_dish = Meal.objects.filter(dishes=dish, start_date__gte=current_date)
            for meal in meals_with_dish:
                meal_details[meal.id].update({
                    "name": meal.name,
                    "start_date": meal.start_date.strftime('%Y-%m-%d'),
                    "is_available": meal.can_be_ordered(),
                    "chefs": [{"id": dish.chef.id, "name": dish.chef.user.username}],
                    "dishes": [{"id": dish.id, "name": dish.name, 'similarity': dish.similarity}]
                })

        guest_dish_result = [{"meal_id": k, **v} for k, v in meal_details.items()]

        if not guest_dish_result:
            return {"message": "No dishes found matching the query.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        return {"guest_dish_result": guest_dish_result, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def get_or_create_meal_plan(user, start_of_week, end_of_week, **kwargs):
    print(f'From get_or_create_meal_plan: {user}, {start_of_week}, {end_of_week}')
    try:
        meal_plan, created = MealPlan.objects.get_or_create(
            user=user,
            week_start_date=start_of_week,
            week_end_date=end_of_week,
            defaults={'created_date': timezone.now()}
        )
        return meal_plan
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None

def cleanup_past_meals(meal_plan, current_date, **kwargs):
    try:
        if meal_plan.week_start_date <= current_date <= meal_plan.week_end_date:
            MealPlanMeal.objects.filter(
                meal_plan=meal_plan, 
                day__lt=current_date,
                meal__start_date__lte=current_date  # Only include meals that cannot be ordered
            ).delete()
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

def auth_get_meal_plan(request, **kwargs):
    print("From auth_get_meal_plan")
    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)

        if user_role.current_role == 'chef':
            return {'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'}

        today = timezone.now().date()
        week_shift = max(int(user.week_shift), 0)
        start_of_week = today + timedelta(days=-today.weekday(), weeks=week_shift)
        end_of_week = start_of_week + timedelta(days=6)

        meal_plan = get_or_create_meal_plan(user, start_of_week, end_of_week)

        if week_shift == 0:
            cleanup_past_meals(meal_plan, today)

        meal_plan_details = [{
            'meal_plan_id': meal_plan.id,
            'week_start_date': meal_plan.week_start_date.strftime('%Y-%m-%d'),
            'week_end_date': meal_plan.week_end_date.strftime('%Y-%m-%d')
        }]

        for meal_plan_meal in MealPlanMeal.objects.filter(meal_plan=meal_plan):
            meal = meal_plan_meal.meal
            chef_username = 'User Created Meal' if meal.creator else (meal.chef.user.username if meal.chef else 'No creator')
            start_date_display = 'User created - No specific date' if meal.creator else (meal.start_date.strftime('%Y-%m-%d') if meal.start_date else 'N/A')
            is_available = 'This meal is user created' if meal.creator else ('Orderable' if meal.can_be_ordered() else 'Not orderable')

            meal_details = {
                "meal_id": meal.id,
                "name": meal.name,
                "chef": chef_username,  # Now indicates 'User Created Meal' if there's a creator
                "start_date": start_date_display,  # Adjusted for user-created meals without a specific date
                "availability": is_available,  # Now includes a specific message for user-created meals
                "dishes": [{"id": dish.id, "name": dish.name} for dish in meal.dishes.all()],
                "day": meal_plan_meal.day,
                "meal_type": meal_plan_meal.meal_type,
                "meal_plan_id": meal_plan.id,
            }
            meal_plan_details.append(meal_details)

        return {
            "auth_meal_plan": meal_plan_details,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def guest_get_meal_plan(request, **kwargs):
    print("From guest_get_meal_plan")
    try:
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # Start of the week is always Monday
        end_of_week = start_of_week + timedelta(days=6)

        # Define meal types
        meal_types = ['Breakfast', 'Lunch', 'Dinner']

        # Store guest meal plan details
        guest_meal_plan = []
        used_meals = set()

        # Fetch and limit meals for each type, randomizing the selection
        for meal_type in meal_types:
            # Get up to 33 meals of the current type, randomizing using `.order_by('?')`
            possible_meals = Meal.objects.filter(meal_type=meal_type, start_date__gte=today, start_date__lte=end_of_week).order_by('?')[:33]

            if not possible_meals.exists():
                # If no meals available for the specific type, provide a fallback
                fallback_meals = Meal.objects.filter(meal_type=meal_type).order_by('?')[:33]
                possible_meals = fallback_meals

            # Select a subset of meals for the week, ensuring no duplicates across meal types
            for chosen_meal in possible_meals:
                if chosen_meal.id not in used_meals:
                    used_meals.add(chosen_meal.id)

                    chef_username = chosen_meal.chef.user.username if chosen_meal.chef else 'User Created Meal'
                    meal_type = chosen_meal.mealplanmeal_set.first().meal_type if chosen_meal.mealplanmeal_set.exists() else meal_type
                    is_available_msg = "Available for exploration - orderable by registered users." if chosen_meal.can_be_ordered() else "Sample meal only."

                    # Construct meal details
                    meal_details = {
                        "meal_id": chosen_meal.id,
                        "name": chosen_meal.name,
                        "start_date": chosen_meal.start_date.strftime('%Y-%m-%d') if chosen_meal.start_date else "N/A",
                        "is_available": is_available_msg,
                        "dishes": [{"id": dish.id, "name": dish.name} for dish in chosen_meal.dishes.all()],
                        "meal_type": meal_type
                    }
                    guest_meal_plan.append(meal_details)

        return {
            "guest_meal_plan": guest_meal_plan,
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def approve_meal_plan(request, meal_plan_id, **kwargs):
    print("From approve_meal_plan")
    logger.info(f"Approving meal plan with ID: {meal_plan_id}")
    logger.info(f"Approving meal plan with ID: {meal_plan_id}")
    try:
        logger.info(f"Request data: {request.data}")
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        logger.info(f"User found: {user.username} (ID: {user.id})")

        user_role = UserRole.objects.get(user=user)
        logger.info(f"User role: {user_role.current_role}")
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        # Step 1: Retrieve the MealPlan using the provided ID
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
        
        # Check if the meal plan is already associated with an order
        if meal_plan.order:
            if meal_plan.order.is_paid:
                # If the order is paid, return a message
                return {'status': 'info', 'message': 'This meal plan has already been paid for.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
            else:
                # If the order is not paid, return a message
                return {'status': 'info', 'message': 'This meal plan has an unpaid order. Please complete the payment.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        # Handle meal plan approval
        paid_meals_exist = False
        for meal_plan_meal in meal_plan.mealplanmeal_set.all():
            meal = meal_plan_meal.meal
            logger.info(f"Checking meal: {meal.name} (Price: {meal.price})")
            if meal.price and meal.price > 0:
                paid_meals_exist = True
                logger.info(f"Paid meal found: {meal.name}")
                break
        
        if not paid_meals_exist:
            logger.info("No paid meals found. Approving meal plan without payment.")
            meal_plan.is_approved = True
            meal_plan.has_changes = False
            meal_plan.save()
            return {'status': 'success', 'message': 'Meal plan approved with no payment required.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        logger.info("Creating a new order for the meal plan.")
        order = Order(customer=user)
        order.save()  # Save the order to generate an ID

       # Create OrderMeal objects for each meal in the meal plan
        for meal_plan_meal in meal_plan.mealplanmeal_set.all():
            meal = meal_plan_meal.meal
            if not meal.can_be_ordered():
                logger.info(f"Skipping meal: {meal.name} (Cannot be ordered)")
                continue  # Skip this meal if it can't be ordered
            if meal.price and meal.price > 0:
                logger.info(f"Adding meal to order: {meal.name}")
                OrderMeal.objects.create(order=order, meal=meal, meal_plan_meal=meal_plan_meal, quantity=1)

        # Link the Order to the MealPlan
        meal_plan.order = order
        meal_plan.is_approved = True
        meal_plan.has_changes = False
        meal_plan.save()


        return {
            'status': 'success', 
            'message': 'Meal plan approved. Proceed to payment.',
            'order_id': order.id, 
            'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except CustomUser.DoesNotExist as e:
        logger.error(f"User not found: {str(e)}")
        return {'status': 'error', 'message': 'User not found.'}
    except MealPlan.DoesNotExist as e:
        logger.error(f"Meal plan not found: {str(e)}")
        return {'status': 'error', 'message': 'Meal plan not found.'}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}", exc_info=True)
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def analyze_nutritional_content(request, dish_id, **kwargs):
    try:
        try:
            dish_id = int(dish_id)
        except ValueError:
            return {'status': 'error', 'message': 'Invalid dish_id'}

        # Retrieving the dish by id
        try:
            dish = Dish.objects.get(pk=dish_id)
        except Dish.DoesNotExist:
            return {'status': 'error', 'message': 'Dish not found'}

        # Preparing the response
        nutritional_content = {
            'calories': dish.calories if dish.calories else 0,
            'fat': dish.fat if dish.fat else 0,
            'carbohydrates': dish.carbohydrates if dish.carbohydrates else 0,
            'protein': dish.protein if dish.protein else 0,
        }

        return {
            'status': 'success',
            'dish_id': dish_id,
            'nutritional_content': nutritional_content
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def get_date(request):
    try:
        current_time = timezone.now()
        
        # User-friendly formatting
        friendly_date_time = date_format(current_time, "DATETIME_FORMAT")
        day_of_week = date_format(current_time, "l")  # Day name
        
        # Additional date information (optional)
        start_of_week = current_time - timezone.timedelta(days=current_time.weekday())
        end_of_week = start_of_week + timezone.timedelta(days=6)

        return {
            'current_time': friendly_date_time,
            'day_of_week': day_of_week,
            'week_start': start_of_week.strftime('%Y-%m-%d'),
            'week_end': end_of_week.strftime('%Y-%m-%d'),
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return {'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}

def sanitize_query(query):
    # Remove delimiters from the user input before executing the query
    return query.replace("####", "")