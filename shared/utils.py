import json
from django.shortcuts import render, redirect
from qa_app.models import FoodQA
from meals.models import Dish, MealType, Meal, MealPlan, MealPlanMeal
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
from meals.views import meal_plan_approval

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



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
        return JsonResponse({"error": "No meals found matching the query."}, status=404)

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
        }
    return {
        "result": meal_details,
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
        }
    return {
        "result": result,
    }

def guest_search_ingredients(query, meal_ids=None):
    print("From guest_search_ingredients")
    # Determine the current date and the end of the week
    week_shift = max(int(request.user.week_shift), 0) # Ensure week_shift is not negative
    current_date = timezone.now().date() + timedelta(weeks=week_shift)
    
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
        meal_info = [{"id": meal.id, "name": meal.name} for meal in meals_for_dish]  # Convert it to a list of dictionaries with id and name
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
        }
    return {
        "result": result,
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
            # "suggested_meal_plan": suggested_meal_plan
        }
    return {
        "auth_chef_result": auth_chef_result,
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
        "suggested_meal_plan": suggested_meal_plan
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
        }
    return {
        "auth_dish_result": auth_dish_result,
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
            "suggested_meal_plan": suggested_meal_plan
        }
    return {
        "guest_dish_result": guest_dish_result,
        "suggested_meal_plan": suggested_meal_plan
    }



def auth_get_meal_plan(request):
    print("From auth_get_meal_plan")
    # Calculate the current week's date range
    week_shift = max(int(request.user.week_shift), 0)  # Ensure week_shift is not negative
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    print(f"Start of week: {start_of_week}")
    print(f"End of week: {end_of_week}")
    # Convert DAYS_OF_WEEK to a list of day names
    days_of_week_list = [day[0] for day in MealPlanMeal.DAYS_OF_WEEK]
    
    # Calculate the index of the current day
    current_day_index = days_of_week_list.index(adjusted_today.strftime('%A'))

    # Fetch or create a MealPlan for the specified week
    meal_plan, created = MealPlan.objects.get_or_create(
        user=request.user,
        week_start_date=start_of_week,
        week_end_date=end_of_week,
        defaults={'created_date': timezone.now()}
    )
    

    # Query meals based on postal code
    postal_query = Meal.postal_objects.for_user(user=request.user).filter(start_date__lte=end_of_week, start_date__gte=adjusted_today)
    print(f"Postal query: {postal_query}")
    # Apply dietary preference filter
    base_meals = postal_query.filter(id__in=Meal.dietary_objects.for_user(request.user))
    print(f"Base meals: {base_meals}")
    # Remove past MealPlanMeal entries for this week
    if not created:
        MealPlanMeal.objects.filter(meal_plan=meal_plan, day__lte=adjusted_today).delete()

    # Iterate over the remaining days of the week
    for i in range(current_day_index, len(days_of_week_list)):
        day_name = days_of_week_list[i]
        current_day = start_of_week + timedelta(days=i)

        # Check if a meal is already planned for this day
        if not MealPlanMeal.objects.filter(meal_plan=meal_plan, day=day_name).exists():
            # Find a meal whose start date matches the current day
            chosen_meal = base_meals.filter(start_date=current_day).first()

            # Print out the IDs of all meals in the meal plan and the chosen meal
            print("IDs of all meals in the meal plan:", MealPlanMeal.objects.filter(meal_plan=meal_plan).values_list('meal_id', flat=True))
            print("Chosen meal:", chosen_meal)

            # Create a MealPlanMeal entry if a suitable meal is found
            if chosen_meal:
                MealPlanMeal.objects.create(
                    meal_plan=meal_plan,
                    meal=chosen_meal,
                    day=day_name
                )

    # Prepare response data
    auth_meal_plan = []
    for meal_plan_meal in MealPlanMeal.objects.filter(meal_plan=meal_plan):
        print(f"MealPlanMeal: {meal_plan_meal}")
        meal = meal_plan_meal.meal
        meal_details = {
            "meal_id": meal.id,
            "name": meal.name,
            "chef": meal.chef.user.username,
            "start_date": meal.start_date.strftime('%Y-%m-%d'),
            "is_available": meal.is_available(week_shift),
            "dishes": [dish.name for dish in meal.dishes.all()],
            "day": meal_plan_meal.day,
            "meal_plan_id": meal_plan.id,
        }
        auth_meal_plan.append(meal_details)

    print(f"Auth meal plan: {auth_meal_plan}")
    return {
        "auth_meal_plan": auth_meal_plan if auth_meal_plan else [{"message": "No meals available this week."}]
    }

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
            "guest_meal_plan": []  # Empty list to indicate no meal plans
        }
    return {
        "guest_meal_plan": guest_meal_plan  # List of meal plans
    }

def approve_meal_plan(request):
    print("From approve_meal_plan")
    # You can add any additional logic here
    return meal_plan_approval(request)

def generate_review_summary(object_id, category):
    # Step 1: Fetch all the review summaries for a specific chef or meal
    content_type = ContentType.objects.get(model=category)
    model_class = content_type.model_class()
    reviews = Review.objects.filter(content_type=content_type, object_id=object_id)

    if not reviews.exists():
        return JsonResponse({"message": "No reviews found for the specified category and object ID."})

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
        return JsonResponse({"message": f"An error occurred: {str(e)}"})

    # Step 4: Store the overall summary in the database
    obj = model_class.objects.get(id=object_id)
    obj.summary = overall_summary
    obj.save()

    
    # Step 5: Return the overall summary
    return JsonResponse({"overall_summary": overall_summary})


def sanitize_query(query):
    # Remove delimiters from the user input before executing the query
    return query.replace("####", "")