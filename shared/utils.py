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
from datetime import date, timedelta
from django.db.models import Q
from reviews.models import Review
from django.contrib.contenttypes.models import ContentType
from random import sample
from collections import defaultdict
from datetime import datetime
from local_chefs.views import chef_service_areas, service_area_chefs
from customer_dashboard.models import FoodPreferences
import os
import openai
from openai import OpenAIError
from django.utils import timezone
from meals.views import meal_plan_approval

# def auth_search_ingredients(request, query):
#     print("From auth_search_ingredients")
    
#     # Fetch the user's dietary preference
#     try:
#         dietary_preference = request.user.foodpreferences.dietary_preference
#     except AttributeError:
#         dietary_preference = None

#     # Determine the current date and the end of the week
#     current_date = date.today()
#     end_of_week = current_date + timedelta(days=(6 - current_date.weekday()))  # Sunday is considered the end of the week
    
#     # Filter the mealsmeal based on the dietary preference, if available
#     meal_filter_conditions = Q(start_date__gte=current_date) & Q(end_date__lte=end_of_week)
#     if dietary_preference:
#         meal_filter_conditions &= Q(dietary_preference=dietary_preference)

#     # First, find the meals available for the current week
#     available_meals = Meal.objects.filter(meal_filter_conditions)
#     # Then, look for the dishes in those meals that contain the ingredient(s) in the query
#     dishes_with_ingredient = Dish.objects.filter(
#         ingredients__name__icontains=query,
#         meal__in=available_meals
#     ).distinct()
    
#     # Finally, list out those dishes along with their chefs
#     result = []
#     for dish in dishes_with_ingredient:
#         meals_for_dish = Meal.objects.filter(dishes=dish)
#         meal_names = [{"meal_id": meal.id, "name": meal.name} for meal in meals_for_dish]
#         result.append({
#             "dish_name": dish.name,
#             "chef": dish.chef.user.username,
#             "ingredients": [ingredient.name for ingredient in dish.ingredients.all()],
#             "meals": meal_names,
#         })

#     # Fetch a suggested meal plan based on the query
#     suggested_meal_plan = auth_get_meal_plan(result, query, 'ingredient')

#     if not result:
#         return {
#             "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
#             "suggested_meal_plan": suggested_meal_plan
#         }
#     return {
#         "result": result,
#         "suggested_meal_plan": suggested_meal_plan
#     }

# def guest_search_ingredients(query, meal_ids=None):
#     print("From guest_search_ingredients")
#     # Determine the current date and the end of the week
#     current_date = date.today()
#     end_of_week = current_date + timedelta(days=(6 - current_date.weekday()))  # Sunday is considered the end of the week
    
#     # First, find the meals available for the current week
#     available_meals = Meal.objects.filter(
#         Q(start_date__gte=current_date) & 
#         Q(end_date__lte=end_of_week)
#     )
#     if meal_ids:
#         available_meals = available_meals.filter(id__in=meal_ids)
#     # Then, look for the dishes in those meals that contain the ingredient(s) in the query
#     dishes_with_ingredient = Dish.objects.filter(
#         ingredients__name__icontains=query,
#         meal__in=available_meals
#     ).distinct()
#     # Finally, list out those dishes along with their chefs
#     result = []
#     for dish in dishes_with_ingredient:
#         meal_for_dish = Meal.objects.filter(dishes=dish)  # This should give you the meals where the dish appears
#         meal_info = [{"id": meal.id, "name": meal.name} for meal in meals_for_dish]  # Convert it to a list of dictionaries with id and name
#         result.append({
#             "dish_id": dish.id,
#             "dish_name": dish.name,
#             "chef_id": dish.chef.id,
#             "chef": dish.chef.user.username,
#             "ingredients": [ingredient.name for ingredient in dish.ingredients.all()],
#             "meals": meal_info,
#         })
    
#     # Fetch a suggested meal plan based on the query
#     suggested_meal_plan = guest_get_meal_plan(query, 'ingredient', meal_ids=meal_ids)

#     if not result:
#         return {
#             "message": "No dishes found containing the queried ingredient(s) in the available meals for this week.",
#             "suggested_meal_plan": suggested_meal_plan
#         }
#     return {
#         "result": result,
#         "suggested_meal_plan": suggested_meal_plan
#     }

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
                        "is_available": meal.is_available()
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
        chef_info['service_areas'] = list(ChefPostalCode.objects.filter(chef=chef).values_list('postal_code__code', flat=True))


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
    postal_query = Meal.postal_objects.for_user(user=request.user).filter(start_date__gte=date(2023, 11, 27))
    print(f"Postal query: {postal_query}")
    # Apply dietary preference filter
    base_meals = postal_query.filter(id__in=Meal.dietary_objects.for_user(request.user))
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
                'is_available': meal.is_available(),
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



def auth_get_meal_plan(request, query, query_type=None):
    print("From auth_get_meal_plan")
    # Calculate the current week's date range
    week_shift = max(int(request.user.week_shift), 0)  # Ensure week_shift is not negative
    # adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    adjusted_today = date(2023, 11, 27)
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
            "is_available": meal.is_available(),
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