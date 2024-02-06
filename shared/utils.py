import json
from django.shortcuts import render, redirect
from django.urls import reverse
from qa_app.models import FoodQA
from meals.models import Dish, MealType, Meal, MealPlan, MealPlanMeal, Order, OrderMeal
from local_chefs.models import ChefPostalCode, PostalCode
from django.conf import settings
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta, datetime
from django.db.models import Q
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
import base64
import os
import requests


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        "Authorization": f"Bearer {get_access_token(client_id=os.getenv('KROGER_CLIENT_ID'), client_secret=os.getenv('KROGER_CLIENT_SECRET'))}"
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
def understand_dietary_choices(request):
    dietary_choices = Meal.DIETARY_CHOICES   
    return dietary_choices

def provide_healthy_meal_suggestions(request, user_id):
    user = CustomUser.objects.get(id=user_id)

    user_info = {
        'goal_name': user.goal.goal_name,
        'goal_description': user.goal.goal_description,
        'dietary_preference': user.dietary_preference
    }

    return user_info

def is_question_relevant(question):
    """
    Determine if a question is relevant to the application's functionality, specifically considering health, nutrition, and diet.

    :param question: A string representing the user's question.
    :return: A boolean indicating whether the question is relevant.
    """
    print("From is_question_relevant")
    client = openai.OpenAI(api_key=settings.OPENAI_KEY)  # Initialize OpenAI client

    # Define application's functionalities and domains for the model to consider
    app_context = """
    The application focuses on food delivery, meal planning, health, nutrition, and diet. It allows users to:
    - Search for dishes and ingredients.
    - Get personalized meal plans based on dietary preferences and nutritional goals.
    - Find chefs and meal delivery options catering to specific dietary needs.
    - Track calorie intake and provide nutrition advice.
    - Access information on healthy meal options and ingredients.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": f"given the {app_context} and the following question: {question}, determine if the question is relevant to the application's functionalities by returning a 'True' if relevant and 'False' if not."
            },
        ],
    )

    # Interpret the model's response
    response_content = response.choices[0].message.content.strip()
    print(f'Is Question Relevant Response: {response_content}')
    if "False" in response_content:
        return False
    else:
        return True


def search_healthy_meal_options(request, search_term, location_id, limit=10, start=0):
    url = "https://api-ce.kroger.com/v1/products"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {get_access_token(client_id=os.getenv('KROGER_CLIENT_ID'), client_secret=os.getenv('KROGER_CLIENT_SECRET'))}"
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


def recommend_follow_up(request, context):
    """
    Recommend follow-up prompts based on the user's interaction context.

    :param context: A string representing the user's last few interactions or context.
    :return: A list of recommended follow-up prompts or actions.
    """
    client = OpenAI(api_key=settings.OPENAI_KEY) # Initialize OpenAI client
    if request.user.is_authenticated:
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
        print("Chatting with Guest GPT")
        functions = """
            "guest_search_dishes: Search dishes in the database",
            "guest_search_chefs: Search chefs in the database and get their info",
            "guest_get_meal_plan: Get a meal plan for the current week",
            "guest_search_ingredients: Search ingredients used in dishes and get their info"
        """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {
                "role": "user", 
                "content": f"Given the following context: {context} and functions: {functions}, what prompt should a user write next? Output only the recommended prompt in a natural sentence without using the function name and without quotations as if the user themselves would type it." 
            }
        ],
    )
    # Correct way to access the response content
    response_content = response.choices[0].message.content
    print(f'Follow-Up Response: {response_content}')
    return response_content.strip().split('\n')



def provide_nutrition_advice(request, user_id):
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

def check_allergy_alert(request, user_id):
    print("From check_allergy_alert")
    user = CustomUser.objects.get(id=user_id)
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    if user.allergies:
        return {'Allergens': [user.allergies]}
    else:
        return {'Allergens': []}

def update_health_metrics(request, user_id, weight=None, bmi=None, mood=None, energy_level=None):
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

def get_unupdated_health_metrics(request, user_id):
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


def adjust_week_shift(request, week_shift_increment):
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


def update_goal(request, goal_name, goal_description):
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


def get_goal(request):
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


def get_user_info(request):
    # Ensure the requesting user is trying to access their own information

    try:
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        user_role = UserRole.objects.get(user=user)
        
        if user_role.current_role == 'chef':
            return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


        
        address = Address.objects.get(user=user)
        user_info = {
            'user_id': user.id,
            'dietary_preference': user.dietary_preference,
            'week_shift': user.week_shift,
            'user_goal': user.goal.goal_description if user.goal else 'None',
            'postal_code': address.input_postalcode if address.input_postalcode else 'Not provided'
        }
        return {'status': 'success', 'user_info': user_info, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except CustomUser.DoesNotExist:
        return {'status': 'error', 'message': 'User not found.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Address.DoesNotExist:
        return {'status': 'error', 'message': 'Address not found for user.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def access_past_orders(request, user_id):
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
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
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


def list_upcoming_meals(request):
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
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.can_be_ordered(),
            "chef": meal.chef.user.username,
            # Add more details as needed
        } for meal in filtered_meals
    ]

    # Return a dictionary instead of JsonResponse
    return {
        "upcoming_meals": meal_details,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def create_meal_plan(request):
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
        return {'status': 'success', 'message': 'Created new meal plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {'status': 'error', 'message': 'A meal plan already exists for this week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def replace_meal_in_plan(request, meal_plan_id, old_meal_id, new_meal_id, day):
    print("From replace_meal_in_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})



    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    # Check if the meal plan is linked to a placed order and if the order is paid
    if meal_plan.order:
        if meal_plan.order.is_paid:
            return {'status': 'error', 'message': 'Cannot modify a paid meal plan.'}
        else:
            return {'status': 'error', 'message': 'Cannot modify a meal plan with an unpaid order.'}

    # Validate old meal
    try:
        old_meal = Meal.objects.get(id=old_meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Old meal not found.'}

    # Validate new meal
    try:
        new_meal = Meal.objects.get(id=new_meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'New meal not found.'}

    # Validate day
    if day not in dict(MealPlanMeal.DAYS_OF_WEEK):
        return {'status': 'error', 'message': f'Invalid day: {day}'}

    # Check if old meal is scheduled for the specified day
    meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=old_meal, day=day).first()
    if not meal_plan_meal:
        return {'status': 'error', 'message': 'Old meal not scheduled on the specified day.'}

    # Replace old meal with new meal
    meal_plan_meal.meal = new_meal
    meal_plan_meal.save()

    return {
        'status': 'success',
        'message': 'Meal replaced successfully.',
        'replaced_meal': {
            'old_meal': old_meal.name,
            'new_meal': new_meal.name,
            'day': day
        },
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def remove_meal_from_plan(request, meal_plan_id, meal_id, day):
    print("From remove_meal_from_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})



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

    # Check if the meal is scheduled for the specified day in the meal plan
    meal_plan_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, meal=meal, day=day).first()
    if not meal_plan_meal:
        return {'status': 'error', 'message': 'Meal not scheduled on the specified day.'}

    # Remove the meal from the meal plan
    meal_plan_meal.delete()
    return {'status': 'success', 'message': 'Meal removed from the plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def add_meal_to_plan(request, meal_plan_id, meal_id, day):
    print("From add_meal_to_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    try:
        meal = Meal.objects.get(id=meal_id)
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

    # Check if the meal can be ordered
    if not meal.can_be_ordered():
        return {
            'status': 'error',
            'message': f'Meal "{meal.name}" cannot be ordered as it starts tomorrow or earlier. To avoid food waste, chefs need at least 24 hours to plan and prepare the meals.'
        }

    # Check if the meal's start date falls within the meal plan's week
    if meal.start_date < meal_plan.week_start_date or meal.start_date > meal_plan.week_end_date:
        return {'status': 'error', 'message': 'Meal not available in the selected week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check if the day is within the meal plan's week
    day_of_week_number = datetime.strptime(day, '%A').weekday()
    target_date = meal_plan.week_start_date + timedelta(days=day_of_week_number)
    if target_date < meal_plan.week_start_date or target_date > meal_plan.week_end_date:
        return {'status': 'error', 'message': 'Invalid day for the meal plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    # Check if there's already a meal scheduled for that day
    existing_meal = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day).first()
    if existing_meal:
        return {
            'status': 'prompt',
            'message': 'This day already has a meal scheduled. Would you like to replace it?',
            'existing_meal': {
                'meal_id': existing_meal.meal.id,
                'name': existing_meal.meal.name,
                'chef': existing_meal.meal.chef.user.username
            }
        }

    # Create the MealPlanMeal
    MealPlanMeal.objects.create(meal_plan=meal_plan, meal=meal, day=day)
    return {'status': 'success', 'action': 'added', 'new_meal': meal.name, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def suggest_alternative_meals(request, meal_ids, days_of_week):
    """
    Suggest alternative meals based on a list of meal IDs and corresponding days of the week.
    """
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    alternative_meals = []
    week_shift = max(int(user.week_shift), 0)  # User's ability to plan for future weeks

    today = timezone.now().date() + timedelta(weeks=week_shift)  # Adjust today's date based on week_shift
    current_weekday = today.weekday()

    # Map of day names to numbers
    day_to_number = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    for meal_id, day_of_week in zip(meal_ids, days_of_week):

        # Get the day number from the map
        day_of_week_number = day_to_number.get(day_of_week)
        if day_of_week_number is None:
            continue

        days_until_target = (day_of_week_number - current_weekday + 7) % 7
        target_date = today + timedelta(days=days_until_target)

        # Filter meals by dietary preferences, postal code, and current week
        dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date=target_date).exclude(id=meal_id)
        postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date=target_date).exclude(id=meal_id)

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
                # Add more details as needed
            }
            alternative_meals.append(meal_details)

    return {"alternative_meals": alternative_meals}

def search_meal_ingredients(request, query):
    print("From search_meal_ingredients")
    # Filter meals by the query in their name
    print(f"Query: {query}")
    meals = Meal.objects.filter(name__icontains=query)

    if not meals.exists():
        return {"error": "No meals found matching the query.", 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    result = []
    for meal in meals:
        meal_ingredients = {
            "meal_id": meal.id,
            "meal_name": meal.name,
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

def auth_search_meals_excluding_ingredient(request, query):
    print("From auth_search_meals_excluding_ingredient")
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

def auth_search_ingredients(request, query):
    print("From auth_search_ingredients")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Determine the current date
    week_shift = max(int(user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    
    # Filter meals available for the current week and for the user
    meal_filter_conditions = Q(start_date__gte=current_date)

    # Filter meals by dietary preferences, postal code, and current week
    dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(meal_filter_conditions)
    postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(meal_filter_conditions)

    # Combine both filters
    available_meals = dietary_filtered_meals & postal_filtered_meals
    
    # Find dishes containing the queried ingredient
    dishes_with_ingredient = Dish.objects.filter(
        ingredients__name__icontains=query,
    ).distinct()
    
    # Initialize data structure to store meal details
    meal_details = defaultdict(lambda: {'name': '', 'chefs': [], 'dishes': []})

    # Iterate over found dishes and compile meal details
    for dish in dishes_with_ingredient:
        # Fetch meals including the current dish and are available
        meals_with_dish = available_meals.filter(dishes=dish)

        for meal in meals_with_dish:
            # Update meal details with chef and dish information
            meal_detail = meal_details[meal.id]
            meal_detail['meal_id'] = meal.id
            meal_detail['name'] = meal.name
            meal_detail['start_date'] = meal.start_date.strftime('%Y-%m-%d')
            meal_detail['is_available'] = meal.can_be_ordered()

            # Add chef details if not already present
            chef_info = {"id": dish.chef.id, "name": dish.chef.user.username}
            if chef_info not in meal_detail['chefs']:
                meal_detail['chefs'].append(chef_info)

            # Add dish details
            dish_info = {
                "id": dish.id,
                "name": dish.name,
                "ingredients": [{"id": ingredient.id, "name": ingredient.name} for ingredient in dish.ingredients.all()]
            }
            meal_detail['dishes'].append(dish_info)

    # Convert the result to a list format
    result = [{"meal_id": k, **v} for k, v in meal_details.items()]

    if not result:
        return {
            "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def guest_search_ingredients(meal_ids=None):
    print("From guest_search_ingredients")
    # Determine the current date and the end of the week
    current_date = timezone.now().date()
    
    # First, find the meals available for the current week
    available_meals = Meal.objects.filter(
        Q(start_date__gte=current_date)
    )
    if meal_ids:
        available_meals = available_meals.filter(id__in=meal_ids)
    else:
        return {"error": "No meals with those ingredients found."}
    # Then, look for the dishes in those meals that contain the ingredient(s) in the query
    dishes_with_ingredient = Dish.objects.filter(
        meal__dishes__in=available_meals
    ).distinct()
    # Finally, list out those dishes along with their chefs
    result = []
    for dish in dishes_with_ingredient:
        meal_for_dish = Meal.objects.filter(dishes=dish)  # This should give you the meals where the dish appears
        meal_info = [{"id": meal.id, "name": meal.name} for meal in meal_for_dish]  # Convert it to a list of dictionaries with id and name
        result.append({
            "dish_id": dish.id,
            "dish_name": dish.name,
            "chef_id": dish.chef.id,
            "chef": dish.chef.user.username,
            "ingredients": [ingredient.name for ingredient in dish.ingredients.all()],
            "meals": meal_info,
        })

    if not result:
        return {
            "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def auth_search_chefs(request):
    # Fetch user's dietary preference
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    try:
        dietary_preference = user.foodpreferences.dietary_preference
    except AttributeError:
        dietary_preference = None

    # Retrieve user's primary postal code from Address model
    user_addresses = Address.objects.filter(user=user.id)
    user_postal_code = user_addresses.input_postalcode if user_addresses.exists() else None

    # Base query
    base_query = Q()

    # Add dietary preference filtering if available
    if dietary_preference:
        base_query &= Q(meals__dietary_preference=dietary_preference)

    # Add postal code filtering if available
    if user_postal_code:
        base_query &= Q(serving_postalcodes__code=user_postal_code)

    # Final query
    chefs = Chef.objects.filter(base_query).distinct()

    if dietary_preference:
        meals = Meal.objects.filter(dietary_preference=dietary_preference)
        if meals.exists():
            base_query = Q(meals__in=meals)
        if user_postal_code:
            base_query &= Q(serving_postalcodes__code=user_postal_code)


    # Add postal code filtering if available
    if user_postal_code:
        base_query &= Q(serving_postalcodes__code=user_postal_code)

    print("Base Query:", base_query)
    # Final query
    chefs = Chef.objects.filter(base_query).distinct()

    auth_chef_result = []
    for chef in chefs:
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


def guest_search_chefs(request):
    print("From guest_search_chefs")

    chefs = Chef.objects.all()

    guest_chef_result = []
    for chef in chefs:
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

    return {
        "guest_chef_result": guest_chef_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }



def auth_search_dishes(request):
    print("From auth_search_dishes")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})


    # Query meals based on postal code
    week_shift = max(int(user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)

    # Filter meals by dietary preferences, postal code, and current week
    dietary_filtered_meals = Meal.dietary_objects.for_user(user).filter(start_date__gte=current_date)
    postal_filtered_meals = Meal.postal_objects.for_user(user=user).filter(start_date__gte=current_date)

    # Apply dietary preference filter
    base_meals = dietary_filtered_meals & postal_filtered_meals
    # Filter the meals based on the chef's serving postal codes and the meal's dietary preference
    # Filter the dishes based on the meals and the dish's name
    dishes = Dish.objects.filter(meal__in=base_meals).distinct()


    auth_dish_result = []
    for dish in dishes:
        meals_with_dish = set(Meal.objects.filter(dishes=dish))
        for meal in meals_with_dish:
            meal_detail = {
                'meal_id': meal.id,
                'name': meal.name,
                'start_date': meal.start_date.strftime('%Y-%m-%d'),
                'is_available': meal.can_be_ordered(),
                'image_url': meal.image.url if meal.image else None,  # Add this line
                'chefs': [{'id': dish.chef.id, 'name': dish.chef.user.username}],
                'dishes': [{'id': dish.id, 'name': dish.name}],
            }
            auth_dish_result.append(meal_detail)

    # Prepare the response
    if not auth_dish_result:
        return {
            "message": "No dishes found that match your search.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "auth_dish_result": auth_dish_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def guest_search_dishes(request):
    print("From guest_search_dishes")

    dishes = Dish.objects.all()

    meal_ids = set() 
    meal_details = defaultdict(lambda: {'name': '', 'chefs': [], 'dishes': []})

    for dish in dishes:
        meals_with_dish = Meal.objects.filter(dishes__id=dish.id)
        for meal in meals_with_dish:
            meal_ids.add(meal.id)
            meal_details[meal.id] = {
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.can_be_ordered(),
                "chefs": [{"id": dish.chef.id, "name": dish.chef.user.username}],
                "dishes": [{"id": dish.id, "name": dish.name}]
            }

    guest_dish_result = [{"meal_id": k, **v} for k, v in meal_details.items()]

    if not guest_dish_result:
        return {
            "message": "No dishes found that match your search.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "guest_dish_result": guest_dish_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def get_or_create_meal_plan(user, start_of_week, end_of_week):
    meal_plan, created = MealPlan.objects.get_or_create(
        user=user,
        week_start_date=start_of_week,
        week_end_date=end_of_week,
        defaults={'created_date': timezone.now()}
    )
    return meal_plan

def cleanup_past_meals(meal_plan, current_date):
    if meal_plan.week_start_date <= current_date <= meal_plan.week_end_date:
        MealPlanMeal.objects.filter(
            meal_plan=meal_plan, 
            day__lt=current_date,
            meal__start_date__lte=current_date  # Only include meals that cannot be ordered
        ).delete()

def auth_get_meal_plan(request):
    print("From auth_get_meal_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
    if user_role.current_role == 'chef':
        return ({'status': 'error', 'message': 'Chefs in their chef role are not allowed to use the assistant.'})



    today = timezone.now().date()
    week_shift = max(int(user.week_shift), 0)
    adjusted_today = today + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    meal_plan = get_or_create_meal_plan(user, start_of_week, end_of_week)

    if week_shift == 0:
        cleanup_past_meals(meal_plan, today)

    meal_plan_details = [{'meal_plan_id': meal_plan.id, 'week_start_date': meal_plan.week_start_date.strftime('%Y-%m-%d'), 'week_end_date': meal_plan.week_end_date.strftime('%Y-%m-%d')}]

    for meal_plan_meal in MealPlanMeal.objects.filter(meal_plan=meal_plan):
        meal = meal_plan_meal.meal
        meal_details = {
            "meal_id": meal.id,
            "name": meal.name,
            "chef": meal.chef.user.username,
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.can_be_ordered(),
            "dishes": [dish.name for dish in meal.dishes.all()],
            "day": meal_plan_meal.day,
            "meal_plan_id": meal_plan.id,
        }
        meal_plan_details.append(meal_details)

    return {"auth_meal_plan": meal_plan_details, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def guest_get_meal_plan(request):
    print("From guest_get_meal_plan")
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Convert DAYS_OF_WEEK to a list of day names
    days_of_week_list = [day[0] for day in MealPlanMeal.DAYS_OF_WEEK]

    # Base query for meals available in the current week
    base_meals = Meal.objects.filter(start_date__gt=today, start_date__lte=end_of_week)  # Only include meals that can be ordered

    # Build the meal plan for each day of the week
    guest_meal_plan = []
    used_meals = set()
    for i, day_name in enumerate(days_of_week_list):
        current_day = start_of_week + timedelta(days=i)
        
        # Skip days not within the current week
        if current_day > end_of_week:
            break

        # Find a meal that hasn't been used yet
        chosen_meal = base_meals.filter(
            start_date__lte=current_day
        ).exclude(
            id__in=used_meals
        ).first()

        # Add meal details if a suitable meal is found
        if chosen_meal:
            used_meals.add(chosen_meal.id)
            meal_details = {
                "meal_id": chosen_meal.id,
                "name": chosen_meal.name,
                "chef": chosen_meal.chef.user.username,
                "start_date": chosen_meal.start_date.strftime('%Y-%m-%d'),
                "is_available": chosen_meal.can_be_ordered(),
                "dishes": [{"id": dish.id, "name": dish.name} for dish in chosen_meal.dishes.all()],
                "day": day_name
            }
            guest_meal_plan.append(meal_details)

    # Return the result
    if not guest_meal_plan:
        return {
            "message": "No meals available this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            "guest_meal_plan": []  # Empty list to indicate no meal plans
        }
    return {
        "guest_meal_plan": guest_meal_plan,  # List of meal plans
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

def approve_meal_plan(request, meal_plan_id):
    print("From approve_meal_plan")
    user = CustomUser.objects.get(id=request.data.get('user_id'))
    user_role = UserRole.objects.get(user=user)
    
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

    # Step 2: Handle meal plan approval
    # Create an Order object
    order = Order(customer=user)
    order.save()  # Save the order to generate an ID
    
    # Step 3: Create OrderMeal objects for each meal in the meal plan
    for meal_plan_meal in meal_plan.mealplanmeal_set.all():
        meal = meal_plan_meal.meal
        if not meal.can_be_ordered():
            return {
                'status': 'error',
                'message': f'Meal "{meal.name}" cannot be ordered as it starts tomorrow or earlier. To avoid food waste, chefs need at least 24 hours to plan and prepare the meals.'
            }
        OrderMeal.objects.create(order=order, meal=meal, meal_plan_meal=meal_plan_meal, quantity=1)  # Include the MealPlanMeal

    # Step 4: Link the Order to the MealPlan
    meal_plan.order = order
    meal_plan.save()


    # Return a success message with the URL
    return {
        'status': 'success', 
        'message': 'Meal plan approved. Proceed to payment.',
        'order_id': order.id, 
        'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def get_date(request):
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


def sanitize_query(query):
    # Remove delimiters from the user input before executing the query
    return query.replace("####", "")
