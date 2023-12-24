import json
from django.shortcuts import render, redirect
from qa_app.models import FoodQA
from meals.models import Dish, MealType, Meal, MealPlan, MealPlanMeal, Order, OrderMeal
from local_chefs.models import ChefPostalCode, PostalCode
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.core.paginator import Paginator
from chefs.models import Chef
from custom_auth.models import Address
from datetime import date, timedelta, datetime
from django.db.models import Q
from reviews.models import Review
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from local_chefs.views import chef_service_areas, service_area_chefs
from customer_dashboard.models import FoodPreferences
import os
import openai
from openai import OpenAIError
from django.utils import timezone
from django.utils.formats import date_format
from meals.views import meal_plan_approval

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# TODO: Reminder: When implementing the functionality for users to edit future meal plans, ensure that all days in the week are included when a user shifts the week using their week_shift attribute. This means that even if the current day of the week is Wednesday, for example, and the user shifts to the next week, the meal plan for that week should include all days from Monday to Sunday.

def list_upcoming_meals(request):
    # Calculate the current week's start and end dates based on week_shift
    week_shift = max(int(request.user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = current_date - timedelta(days=current_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Filter meals by dietary preferences, postal code, and current week
    dietary_filtered_meals = Meal.dietary_objects.for_user(request.user).filter(start_date__range=[start_of_week, end_of_week])
    postal_filtered_meals = Meal.postal_objects.for_user(user=request.user).filter(start_date__range=[start_of_week, end_of_week])

    # Combine both filters
    filtered_meals = dietary_filtered_meals & postal_filtered_meals

    # Compile meal details
    meal_details = [
        {
            "meal_id": meal.id,
            "name": meal.name,
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.is_available(week_shift),
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

    # Calculate the week's date range which also works if user shifts week
    week_shift = max(int(request.user.week_shift), 0)  # Ensure week_shift is not negative
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    print(f"Start of week: {start_of_week}")
    print(f"End of week: {end_of_week}")

    # Check if a MealPlan already exists for the specified week
    if not MealPlan.objects.filter(user=request.user, week_start_date=start_of_week, week_end_date=end_of_week).exists():
        # Create a new MealPlan for the remaining days in the week
        meal_plan = MealPlan.objects.create(
            user=request.user,
            week_start_date=start_of_week,
            week_end_date=end_of_week,
            created_date=timezone.now()
        )
        print(f"Created new meal plan: {meal_plan}")
        return {'status': 'success', 'message': 'Created new meal plan.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    return {'status': 'error', 'message': 'A meal plan already exists for this week.', 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def replace_meal_in_plan(request, meal_plan_id, old_meal_id, new_meal_id, day):
    print("From replace_meal_in_plan")

    # Validate meal plan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

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

    # Retrieve the specified MealPlan
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)
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
    try:
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)
        print(f"Meal plan: {meal_plan}")
    except MealPlan.DoesNotExist:
        return {'status': 'error', 'message': 'Meal plan not found.'}

    try:
        meal = Meal.objects.get(id=meal_id)
        print(f"Meal: {meal}")
    except Meal.DoesNotExist:
        return {'status': 'error', 'message': 'Meal not found.'}

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
    print("From suggest_alternative_meals")
    alternative_meals = []
    week_shift = max(int(request.user.week_shift), 0)  # User's ability to plan for future weeks

    today = timezone.now().date() + timedelta(weeks=week_shift)  # Adjust today's date based on week_shift
    current_weekday = today.weekday()
    print(f"Today: {today}")

    # Map of day names to numbers
    day_to_number = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    for meal_id, day_of_week in zip(meal_ids, days_of_week):
        print(f"Meal ID: {meal_id}")
        print(f"Day of week: {day_of_week}")

        # Get the day number from the map
        day_of_week_number = day_to_number.get(day_of_week)
        if day_of_week_number is None:
            print(f"Invalid day of week: {day_of_week}")
            continue

        print(f"Day of week number: {day_of_week_number}")
        days_until_target = (day_of_week_number - current_weekday + 7) % 7
        print(f"Days until target: {days_until_target}")
        target_date = today + timedelta(days=days_until_target)
        print(f"Target date for {day_of_week}: {target_date}")

        # Fetch alternative meals for the target date, excluding the current meal ID
        available_meals = Meal.dietary_objects.for_user(request.user).filter(
            start_date=target_date
        ).exclude(id=meal_id)
        print(f"Available meals for {day_of_week}: {available_meals}")
        for meal in available_meals:
            meal_details = {
                "meal_id": meal.id,
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.is_available(week_shift),
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
    print(f"Meals: {meals}")
    for meal in meals:
        meal_ingredients = {
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
    
    # Determine the current date
    week_shift = max(int(request.user.week_shift), 0)  # Ensure week_shift is not negative
    current_date = timezone.now().date() + timedelta(weeks=week_shift)

    # Find dishes containing the excluded ingredient
    dishes_with_excluded_ingredient = Dish.objects.filter(
        ingredients__name__icontains=query
    ).distinct()

    # Filter meals available for the current week and for the user, excluding those with the unwanted ingredient
    meal_filter_conditions = Q(start_date__gte=current_date)
    available_meals = Meal.dietary_objects.for_user(request.user).filter(meal_filter_conditions)
    print(f"Available meals: {available_meals}")
    available_meals = available_meals.exclude(dishes__in=dishes_with_excluded_ingredient)

    # Compile meal details
    meal_details = []
    for meal in available_meals:
        meal_detail = {
            "meal_id": meal.id,
            "name": meal.name,
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.is_available(week_shift),
            "chefs": [{"id": chef.id, "name": chef.user.username} for chef in meal.chef.all()],
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
    
    # Determine the current date
    week_shift = max(int(request.user.week_shift), 0)
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    
    # Filter meals available for the current week and for the user
    meal_filter_conditions = Q(start_date__gte=current_date)
    available_meals = Meal.dietary_objects.for_user(request.user).filter(meal_filter_conditions)
    
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
            meal_detail['name'] = meal.name
            meal_detail['start_date'] = meal.start_date.strftime('%Y-%m-%d')
            meal_detail['is_available'] = meal.is_available(week_shift)

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

def guest_search_ingredients(query, meal_ids=None):
    print("From guest_search_ingredients")
    # Determine the current date and the end of the week
    current_date = timezone.now().date()
    
    # First, find the meals available for the current week
    available_meals = Meal.objects.filter(
        Q(start_date__gte=current_date)
    )
    if meal_ids:
        available_meals = available_meals.filter(id__in=meal_ids)
    # Then, look for the dishes in those meals that contain the ingredient(s) in the query
    dishes_with_ingredient = Dish.objects.filter(
        ingredients__name__icontains=query,
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
    
    # Fetch a suggested meal plan based on the query
    suggested_meal_plan = guest_get_meal_plan(query, 'ingredient', meal_ids=meal_ids)

    if not result:
        return {
            "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
            "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    return {
        "result": result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def auth_search_chefs(request, query):
    # Fetch user's dietary preference
    print("From auth_search_chefs")
    try:
        dietary_preference = request.user.foodpreferences.dietary_preference
    except AttributeError:
        dietary_preference = None

    # Normalize the query by removing common titles and trimming whitespace
    normalized_query = query.lower().replace('chef', '').strip()
    print("Normalized Query:", normalized_query)

    # Retrieve user's primary postal code from Address model
    user_addresses = Address.objects.filter(user=request.user)
    user_postal_code = user_addresses.first().postalcode.code if user_addresses.exists() else None

    # Query for chefs whose names contain the normalized query
    chefs = Chef.objects.filter(user__username__icontains=normalized_query).distinct()



    if dietary_preference:
        meals = Meal.objects.filter(dietary_preference=dietary_preference)
        if meals.exists():
            base_query = Q(user__username__icontains=normalized_query, meals__in=meals)
        else:
            base_query = Q(user__username__icontains=normalized_query)
    else:
        base_query = Q(user__username__icontains=normalized_query)


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
                        "is_available": meal.is_available(request.user.week_shift)
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


def guest_search_chefs(query):
    print("From guest_search_chefs")
    normalized_query = query.lower().replace('chef', '').strip()

    chefs = Chef.objects.filter(user__username__icontains=normalized_query)

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
                        "is_available": meal.is_available()
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

    suggested_meal_plan = guest_get_meal_plan(query, 'chef')

    return {
        "guest_chef_result": guest_chef_result,
        "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }



def auth_search_dishes(request, query):
    print("From auth_search_dishes")
    # Query meals based on postal code
    week_shift = max(int(request.user.week_shift), 0)  # Ensure week_shift is not negative
    postal_query = Meal.postal_objects.for_user(user=request.user).filter(start_date__gte=timezone.now().date() + timedelta(weeks=week_shift))
    print(f"Postal query: {postal_query}")
    # Apply dietary preference filter
    base_meals = postal_query.filter(id__in=Meal.dietary_objects.for_user(request.user))
    print(f"Base meals: {base_meals}")
    # Filter the meals based on the chef's serving postal codes and the meal's dietary preference
    # Filter the dishes based on the meals and the dish's name
    dishes = Dish.objects.filter(meal__in=base_meals, name__icontains=query).distinct()

    print(f'Dishes: {dishes}')

    auth_dish_result = []
    for dish in dishes:
        print(f"Processing dish: {dish}")
        meals_with_dish = set(Meal.objects.filter(dishes=dish))
        print(f"meals_with_dish: {meals_with_dish}")
        for meal in meals_with_dish:
            meal_detail = {
                'meal_id': meal.id,
                'name': meal.name,
                'start_date': meal.start_date.strftime('%Y-%m-%d'),
                'is_available': meal.is_available(week_shift),
                'image_url': meal.image.url if meal.image else None,  # Add this line
                'chefs': [{'id': dish.chef.id, 'name': dish.chef.user.username}],
                'dishes': [{'id': dish.id, 'name': dish.name}],
            }
            auth_dish_result.append(meal_detail)
    print(f"auth_dish_result: {auth_dish_result}")

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

def guest_search_dishes(query):
    print("From guest_search_dishes")

    dishes = Dish.objects.filter(name__icontains=query)
    print(f'Query: {query}')

    meal_ids = set() 
    meal_details = defaultdict(lambda: {'name': '', 'chefs': [], 'dishes': []})

    for dish in dishes:
        meals_with_dish = Meal.objects.filter(dishes__id=dish.id)
        for meal in meals_with_dish:
            meal_ids.add(meal.id)
            meal_details[meal.id] = {
                "name": meal.name,
                "start_date": meal.start_date.strftime('%Y-%m-%d'),
                "is_available": meal.is_available(),
                "chefs": [{"id": dish.chef.id, "name": dish.chef.user.username}],
                "dishes": [{"id": dish.id, "name": dish.name}]
            }

    guest_dish_result = [{"meal_id": k, **v} for k, v in meal_details.items()]

    suggested_meal_plan = guest_get_meal_plan(query, 'dish')

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
        MealPlanMeal.objects.filter(meal_plan=meal_plan, day__lt=current_date).delete()


def auth_get_meal_plan(request):
    print("From auth_get_meal_plan")

    today = timezone.now().date()
    week_shift = max(int(request.user.week_shift), 0)
    adjusted_today = today + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    meal_plan = get_or_create_meal_plan(request.user, start_of_week, end_of_week)

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
            "is_available": meal.is_available(),
            "dishes": [dish.name for dish in meal.dishes.all()],
            "day": meal_plan_meal.day,
            "meal_plan_id": meal_plan.id,
        }
        meal_plan_details.append(meal_details)

    return {"auth_meal_plan": meal_plan_details, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

def guest_get_meal_plan(query, query_type=None, include_dish_id=False):
    print("From guest_get_meal_plan")
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Convert DAYS_OF_WEEK to a list of day names
    days_of_week_list = [day[0] for day in MealPlanMeal.DAYS_OF_WEEK]

    # Base query for meals available in the current week
    base_meals = Meal.objects.filter(start_date__lte=end_of_week)

    # Additional filter based on query type
    query_filter = Q()
    if query_type == 'chef':
        query_filter |= Q(chef__user__username__icontains=query)
    elif query_type == 'dish':
        query_filter |= Q(dishes__name__icontains=query)

    if query_type:
        base_meals = base_meals.filter(query_filter)

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
                "is_available": chosen_meal.is_available(),
                "dishes": [{"id": dish.id, "name": dish.name} for dish in chosen_meal.dishes.all()] if include_dish_id else [dish.name for dish in chosen_meal.dishes.all()],
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
    
    # Step 1: Retrieve the MealPlan using the provided ID
    meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)
    
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
    order = Order(customer=request.user)
    order.save()  # Save the order to generate an ID
    
    # Step 3: Create OrderMeal objects for each meal in the meal plan
    for meal in meal_plan.meal.all():
        OrderMeal.objects.create(order=order, meal=meal, quantity=1)

    # Step 4: Link the Order to the MealPlan
    meal_plan.order = order
    meal_plan.save()

    # Step 5: Return a success message
    return {'status': 'success', 'message': 'Meal plan approved. Proceed to payment.', 'order_id': order.id, 'current_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

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


def generate_review_summary(object_id, category):
    # Step 1: Fetch all the review summaries for a specific chef or meal
    content_type = ContentType.objects.get(model=category)
    model_class = content_type.model_class()
    reviews = Review.objects.filter(content_type=content_type, object_id=object_id)

    if not reviews.exists():
        return {"message": "No reviews found for the specified category and object ID.", "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

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
    obj.summary = overall_summary
    obj.save()

    
    # Step 5: Return the overall summary
    return {"overall_summary": overall_summary, "current_time": timezone.now().strftime('%Y-%m-%d %H:%M:%S')}


def sanitize_query(query):
    # Remove delimiters from the user input before executing the query
    return query.replace("####", "")