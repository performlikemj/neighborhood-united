import logging
import os
import traceback
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import date, datetime, timedelta
from .forms import DishForm, IngredientForm, MealForm
from .models import (
    Meal, Cart, Dish, Ingredient, Order, OrderMeal, MealPlan, MealPlanMeal, Instruction, PantryItem, 
    ChefMealEvent, ChefMealOrder, ChefMealReview, PostalCode, ChefPostalCode, StripeConnectAccount, 
    PlatformFeeConfig, PaymentLog
)
from django.http import JsonResponse, HttpResponseBadRequest
from .serializers import (
    MealPlanSerializer, MealSerializer, PantryItemSerializer, UserSerializer, ChefMealEventSerializer, 
    ChefMealEventCreateSerializer, ChefMealOrderSerializer, ChefMealOrderCreateSerializer, 
    ChefMealReviewSerializer, StripeConnectAccountSerializer
)
from chefs.models import Chef
from shared.utils import day_to_offset
from django.conf import settings
import requests
from django.http import JsonResponse
from rest_framework.response import Response
from django.urls import reverse
from django.http import HttpResponseBadRequest
from custom_auth.models import Address, CustomUser
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseForbidden
from custom_auth.models import UserRole
import json
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q, F, Sum, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
import stripe
import json
import decimal
from openai import OpenAI
from gptcache import cache
from django.db import transaction
import uuid


logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_KEY)

stripe.api_key = settings.STRIPE_SECRET_KEY

def is_chef(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'chef'
        except UserRole.DoesNotExist:
            return False
    return False

def is_customer(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'customer'
        except UserRole.DoesNotExist:
            return False
    return False

def api_search_ingredients(request):
    query = request.GET.get('query', '')
    results = search_ingredients(query)
    return JsonResponse(results)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_meal_plan_preference(request):
    if request.method == 'GET':
        # Retrieve the meal plans for the current user
        meal_plans = MealPlan.objects.filter(user=request.user)
        serializer = MealPlanSerializer(meal_plans, many=True)
        return Response(serializer.data, status=200)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_post_meal_plan_preference(request):
    if request.method == 'POST':
        data = request.data.copy()
        data['user'] = request.user.id  # Assign the current user

        serializer = MealPlanSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        else:
            return Response(serializer.errors, status=400)
        
@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated access
def api_email_approved_meal_plan(request):
    approval_token = request.data.get('approval_token')
    meal_prep_preference = request.data.get('meal_prep_preference')
    valid_preferences = dict(MealPlan.MEAL_PREP_CHOICES).keys()

    if not approval_token:
        return Response({'error': 'Approval token is required.'}, status=400)
    
    if not meal_prep_preference or meal_prep_preference not in valid_preferences:
        return Response({'error': 'Invalid meal prep preference.'}, status=400)
    try:
        meal_plan = MealPlan.objects.get(approval_token=approval_token)
        meal_plan.is_approved = True
        meal_plan.has_changes = False
        meal_plan.meal_prep_preference = meal_prep_preference
        meal_plan.save()
        return Response({'status': 'success', 'message': 'Meal plan approved successfully.'})
    except MealPlan.DoesNotExist:
        return Response({'status': 'error', 'message': 'Invalid or expired approval token.'}, status=400)
    
def search_ingredients(query, number=20, apiKey=settings.SPOONACULAR_API_KEY):
    search_url = "https://api.spoonacular.com/food/ingredients/search"
    search_params = {
        "query": query,
        "number": number,
        "apiKey": apiKey,
    }
    response = requests.get(search_url, params=search_params)
    response.raise_for_status()  # Raises an HTTPError if the response status isn't 200
    return response.json()

def embeddings_list(request):
    meals = Meal.objects.all()  # Fetch all meals, or filter as needed
    return render(request, 'meals/embeddings_list.html', {'meals': meals})

def get_ingredient_info(id, apiKey=settings.SPOONACULAR_API_KEY):
    info_url = f"https://api.spoonacular.com/food/ingredients/{id}/information"
    info_params = {
        "amount": 1,
        "apiKey": apiKey,
    }
    response = requests.get(info_url, params=info_params)
    response.raise_for_status()  # Raises an HTTPError if the response status isn't 200
    return response.json()

@user_passes_test(is_chef, login_url='custom_auth:login')
def api_create_ingredient(request):
    if request.method == 'POST':
        print(request.POST)
        chef = request.user.chef
        print(chef)
        name = request.POST.get('name')
        spoonacular_id = request.POST.get('spoonacular_id')
        if chef.ingredients.filter(spoonacular_id=spoonacular_id).exists():
            # Ingredient already exists, no need to add it again
            return JsonResponse({"message": "Ingredient already added"}, status=400)
        
        ingredient_info = get_ingredient_info(spoonacular_id)
        if 'error' in ingredient_info:
            return JsonResponse({"message": "Error fetching ingredient information"}, status=400)
        # Extract nutritional information
        calories = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Calories'), None)
        fat = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Fat'), None)
        carbohydrates = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Net Carbohydrates'), None)
        protein = next((nutrient['amount'] for nutrient in ingredient_info['nutrition']['nutrients'] if nutrient['name'] == 'Protein'), None)

        # Create Ingredient object
        ingredient = Ingredient.objects.create(
            chef=chef,
            name=name,
            spoonacular_id=spoonacular_id,
            calories=calories,
            fat=fat,
            carbohydrates=carbohydrates,
            protein=protein,
        )

        # Save the ingredient
        ingredient.save()

        return JsonResponse({
            'name': ingredient.name,
            'spoonacular_id': ingredient.spoonacular_id,
            'calories': ingredient.calories,
            'message': "Ingredient created successfully"
        })




@login_required
@require_http_methods(["GET", "POST"])  # Restrict to GET and POST methods
def api_customize_meal_plan(request, meal_plan_id):
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)

    if request.method == 'POST':
        # Handle AJAX requests for meal plan modifications
        if request.is_ajax():
            data = json.loads(request.body)
            action = data.get('action')
            meal_id = data.get('meal_id')
            day = data.get('day')

            if action == 'remove':
                MealPlanMeal.objects.filter(meal_plan=meal_plan, meal__id=meal_id, day=day).delete()
                return JsonResponse({'status': 'success', 'action': 'removed'})

            elif action == 'replace':
                new_meal_id = data.get('new_meal_id')
                new_meal = get_object_or_404(Meal, id=new_meal_id)
                MealPlanMeal.objects.filter(meal_plan=meal_plan, meal__id=meal_id, day=day).update(meal=new_meal)
                return JsonResponse({'status': 'success', 'action': 'replaced', 'new_meal': new_meal.name})

            elif action == 'add':
                new_meal_id = data.get('new_meal_id')
                new_meal = get_object_or_404(Meal, id=new_meal_id)
                offset = day_to_offset(day)
                meal_date = meal_plan.week_start_date + timedelta(days=offset)
                MealPlanMeal.objects.create(meal_plan=meal_plan, meal=new_meal, day=day, meal_date=meal_date)
                return JsonResponse({'status': 'success', 'action': 'added', 'new_meal': new_meal.name})

            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

        # Render the customization form or UI for GET requests
        else:
            return render(request, 'customize_meal_plan.html', {'meal_plan': meal_plan})

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required
@user_passes_test(is_customer, login_url='custom_auth:profile')
def get_alternative_meals(request):

    # Calculate the current week's date range
    week_shift = max(int(request.user.week_shift), 0)
    adjusted_today = timezone.now().date() + timedelta(weeks=week_shift)
    start_of_week = adjusted_today - timedelta(days=adjusted_today.weekday()) + timedelta(weeks=week_shift)
    end_of_week = start_of_week + timedelta(days=6)

    # Get current day from the request
    current_day = request.GET.get('day', adjusted_today.strftime('%A'))
    # Convert DAYS_OF_WEEK to a list of day names
    days_of_week_list = [day[0] for day in MealPlanMeal.DAYS_OF_WEEK]

    # Convert the day name to a date object
    current_day_date = start_of_week + timedelta(days=days_of_week_list.index(current_day))
    # Retrieve the meal plan for the specified week
    meal_plan = MealPlan.objects.filter(
        user=request.user,
        week_start_date=start_of_week,
        week_end_date=end_of_week
    ).first()

    if not meal_plan:
        return JsonResponse({"message": "No meal plan found for the specified week."})

    # Query MealPlanMeal for the specific day within the meal plan
    meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan, day=current_day)

    # Query meals based on postal code, and availability for the specific day
    postal_query = Meal.postal_objects.for_user(user=request.user).filter(start_date=current_day_date)
    # Apply dietary preference filter only if it's not None
    meals = postal_query.filter(id__in=Meal.dietary_objects.for_user(request.user))

    print(meals)

    # Return the meals as JSON
    if meals.exists():
        meals_data = [{
            'id': meal.id,
            'name': meal.name,
            'chef': meal.chef.user.username,
            # ... include other meal details as needed ...
        } for meal in meals]
        return JsonResponse({"success": True, "meals": meals_data})
    else:
        return JsonResponse({"success": False, "message": "No alternative meals available."})



@login_required
@user_passes_test(is_customer, login_url='custom_auth:profile')
@require_http_methods(["POST"])
def submit_meal_plan_updates(request):
    try:
        # Load the JSON data from the request
        data = json.loads(request.body)
        updated_meals = data.get('mealPlan')
        print(updated_meals)
        print(type(updated_meals))

        # Assuming each meal in updated_meals includes a 'meal_plan_id'
        if not updated_meals:
            raise ValueError("Updated meal plan is empty.")

        # Example: getting the meal_plan_id from the first meal
        meal_plan_id = updated_meals[0].get('meal_plan_id')
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)

        # Clear existing MealPlanMeal entries
        MealPlanMeal.objects.filter(meal_plan=meal_plan).delete()

        # Create new MealPlanMeal entries based on the updated meal plan
        offset = day_to_offset(day)
        meal_date = meal_plan.week_start_date + timedelta(days=offset)

        for meal in updated_meals:
            day=meal['day']
            offset = day_to_offset(day)
            meal_date = meal_plan.week_start_date + timedelta(days=offset)
            MealPlanMeal.objects.create(
                meal_plan=meal_plan,
                meal_id=meal['meal_id'],
                day=day,
                meal_date=meal_date
            )

        return JsonResponse({'status': 'success', 'message': 'Meal plan updated successfully.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def meal_plan_approval(request):
    # Step 1: Retrieve the current MealPlan for the user
    week_shift = max(int(request.user.week_shift), 0)
    today = timezone.now().date() + timedelta(weeks=week_shift)
    meal_plan = get_object_or_404(MealPlan, user=request.user, week_start_date__lte=today, week_end_date__gte=today)
    
    # Check if the meal plan is already associated with an order
    if meal_plan.order:
        if meal_plan.order.is_paid:
            # If the order is paid, redirect to the confirmation page
            messages.info(request, 'This meal plan has already been paid for.')
            return redirect('meals:meal_plan_confirmed')
        else:
            # If the order is not paid, redirect to the payment page
            messages.info(request, 'This meal plan has an unpaid order. Please complete the payment.')
            return redirect('meals:process_payment', order_id=meal_plan.order.id)

    # Step 2: Display it for approval
    if request.method == 'POST':
        # Step 3: Handle meal plan approval
        # Create an Order object
        order = Order.objects.create(
            customer=request.user,
            status='Placed',
            meal_plan=meal_plan
        )

        # Step 5: Create OrderMeal objects for each meal in the meal plan
        for meal in meal_plan.meal.all():
            OrderMeal.objects.create(order=order, meal=meal, quantity=1)

        # Step 4: Link the Order to the MealPlan
        meal_plan.order = order
        meal_plan.save()


        # Step 6: Redirect to payment
        return redirect('meals:process_payment', order_id=order.id)
    
    # Render the meal plan approval page
    return render(request, 'meals/approve_meal_plan.html', {'meal_plan': meal_plan})



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_meal_plans(request):
    try:
        user = request.user
        week_start_date_str = request.query_params.get('week_start_date')
        print(f'Week Start Date: {week_start_date_str}')
        if week_start_date_str:
            week_start_date = datetime.strptime(week_start_date_str, '%Y-%m-%d').date()
            week_end_date = week_start_date + timedelta(days=6)
            meal_plans = MealPlan.objects.filter(
                user=user,
                week_start_date__lte=week_end_date,   # starts on or before the last day
                week_end_date__gte=week_start_date    # ends on or after the first day
            )
        else:
            meal_plans = MealPlan.objects.filter(user=user)

        serializer = MealPlanSerializer(meal_plans, many=True)
        return Response(serializer.data, status=200)
    
    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_meal_plan_by_id(request, meal_plan_id):
    try:
        user = request.user
        meal_plan = MealPlan.objects.get(id=meal_plan_id, user=user)
        serializer = MealPlanSerializer(meal_plan)
        return Response(serializer.data, status=200)
    except MealPlan.DoesNotExist:
        return Response({"error": "Meal plan not found."}, status=404)
    except Exception as e:
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)
            
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_generate_cooking_instructions(request):
    try:
        from .meal_instructions import generate_instructions
        # Extract meal_plan_meal_ids from request data
        meal_plan_meal_ids = request.data.get('meal_plan_meal_ids', [])
        if not meal_plan_meal_ids:
            return Response({"error": "meal_plan_meal_ids are required"}, status=400)

        # Verify that each MealPlanMeal exists and belongs to the current user
        valid_meal_plan_meal_ids = []
        for meal_plan_meal_id in meal_plan_meal_ids:
            try:
                meal_plan_meal = MealPlanMeal.objects.get(id=meal_plan_meal_id)
                valid_meal_plan_meal_ids.append(meal_plan_meal.id)  # Append the ID, not the MealPlanMeal instance
            except MealPlanMeal.DoesNotExist:
                logger.warning(f"MealPlanMeal with ID {meal_plan_meal_id} not found or unauthorized access attempted.")
                continue

        if not valid_meal_plan_meal_ids:
            return Response({"error": "No valid meal plan meals found or you do not have permission to access them."}, status=404)

        # Call the Celery task to generate cooking instructions for each valid meal plan meal
        generate_instructions.delay(valid_meal_plan_meal_ids)

        return Response({"message": "Cooking instructions generation initiated successfully for the selected meal plan meals."}, status=200)

    except Exception as e:
        logger.error(f"An error occurred while initiating cooking instructions generation: {str(e)}")
        return Response({"error": "An unexpected error occurred. Please try again later."}, status=500)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_remove_meal_from_plan(request):
    """
    API endpoint to remove meals from a user's meal plan.
    Expects a list of MealPlanMeal IDs in the request data.
    """
    logger.info("Starting api_remove_meal_from_plan")
    user = request.user
    meal_plan_meal_ids = request.data.get('meal_plan_meal_ids', [])
    logger.info(f"Removing meals from meal plan: {meal_plan_meal_ids}") 
    logger.info(f"User: {user}")
    if not meal_plan_meal_ids:
        return Response({"error": "No meal_plan_meal_ids provided."}, status=400)

    # Ensure meal_plan_meal_ids is a list of integers
    try:
        meal_plan_meal_ids = [int(id) for id in meal_plan_meal_ids if id]
    except ValueError:
        return Response({"error": "Invalid meal_plan_meal_ids provided."}, status=400)

    # Fetch MealPlanMeal instances that belong to the user
    meal_plan_meals = MealPlanMeal.objects.filter(
        id__in=meal_plan_meal_ids,
        meal_plan__user=user
    )

    if not meal_plan_meals.exists():
        return Response({"error": "No meal plan meals found to delete."}, status=404)

    # Delete meal plan meals
    for meal_plan_meal in meal_plan_meals:
        meal_plan_meal.delete()

    return Response({"message": "Selected meals removed from the plan."}, status=200)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_fetch_instructions(request):
    from meals.models import MealPlanMeal, Instruction, MealPlan, MealPlanInstruction
    meal_plan_meal_ids = request.query_params.get('meal_plan_meal_ids', '').split(',')
    meal_plan_id = request.query_params.get('meal_plan_id', None)
    
    # Get the meal plan ID from the first meal plan meal if not provided
    if not meal_plan_id and meal_plan_meal_ids:
        print(f'Meal Plan Meal IDs: {meal_plan_meal_ids}')
        try:
            meal_plan_meal = MealPlanMeal.objects.filter(id=meal_plan_meal_ids[0]).first()
            if meal_plan_meal:
                meal_plan_id = meal_plan_meal.meal_plan.id
                print(f'Meal Plan ID: {meal_plan_id}')
            else:
                return Response({"error": "Invalid meal plan meal ID"}, status=404)
        except MealPlanMeal.DoesNotExist:
            return Response({"error": "Invalid meal plan meal ID"}, status=404)
    
    meal_plan = get_object_or_404(MealPlan, id=meal_plan_id)
    meal_prep_preference = meal_plan.meal_prep_preference
    instructions = []

    if meal_prep_preference == 'daily':
        if not meal_plan_meal_ids:
            return Response({"error": "meal_plan_meal_ids are required for daily meal prep preference"}, status=400)
        meal_plan_meal_ids = [int(id) for id in meal_plan_meal_ids if id]

        for meal_plan_meal_id in meal_plan_meal_ids:
            meal_plan_meal = get_object_or_404(MealPlanMeal, id=meal_plan_meal_id)
            instruction = Instruction.objects.filter(meal_plan_meal=meal_plan_meal).first()
            print(f'Instruction: {instruction.content if instruction else None}')
            # Calculate the date based on the meal plan's week start date and the meal's day
            meal_plan = meal_plan_meal.meal_plan
            day_of_week = meal_plan_meal.day  # e.g., 'Monday'
            week_start_date = meal_plan.week_start_date

            # Map day names to offsets from the start date
            day_offset = {
                'Monday': 0,
                'Tuesday': 1,
                'Wednesday': 2,
                'Thursday': 3,
                'Friday': 4,
                'Saturday': 5,
                'Sunday': 6,
            }
            meal_date = week_start_date + timedelta(days=day_offset[day_of_week])

            meal_name = meal_plan_meal.meal.name
            if instruction:
                instructions.append({
                    "meal_plan_meal_id": meal_plan_meal_id,
                    "instruction_type": "daily",
                    "date": meal_date.isoformat(),
                    "meal_name": meal_name,
                    "instructions": instruction.content
                })
            else:
                instructions.append({
                    "meal_plan_meal_id": meal_plan_meal_id,
                    "instruction_type": "daily",
                    "date": meal_date.isoformat(),
                    "meal_name": meal_name,
                    "instructions": None
                })

    elif meal_prep_preference == 'one_day_prep':
        # Fetch all instructions for the meal plan
        meal_plan_instructions = MealPlanInstruction.objects.filter(
            meal_plan=meal_plan
        ).order_by('date')

        for instruction in meal_plan_instructions:
            instruction_data = {
                "meal_plan_id": meal_plan.id,
                "instruction_type": "bulk_prep" if instruction.is_bulk_prep else "follow_up",
                "date": instruction.date.isoformat(),
                "instructions": instruction.instruction_text
            }
            instructions.append(instruction_data)

    else:
        return Response({"error": f"Unknown meal_prep_preference '{meal_prep_preference}'"}, status=400)

    return Response({
        "meal_prep_preference": meal_prep_preference,
        "instructions": instructions
    }, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_approve_meal_plan(request):
    """
    Endpoint to approve a meal plan with specified meal prep preference.
    Expects meal_plan_id and meal_prep_preference in request data.
    """
    meal_plan_id = request.data.get('meal_plan_id')
    meal_prep_preference = request.data.get('meal_prep_preference')
    user_id = request.data.get('user_id')
    
    if not user_id:
        return Response({"status": "error", "message": "User ID is required."}, status=400)
        
    if not meal_plan_id:
        return Response({'error': 'Meal plan ID is required.'}, status=400)
    
    valid_preferences = dict(MealPlan.MEAL_PREP_CHOICES).keys()
    if not meal_prep_preference or meal_prep_preference not in valid_preferences:
        return Response({'error': 'Invalid meal prep preference.'}, status=400)

    try:
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)
        
        # Update meal plan preferences
        meal_plan.is_approved = True
        meal_plan.has_changes = False
        meal_plan.meal_prep_preference = meal_prep_preference
        meal_plan.save()

        # Create an Order for the approved meal plan
        order = Order.objects.create(
            customer=request.user,
            status='Placed',
            meal_plan=meal_plan
        )

        # Add meals from meal plan to order with their corresponding MealPlanMeal
        for meal_plan_meal in meal_plan.mealplanmeal_set.all():
            OrderMeal.objects.create(
                order=order,
                meal=meal_plan_meal.meal,
                meal_plan_meal=meal_plan_meal,
                quantity=1
            )
        print(f'Successfully created order with ID: {order.id}')
        print(f'Order Meals: {order.ordermeal_set.all()}')
        return Response({
            'status': 'success',
            'message': 'Meal plan approved successfully.',
            'order_id': order.id
        })

    except MealPlan.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Meal plan not found.'
        }, status=404)
    except Exception as e:
        logger.error(f"Error approving meal plan: {str(e)}")
        return Response({
            'status': 'error',
            'message': 'An error occurred while approving the meal plan.'
        }, status=500)

class PantryItemPagination(PageNumberPagination):
    page_size = 10  # Adjust as needed
    page_size_query_param = 'page_size'
    max_page_size = 100

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_pantry_items(request):
    """
    GET: List all pantry items for the authenticated user with pagination.
    POST: Create a new pantry item for the authenticated user.
    """
    print(f'Request Info: {request}')
    print(f'Request User: {request.user}')
    print(f'Request Data: {request.data}')
    print(f'Request Method: {request.method}')
    
    if request.method == 'GET':
        pantry_items = PantryItem.objects.filter(user=request.user).order_by('-expiration_date')
        paginator = PantryItemPagination()
        result_page = paginator.paginate_queryset(pantry_items, request)
        serializer = PantryItemSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    elif request.method == 'POST':
        # Ensure request.data is a dictionary, not a string
        if isinstance(request.data, str):
            try:
                data = json.loads(request.data)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format."}, status=400)
        else:
            data = request.data

        serializer = PantryItemSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user) 
            return Response(serializer.data, status=201)
        else:
            print(f"Serializer Errors: {serializer.errors}")  # Log the errors
            return Response(serializer.errors, status=400)
    
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def api_pantry_item_detail(request, pk):
    """
    Handles GET, PUT/PATCH, DELETE methods for a single pantry item.
    """
    pantry_item = get_object_or_404(PantryItem, pk=pk, user=request.user)

    if request.method == 'GET':
        serializer = PantryItemSerializer(pantry_item)
        return Response(serializer.data, status=200)

    elif request.method in ['PUT', 'PATCH']:
        # If request.data is a string (which it shouldn't be in a correctly configured API request)
        if isinstance(request.data, str):
            try:
                # Convert the string to a dictionary
                data = json.loads(request.data)
            except json.JSONDecodeError:
                return Response({"error": "Invalid JSON format."}, status=400)
        else:
            # Otherwise, use request.data as is
            data = request.data


        # Set partial=True for PATCH and False for PUT
        partial = request.method == 'PATCH'
        serializer = PantryItemSerializer(pantry_item, data=data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        else:
            print(f"Serializer Errors: {serializer.errors}")
            return Response(serializer.errors, status=400)

    elif request.method == 'DELETE':
        pantry_item.delete()
        return Response(status=204)


# Emergency pantry item API
@api_view(['POST'])
def api_generate_emergency_plan(request):
    approval_token = request.data.get('approval_token')

    if not approval_token:
        return Response({"error": "Approval token is required."}, status=400)

    try:
        # Retrieve the MealPlan or user associated with that token
        # or store the token on the user object—whatever logic fits your design.
        # For example, maybe you store the token on the `User` or `MealPlan`:

        meal_plan = MealPlan.objects.get(approval_token=approval_token)
        user = meal_plan.user  # The associated user
    except MealPlan.DoesNotExist:
        return Response({"error": "Invalid or expired approval token."}, status=400)

    # Great, we found a valid user from the token. Now let's generate the plan:
    from meals.email_service import generate_emergency_supply_list

    try:
        generate_emergency_supply_list(user.id)
        return Response({"message": "Emergency supply list generated successfully."}, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_update_meals_with_prompt(request):
    """
    API endpoint to update meals in a meal plan based on a text prompt.
    Requires meal_plan_meal_ids and their corresponding dates to ensure correct meal updates.
    """
    logger.info("Starting api_update_meals_with_prompt")
    from meals.meal_generation import generate_and_create_meal
    try:
        meal_plan_meal_ids = request.data.get('meal_plan_meal_ids', [])
        meal_dates = request.data.get('meal_dates', [])
        prompt = request.data.get('prompt', '').strip()
        logger.info(f"Received meal_plan_meal_ids: {meal_plan_meal_ids}, dates: {meal_dates}, prompt: {prompt}")

        if not meal_plan_meal_ids or not meal_dates:
            logger.warning("Missing required data: meal_plan_meal_ids or meal_dates")
            return Response({
                "error": "Both meal_plan_meal_ids and meal_dates are required."
            }, status=400)

        if len(meal_plan_meal_ids) != len(meal_dates):
            logger.warning("Mismatched lengths: meal_plan_meal_ids and meal_dates")
            return Response({
                "error": "Number of meal IDs must match number of dates."
            }, status=400)

        # Get current date for comparisons
        today = timezone.now().date()
        logger.info(f"Current date: {today}")

        # Convert string dates to date objects and create ID-to-date mapping
        try:
            id_date_pairs = []
            for meal_id, date_str in zip(meal_plan_meal_ids, meal_dates):
                meal_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                # Check if date is in the past
                if meal_date < today:
                    logger.info(f"Skipping past date: {date_str} for meal_id: {meal_id}")
                    continue  # Skip past dates
                id_date_pairs.append((meal_id, meal_date))
                logger.info(f"Added valid date pair: meal_id={meal_id}, date={date_str}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            return Response({
                "error": "Invalid date format. Use YYYY-MM-DD."
            }, status=400)

        if not id_date_pairs:
            logger.warning("No valid future dates found in request")
            return Response({
                "error": "No valid future dates provided for meal updates."
            }, status=400)

        updates = []
        logger.info("Starting meal updates process")
        total_meals = len(id_date_pairs)
        processed_meals = 0

        # Process each meal plan meal directly from ID-date pairs
        for meal_plan_meal_id, meal_date in id_date_pairs:
            try:
                meal_plan_meal = MealPlanMeal.objects.select_related('meal_plan', 'meal').get(
                    id=meal_plan_meal_id,
                    meal_plan__user=request.user
                )
                logger.info(f"Processing meal: ID={meal_plan_meal.id}, Name={meal_plan_meal.meal.name}, Date={meal_date}")

                # Add day verification
                expected_day = meal_date.strftime("%A")
                if meal_plan_meal.day != expected_day:
                    error_message = (
                        f"Day mismatch for MealPlanMeal ID {meal_plan_meal.id}: "
                        f"expected day '{expected_day}' (from provided date {meal_date}), "
                        f"but found day '{meal_plan_meal.day}' with meal type '{meal_plan_meal.meal_type}'."
                    )
                    logger.error(error_message)
                    return Response({
                        "error": error_message,
                        "meal_plan_meal": {
                            "id": meal_plan_meal.id,
                            "name": meal_plan_meal.meal.name,
                            "day": meal_plan_meal.day,
                            "meal_type": meal_plan_meal.meal_type,
                            "provided_date": meal_date.strftime("%Y-%m-%d")
                        }
                    }, status=400)

            except MealPlanMeal.DoesNotExist:
                error_message = f"Meal plan meal with ID {meal_plan_meal_id} not found or unauthorized"
                logger.warning(error_message)
                return Response({
                    "error": error_message,
                    "details": {
                        "meal_plan_meal_id": meal_plan_meal_id,
                        "provided_date": meal_date.strftime("%Y-%m-%d")
                    }
                }, status=404)

        # Get the meal plan from the first valid meal
        meal_plan = None
        for meal_plan_meal_id, _ in id_date_pairs:
            try:
                meal_plan_meal = MealPlanMeal.objects.select_related('meal_plan').get(
                    id=meal_plan_meal_id,
                    meal_plan__user=request.user
                )
                meal_plan = meal_plan_meal.meal_plan
                break
            except MealPlanMeal.DoesNotExist:
                continue

        if not meal_plan:
            logger.warning("No valid meal plan found")
            return Response({
                "error": "No valid meal plan found for the specified meals."
            }, status=404)

        logger.info(f"Retrieved meal plan with ID: {meal_plan.id}")

        # Create a mapping of meal dates
        meal_dates_map = {meal_id: date for meal_id, date in id_date_pairs}

        # If no prompt is provided, try suggest_alternative_meals first
        if not prompt:
            logger.info("No prompt provided, attempting to find alternative meals")
            # Get the days and meal types for each meal to be replaced
            days_of_week = []
            meal_types = []
            old_meal_ids = []
            
            # First, remove all the old meal plan meals
            for meal_plan_meal_id, _ in id_date_pairs:
                try:
                    meal_plan_meal = MealPlanMeal.objects.get(id=meal_plan_meal_id, meal_plan__user=request.user)
                    logger.info(f"Removing meal plan meal: {meal_plan_meal.meal.name} from {meal_plan_meal.day} {meal_plan_meal.meal_type}")
                    days_of_week.append(meal_plan_meal.day)
                    meal_types.append(meal_plan_meal.meal_type)
                    old_meal_ids.append(meal_plan_meal.meal.id)
                    meal_plan_meal.delete()
                    logger.info(f"Preparing to update: Day={meal_plan_meal.day}, Type={meal_plan_meal.meal_type}, Old Meal ID={meal_plan_meal.meal.id}")
                except MealPlanMeal.DoesNotExist:
                    logger.warning(f"Meal plan meal with ID {meal_plan_meal_id} not found or unauthorized")
                    continue

            # Use the existing suggest_alternative_meals function to get alternatives
            from shared.utils import suggest_alternative_meals
            alternatives_response = suggest_alternative_meals(
                request=request,
                meal_ids=old_meal_ids,
                days_of_week=days_of_week,
                meal_types=meal_types
            )
            logger.info(f"Alternatives response: {alternatives_response}")

            # Get the alternative meals
            alternative_meals = alternatives_response.get('alternative_meals', [])

            if alternative_meals:
                logger.info(f"Found {len(alternative_meals)} alternative meals")
                # Use the alternative meals to update the meal plan
                for idx, alternative in enumerate(alternative_meals):
                    day = days_of_week[idx]
                    meal_type = meal_types[idx]
                    new_meal_id = alternative['meal_id']
                    logger.info(f"Processing alternative meal: Day={day}, Type={meal_type}, New ID={new_meal_id}")
                    
                    # Use replace_meal_in_plan instead of direct update
                    from shared.utils import replace_meal_in_plan
                    result = replace_meal_in_plan(
                        request=request,
                        meal_plan_id=meal_plan.id,
                        old_meal_id=old_meal_ids[idx],
                        new_meal_id=new_meal_id,
                        day=day,
                        meal_type=meal_type
                    )

                    if result['status'] == 'success':
                        updates.append({
                            "old_meal": {
                                "id": old_meal_ids[idx],
                                "name": result['replaced_meal']['old_meal']
                            },
                            "new_meal": {
                                "id": new_meal_id,
                                "name": result['replaced_meal']['new_meal'],
                                "was_generated": False
                            }
                        })
                        processed_meals += 1
                        logger.info(f"Successfully replaced meal {processed_meals}/{total_meals}")
                    else:
                        logger.error(f"Failed to replace meal: {result['message']}")

            else:
                logger.info("No alternatives found, proceeding to generate new meals")
                # If no alternatives found, fall back to generating new meals
                
                for idx, (day, meal_type) in enumerate(zip(days_of_week, meal_types)):
                    # Get existing meal names and embeddings for remaining meals
                    existing_meal_names = set(meal_plan.mealplanmeal_set.values_list('meal__name', flat=True))
                    existing_meal_embeddings = list(meal_plan.mealplanmeal_set.values_list('meal__meal_embedding', flat=True))

                    # Generate and create a new meal
                    result = generate_and_create_meal(
                        user=request.user,
                        meal_plan=meal_plan,
                        meal_type=meal_type,
                        existing_meal_names=existing_meal_names,
                        existing_meal_embeddings=existing_meal_embeddings,
                        user_id=request.user.id,
                        day_name=day,
                        user_prompt=None
                    )

                    if result['status'] == 'success':
                        new_meal = result['meal']
                        logger.info(f"Creating new MealPlanMeal association for meal '{new_meal.name}' in meal plan {meal_plan.id}")
                        # No need to create MealPlanMeal here - it's already created by generate_and_create_meal
                        logger.info(f"Successfully created MealPlanMeal for {new_meal.name} on {day}")
                        updates.append({
                            "old_meal": {
                                "id": old_meal_ids[idx],
                                "name": result['replaced_meal']['old_meal'] if 'replaced_meal' in result else "Unknown"
                            },
                            "new_meal": {
                                "id": new_meal.id,
                                "name": new_meal.name,
                                "was_generated": True,
                                "used_pantry_items": result.get('used_pantry_items', [])
                            }
                        })
                        processed_meals += 1
                        logger.info(f"Successfully generated new meal {processed_meals}/{total_meals}")

        elif prompt:
            logger.info(f"Prompt provided: '{prompt}', proceeding to update {total_meals} meals")
            
            # Store meal info before deletion
            meal_info = []
            for meal_plan_meal_id, meal_date in id_date_pairs:
                try:
                    meal_plan_meal = MealPlanMeal.objects.get(id=meal_plan_meal_id, meal_plan__user=request.user)
                    meal_info.append({
                        'id': meal_plan_meal_id,
                        'day': meal_plan_meal.day,
                        'meal_type': meal_plan_meal.meal_type,
                        'old_meal': meal_plan_meal.meal,
                        'meal_date': meal_date
                    })
                    logger.info(f"Removing meal plan meal: {meal_plan_meal.meal.name} from {meal_plan_meal.day} {meal_plan_meal.meal_type}")
                    
                    # Delete only the specific meal plan meal
                    try:
                        with transaction.atomic():
                            # Verify no existing meal plan meal before deletion
                            existing = MealPlanMeal.objects.filter(
                                meal_plan=meal_plan,
                                day=meal_plan_meal.day,
                                meal_type=meal_plan_meal.meal_type
                            ).exclude(id=meal_plan_meal_id).exists()
                            
                            if existing:
                                raise Exception(f"Found existing meal plan meal for {meal_plan_meal.day} {meal_plan_meal.meal_type}")
                            
                            # Delete only this specific meal plan meal
                            meal_plan_meal.delete()
                            logger.info(f"Deleted meal plan meal ID {meal_plan_meal_id}")
                            
                            # Verify the deletion
                            if MealPlanMeal.objects.filter(id=meal_plan_meal_id).exists():
                                raise Exception(f"Failed to delete meal plan meal ID {meal_plan_meal_id}")
                    except Exception as e:
                        logger.error(f"Error during meal deletion: {str(e)}")
                        return Response({
                            "error": f"Failed to delete meal plan meal: {str(e)}"
                        }, status=500)
                except MealPlanMeal.DoesNotExist:
                    logger.warning(f"Meal plan meal with ID {meal_plan_meal_id} not found or unauthorized")
                    continue

            # Get existing meal names and embeddings once before the loop
            existing_meal_names = set(meal_plan.mealplanmeal_set.values_list('meal__name', flat=True))
            existing_meal_embeddings = list(meal_plan.mealplanmeal_set.values_list('meal__meal_embedding', flat=True))
            
            # Now create new meals for each removed meal
            for info in meal_info:
                logger.info(f"Generating new meal for {info['day']} {info['meal_type']}")
                result = generate_and_create_meal(
                    user=request.user,
                    meal_plan=meal_plan,
                    meal_type=info['meal_type'],
                    existing_meal_names=existing_meal_names,
                    existing_meal_embeddings=existing_meal_embeddings,
                    user_id=request.user.id,
                    day_name=info['day'],
                    user_prompt=prompt
                )

                if result['status'] == 'success':
                    new_meal = result['meal']
                    logger.info(f"Successfully generated meal '{new_meal.name}' for {info['day']} {info['meal_type']}")
                    
                    # Add to updates list - no need to create MealPlanMeal as it's already created by generate_and_create_meal
                    updates.append({
                        "old_meal": {
                            "id": info['old_meal'].id,
                            "name": info['old_meal'].name
                        },
                        "new_meal": {
                            "id": new_meal.id,
                            "name": new_meal.name,
                            "was_generated": True,
                            "used_pantry_items": result.get('used_pantry_items', [])
                        }
                    })
                    processed_meals += 1
                    logger.info(f"Successfully processed meal {processed_meals}/{total_meals}")

        # Mark the meal plan as having changes
        if updates:
            logger.info(f"Updates completed: {len(updates)} meals updated out of {total_meals} selected")
            meal_plan.has_changes = True
            meal_plan.save()
        
        logger.info("Successfully completed meal updates")
        return Response({
            "message": f"Successfully updated {len(updates)} meals",
            "updates": updates
        }, status=200)

    except Exception as e:
        logger.error(f"Error in api_update_meals_with_prompt: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return Response({
            "error": f"An error occurred: {str(e)}"
        }, status=500)

def get_user_dietary_preferences(user_id):
    """
    Get a user's dietary preferences with caching to improve performance.
    
    Parameters:
    - user_id: The ID of the user
    
    Returns:
    - A list of dietary preference names
    """
    cache_key = f"user_dietary_prefs_{user_id}"
    prefs = cache.get(cache_key)
    
    if prefs is None:
        try:
            user = CustomUser.objects.get(id=user_id)
            prefs = list(user.dietary_preferences.values_list('name', flat=True))
            # Cache for 1 hour (3600 seconds)
            cache.set(cache_key, prefs, 3600)
            logger.debug(f"Cached dietary preferences for user {user_id}")
        except Exception as e:
            logger.error(f"Error fetching dietary preferences for user {user_id}: {str(e)}")
            prefs = []
    
    return prefs

def get_available_meals_count(user_id):
    """
    Get the count of available meals for a user with caching to improve performance.
    
    Parameters:
    - user_id: The ID of the user
    
    Returns:
    - The count of available meals
    """
    cache_key = f"available_meals_count_{user_id}"
    count = cache.get(cache_key)
    
    if count is None:
        try:
            count = Meal.objects.filter(creator_id=user_id).count()
            # Cache for 15 minutes (900 seconds) as this might change more frequently
            cache.set(cache_key, count, 900)
            logger.debug(f"Cached available meals count for user {user_id}")
        except Exception as e:
            logger.error(f"Error counting available meals for user {user_id}: {str(e)}")
            count = 0
    
    return count

def get_user_postal_code(user):
    """
    Get a user's postal code with caching to improve performance.
    
    Parameters:
    - user: The user object
    
    Returns:
    - The user's postal code or None if not available
    """
    cache_key = f"user_postal_code_{user.id}"
    postal_code = cache.get(cache_key)
    
    if postal_code is None:
        try:
            if hasattr(user, 'address'):
                postal_code = user.address.input_postalcode
                # Cache for 1 day (86400 seconds) as this rarely changes
                cache.set(cache_key, postal_code, 86400)
                logger.debug(f"Cached postal code for user {user.id}")
        except Exception as e:
            logger.error(f"Error fetching postal code for user {user.id}: {str(e)}")
            postal_code = None
    
    return postal_code

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_generate_meal_plan(request):
    """
    Generate a meal plan for a specific week. The week_start_date should be provided
    in the request parameters in YYYY-MM-DD format.
    """
    # Generate a unique request ID for tracking this request through logs
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Received meal plan generation request for user {request.user.username}")
    logger.debug(f"[{request_id}] Request data: {request.data}")
    logger.debug(f"[{request_id}] Query params: {request.query_params}")

    try:
        # Get week_start_date from request parameters
        week_start_date_str = request.data.get('week_start_date') or request.query_params.get('week_start_date')
        if not week_start_date_str:
            logger.warning(f"[{request_id}] Missing week_start_date parameter in request from user {request.user.username}")
            return standardize_response(
                status="error",
                message="week_start_date parameter is required in YYYY-MM-DD format",
                details="The parameter was not found in either request body or query parameters",
                status_code=400
            )

        # Parse the date
        try:
            week_start_date = datetime.strptime(week_start_date_str, '%Y-%m-%d').date()
            week_end_date = week_start_date + timedelta(days=6)
            logger.info(f"[{request_id}] Parsed dates - Start: {week_start_date}, End: {week_end_date}")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid date format provided: {week_start_date_str}")
            return standardize_response(
                status="error",
                message="Invalid date format. Please use YYYY-MM-DD",
                details={
                    "provided_date": week_start_date_str,
                    "example": "2024-03-25",
                    "error": str(e)
                },
                status_code=400
            )

        # Check if the date is in the past
        today = timezone.now().date()
        if week_end_date < today:
            logger.warning(f"[{request_id}] Past date provided: {week_start_date}")
            return standardize_response(
                status="error",
                message="Cannot generate meal plans for past weeks",
                details={
                    "current_date": today.strftime('%Y-%m-%d'),
                    "earliest_allowed": today.strftime('%Y-%m-%d'),
                    "provided_date": week_start_date.strftime('%Y-%m-%d'),
                    "message": "Meal plans can only be generated for current or future weeks."
                },
                status_code=400
            )

        # Use a transaction to prevent race conditions
        with transaction.atomic():
            # Check if any meal plan already exists for this week (approved or not)
            existing_plan = MealPlan.objects.select_for_update().filter(
                user=request.user,
                week_start_date=week_start_date,
                week_end_date=week_end_date
            ).first()

            if existing_plan:
                # Check if the plan has meals
                meal_count = MealPlanMeal.objects.filter(meal_plan=existing_plan).count()
                
                if meal_count > 0:
                    logger.info(f"[{request_id}] Found existing meal plan (ID: {existing_plan.id}) with {meal_count} meals")
                    status_message = "approved" if existing_plan.is_approved else "pending approval"
                    
                    return standardize_response(
                        status="existing_plan",
                        message=f"A meal plan already exists for this week ({status_message}). "
                                "If you want a new plan, please delete all meals in the existing plan and generate a new one.",
                        details={
                            "meal_plan_id": existing_plan.id,
                            "is_approved": existing_plan.is_approved,
                            "has_changes": existing_plan.has_changes,
                            "meal_count": meal_count,
                            "week_start_date": existing_plan.week_start_date.strftime('%Y-%m-%d'),
                            "week_end_date": existing_plan.week_end_date.strftime('%Y-%m-%d'),
                            "action_required": "To make changes, please modify individual meals in the existing plan"
                        },
                        meal_plan=existing_plan
                    )
                else:
                    # We found an empty meal plan - log and delete it
                    logger.warning(f"[{request_id}] Found empty meal plan (ID: {existing_plan.id}) for user {request.user.username}")
                    existing_plan_id = existing_plan.id
                    existing_plan.delete()
                    logger.info(f"[{request_id}] Deleted empty meal plan (ID: {existing_plan_id})")
                    # Continue to meal plan creation

            # Use the existing create_meal_plan_for_user function
            from meals.meal_plan_service import create_meal_plan_for_user
            
            logger.info(f"[{request_id}] Calling create_meal_plan_for_user for user {request.user.username}")
            
            # Wrap the meal plan creation in a try-except block to catch specific errors
            try:
                meal_plan = create_meal_plan_for_user(
                    user=request.user,
                    start_of_week=week_start_date,
                    end_of_week=week_end_date,
                    monday_date=week_start_date,
                    request_id=request_id
                )
            except Exception as e:
                logger.error(f"[{request_id}] Error in create_meal_plan_for_user: {str(e)}")
                logger.error(f"[{request_id}] Full traceback: {traceback.format_exc()}")
                
                return standardize_response(
                    status="error",
                    message="Error creating meal plan",
                    details={
                        "error_details": str(e),
                        "error_type": e.__class__.__name__,
                        "suggestion": "Please try again later or contact support"
                    },
                    status_code=500
                )

            # Check if meal_plan is None (shouldn't happen with our updated function, but just in case)
            if not meal_plan:
                logger.error(f"[{request_id}] Failed to generate meal plan for user {request.user.username}")
                
                # Get user's postal code safely
                user_postal_code = get_user_postal_code(request.user)
                
                # Get user's dietary preferences safely
                dietary_preferences = get_user_dietary_preferences(request.user.id)
                
                # Get count of available meals for better context
                available_meals_count = get_available_meals_count(request.user.id)

                return standardize_response(
                    status="error",
                    message="Could not generate meal plan. No suitable meals available.",
                    details={
                        "user_postal_code": user_postal_code,
                        "dietary_preferences": dietary_preferences,
                        "available_meals_count": available_meals_count,
                        "possible_reasons": [
                            "No chefs are currently serving your area",
                            "No meals match your dietary preferences",
                            "No meals are available for the selected dates"
                        ],
                        "suggestion": "Try adjusting your dietary preferences or choosing a different week"
                    },
                    status_code=400
                )

            # Get the meal plan meals
            meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
            meals_added = meal_plan_meals.count()
            
            # Check if we actually added any meals
            if meals_added == 0:
                logger.warning(f"[{request_id}] Created meal plan (ID: {meal_plan.id}) but no meals were added")
                meal_plan.delete()
                return standardize_response(
                    status="error",
                    message="Could not generate meal plan. No suitable meals available.",
                    details={
                        "reason": "Failed to add any meals to the plan",
                        "suggestion": "Try again later or contact support"
                    },
                    status_code=400
                )

            # Verify day names match dates for each meal
            day_mismatches = []
            for mpm in meal_plan_meals:
                expected_day = mpm.meal_date.strftime("%A")
                if mpm.day != expected_day:
                    day_mismatches.append({
                        "meal_id": mpm.meal.id,
                        "meal_name": mpm.meal.name,
                        "stored_day": mpm.day,
                        "expected_day": expected_day,
                        "date": mpm.meal_date.strftime("%Y-%m-%d")
                    })
            
            if day_mismatches:
                logger.warning(f"[{request_id}] Found {len(day_mismatches)} day mismatches in meal plan {meal_plan.id}")
                for mismatch in day_mismatches:
                    logger.warning(f"[{request_id}] Day mismatch: {mismatch}")
            
            logger.info(f"[{request_id}] Successfully generated meal plan (ID: {meal_plan.id}) with {meals_added} meals")
            
            # Return the generated meal plan
            return standardize_response(
                status="success",
                message="Meal plan generated successfully",
                details={
                    "meals_added": meals_added,
                    "week_start_date": meal_plan.week_start_date.strftime('%Y-%m-%d'),
                    "week_end_date": meal_plan.week_end_date.strftime('%Y-%m-%d'),
                    "used_pantry_items": any(hasattr(mpm, 'pantry_usage') and mpm.pantry_usage.exists() for mpm in meal_plan_meals),
                    "day_mismatches": day_mismatches if day_mismatches else None
                },
                meal_plan=meal_plan,
                status_code=201
            )

    except Exception as e:
        logger.error(f"[{request_id}] Error generating meal plan: {str(e)}")
        logger.error(f"[{request_id}] Full traceback: {traceback.format_exc()}")
        return standardize_response(
            status="error",
            message="An error occurred while generating the meal plan",
            details={
                "error_details": str(e),
                "error_type": e.__class__.__name__,
                "suggestion": "Please try again later or contact support"
            },
            status_code=500
        )

def standardize_response(status, message, details=None, status_code=200, meal_plan=None):
    """
    Helper function to standardize API responses
    
    Parameters:
    - status: A string indicating the status of the operation (e.g., "success", "error", "existing_plan")
    - message: A user-friendly message describing the result
    - details: Optional dictionary with additional context about the operation
    - status_code: HTTP status code to return
    - meal_plan: Optional MealPlan object to serialize and include in the response
    
    Returns:
    - A Response object with a standardized structure
    """
    response = {
        "status": status,
        "message": message
    }
    
    if details:
        response["details"] = details
        
    if meal_plan:
        serializer = MealPlanSerializer(meal_plan)
        response["meal_plan"] = serializer.data
        
    return Response(response, status=status_code)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_user_profile(request):
    """
    API endpoint to retrieve the authenticated user's profile information
    including properly serialized dietary preferences.
    """
    if request.method == 'GET':
        # Serialize the current user with the UserSerializer
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_get_meal_by_id(request, meal_id):
    """
    API endpoint to retrieve details for a specific meal,
    including properly serialized dietary preferences.
    """
    try:
        meal = get_object_or_404(Meal, id=meal_id)
        serializer = MealSerializer(meal)
        return Response(serializer.data, status=200)
    except Exception as e:
        logger.error(f"Error fetching meal details: {str(e)}")
        return Response({"error": str(e)}, status=500)

# Chef Meal Event Views
@login_required
def chef_meal_dashboard(request):
    """Dashboard for chefs to manage their meal events"""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        messages.error(request, "You do not have a chef profile.")
        return redirect('home')
    
    # Get all chef's meal events
    upcoming_events = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__gte=timezone.now().date()
    ).order_by('event_date', 'event_time')
    
    past_events = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__lt=timezone.now().date()
    ).order_by('-event_date', '-event_time')[:10]  # Show only 10 past events
    
    context = {
        'chef': chef,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
    }
    return render(request, 'meals/chef_meal_dashboard.html', context)

@login_required
def create_chef_meal_event(request):
    """Create a new meal event as a chef"""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        messages.error(request, "You do not have a chef profile.")
        return redirect('home')
    
    # Get meals that belong to this chef
    chef_meals = Meal.objects.filter(chef=chef)
    
    if request.method == 'POST':
        # Get form data
        meal_id = request.POST.get('meal')
        event_date = request.POST.get('event_date')
        event_time = request.POST.get('event_time')
        cutoff_time = request.POST.get('order_cutoff_time')
        base_price = request.POST.get('base_price')
        min_price = request.POST.get('min_price')
        max_orders = request.POST.get('max_orders')
        min_orders = request.POST.get('min_orders')
        description = request.POST.get('description')
        special_instructions = request.POST.get('special_instructions')
        
        try:
            # Validate form data
            meal = Meal.objects.get(id=meal_id, chef=chef)
            
            # Convert cutoff time string to datetime
            cutoff_datetime = timezone.datetime.strptime(
                f"{event_date} {cutoff_time}", 
                "%Y-%m-%d %H:%M"
            )
            
            # Create the ChefMealEvent
            event = ChefMealEvent.objects.create(
                chef=chef,
                meal=meal,
                event_date=event_date,
                event_time=event_time,
                order_cutoff_time=cutoff_datetime,
                base_price=base_price,
                current_price=base_price,  # Initially same as base price
                min_price=min_price,
                max_orders=max_orders,
                min_orders=min_orders,
                description=description,
                special_instructions=special_instructions,
                status='scheduled'
            )
            
            messages.success(request, f"Meal event '{meal.name}' scheduled successfully for {event_date}.")
            return redirect('chef_meal_dashboard')
            
        except (Meal.DoesNotExist, ValueError) as e:
            messages.error(request, f"Error creating meal event: {str(e)}")
    
    context = {
        'chef': chef,
        'chef_meals': chef_meals,
    }
    return render(request, 'meals/create_chef_meal_event.html', context)

@login_required
def edit_chef_meal_event(request, event_id):
    """Edit an existing meal event"""
    try:
        chef = Chef.objects.get(user=request.user)
        event = ChefMealEvent.objects.get(id=event_id, chef=chef)
    except Chef.DoesNotExist:
        messages.error(request, "You do not have a chef profile.")
        return redirect('home')
    except ChefMealEvent.DoesNotExist:
        messages.error(request, "Meal event not found.")
        return redirect('chef_meal_dashboard')
    
    # Check if event can be edited (not too close to event date or has orders)
    now = timezone.now()
    cutoff = timezone.datetime.combine(event.event_date, event.event_time, tzinfo=timezone.get_current_timezone()) - timezone.timedelta(hours=24)
    
    if now > cutoff:
        messages.error(request, "This event is too close to its scheduled date and cannot be edited.")
        return redirect('chef_meal_dashboard')
    
    if event.orders_count > 0:
        messages.warning(request, "This event has orders. Some fields cannot be modified.")
    
    if request.method == 'POST':
        # Get form data
        event_date = request.POST.get('event_date')
        event_time = request.POST.get('event_time')
        cutoff_time = request.POST.get('order_cutoff_time')
        description = request.POST.get('description')
        special_instructions = request.POST.get('special_instructions')
        
        # Fields that can only be edited if no orders exist
        if event.orders_count == 0:
            base_price = request.POST.get('base_price')
            min_price = request.POST.get('min_price')
            max_orders = request.POST.get('max_orders')
            min_orders = request.POST.get('min_orders')
            
            event.base_price = base_price
            event.min_price = min_price
            event.max_orders = max_orders
            event.min_orders = min_orders
            
            # If price is changing, update current price too
            if float(base_price) != float(event.base_price):
                event.current_price = base_price
        
        # Convert cutoff time string to datetime
        cutoff_datetime = timezone.datetime.strptime(
            f"{event_date} {cutoff_time}", 
            "%Y-%m-%d %H:%M"
        )
        
        # Update the event
        event.event_date = event_date
        event.event_time = event_time
        event.order_cutoff_time = cutoff_datetime
        event.description = description
        event.special_instructions = special_instructions
        event.save()
        
        messages.success(request, f"Meal event updated successfully.")
        return redirect('chef_meal_dashboard')
    
    # Pre-populate the form
    context = {
        'chef': chef,
        'event': event,
        'has_orders': event.orders_count > 0,
    }
    return render(request, 'meals/edit_chef_meal_event.html', context)

@login_required
def cancel_chef_meal_event(request, event_id):
    """Cancel a meal event and notify customers"""
    try:
        chef = Chef.objects.get(user=request.user)
        event = ChefMealEvent.objects.get(id=event_id, chef=chef)
    except Chef.DoesNotExist:
        messages.error(request, "You do not have a chef profile.")
        return redirect('home')
    except ChefMealEvent.DoesNotExist:
        messages.error(request, "Meal event not found.")
        return redirect('chef_meal_dashboard')
    
    # Process cancellation
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '')
        
        # Cancel the event
        event.status = 'cancelled'
        event.save()
        
        # Cancel all orders and prepare for refunds
        orders = ChefMealOrder.objects.filter(meal_event=event, status__in=['placed', 'confirmed'])
        
        # For now, just mark orders as cancelled
        # In a real implementation, we would trigger Stripe refunds here
        orders.update(status='cancelled')
        
        # Create payment logs for all cancelled orders
        for order in orders:
            PaymentLog.objects.create(
                chef_meal_order=order,
                user=order.customer,
                chef=chef,
                action='refund',
                amount=order.price_paid * order.quantity,
                status='pending',
                details={
                    'cancellation_reason': reason,
                    'cancelled_by': 'chef',
                    'event_id': event.id,
                    'event_name': event.meal.name
                }
            )
        
        # TODO: Send email notifications to customers
        
        messages.success(request, f"Meal event '{event.meal.name}' has been cancelled.")
        return redirect('chef_meal_dashboard')
    
    context = {
        'chef': chef,
        'event': event,
    }
    return render(request, 'meals/cancel_chef_meal_event.html', context)

# Customer-facing views for chef meals
@login_required
def browse_chef_meals(request):
    """Browse available chef meal events"""
    # Get the user's location/postal code to filter by service area
    user_address = None
    if hasattr(request.user, 'addresses'):
        user_address = request.user.addresses.filter(is_default=True).first()
    
    # Get all upcoming meal events
    now = timezone.now()
    upcoming_events = ChefMealEvent.objects.filter(
        event_date__gte=now.date(),
        status__in=['scheduled', 'open'],
        order_cutoff_time__gt=now
    ).select_related('chef', 'meal').order_by('event_date', 'event_time')
    
    # Filter by postal code if the user has an address
    if user_address and hasattr(user_address, 'postal_code'):
        # Get all chefs serving this postal code
        postal_code_obj = PostalCode.objects.filter(code=user_address.postal_code).first()
        if postal_code_obj:
            chef_ids = ChefPostalCode.objects.filter(
                postal_code=postal_code_obj
            ).values_list('chef_id', flat=True)
            
            upcoming_events = upcoming_events.filter(chef_id__in=chef_ids)
    
    # Group by date for display
    events_by_date = {}
    for event in upcoming_events:
        date_str = event.event_date.strftime('%Y-%m-%d')
        if date_str not in events_by_date:
            events_by_date[date_str] = []
        events_by_date[date_str].append(event)
    
    context = {
        'events_by_date': events_by_date,
        'user_address': user_address,
    }
    return render(request, 'meals/browse_chef_meals.html', context)

@login_required
def chef_meal_detail(request, event_id):
    """View details for a specific chef meal event"""
    try:
        event = ChefMealEvent.objects.select_related('chef', 'meal').get(id=event_id)
    except ChefMealEvent.DoesNotExist:
        messages.error(request, "Meal event not found.")
        return redirect('browse_chef_meals')
    
    # Check if user is in chef's service area
    user_can_order = True
    user_address = None
    if hasattr(request.user, 'addresses'):
        user_address = request.user.addresses.filter(is_default=True).first()
        
        if user_address and hasattr(user_address, 'postal_code'):
            postal_code_obj = PostalCode.objects.filter(code=user_address.postal_code).first()
            if postal_code_obj:
                chef_serves_area = ChefPostalCode.objects.filter(
                    chef=event.chef,
                    postal_code=postal_code_obj
                ).exists()
                
                user_can_order = chef_serves_area
    
    # Check if user already has an order for this event
    user_order = None
    if request.user.is_authenticated:
        user_order = ChefMealOrder.objects.filter(
            customer=request.user,
            meal_event=event
        ).first()
    
    # Get chef's other upcoming events
    other_events = ChefMealEvent.objects.filter(
        chef=event.chef,
        event_date__gte=timezone.now().date(),
        status__in=['scheduled', 'open']
    ).exclude(id=event.id).order_by('event_date', 'event_time')[:5]
    
    context = {
        'event': event,
        'user_can_order': user_can_order and event.is_available_for_orders(),
        'user_address': user_address,
        'user_order': user_order,
        'other_events': other_events,
    }
    return render(request, 'meals/chef_meal_detail.html', context)

@login_required
def place_chef_meal_order(request, event_id):
    """Place an order for a chef meal event"""
    try:
        event = ChefMealEvent.objects.select_related('chef', 'meal').get(id=event_id)
    except ChefMealEvent.DoesNotExist:
        messages.error(request, "Meal event not found.")
        return redirect('browse_chef_meals')
    
    # Check if the event is available for orders
    if not event.is_available_for_orders():
        messages.error(request, "This meal is no longer available for orders.")
        return redirect('chef_meal_detail', event_id=event.id)
    
    # Check if user is in chef's service area
    user_address = None
    if hasattr(request.user, 'addresses'):
        user_address = request.user.addresses.filter(is_default=True).first()
        
        if user_address and hasattr(user_address, 'postal_code'):
            postal_code_obj = PostalCode.objects.filter(code=user_address.postal_code).first()
            if postal_code_obj:
                chef_serves_area = ChefPostalCode.objects.filter(
                    chef=event.chef,
                    postal_code=postal_code_obj
                ).exists()
                
                if not chef_serves_area:
                    messages.error(request, "This chef does not deliver to your area.")
                    return redirect('chef_meal_detail', event_id=event.id)
    
    # Handle form submission
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        special_requests = request.POST.get('special_requests', '')
        
        # Create/get the main order
        order, created = Order.objects.get_or_create(
            customer=request.user,
            status='Placed',
            is_paid=False,
            defaults={
                'address': user_address,
                'delivery_method': 'Delivery' if user_address else 'Pickup',
            }
        )
        
        # Create the chef meal order
        chef_meal_order = ChefMealOrder.objects.create(
            order=order,
            meal_event=event,
            customer=request.user,
            quantity=quantity,
            price_paid=event.current_price,
            special_requests=special_requests,
            status='placed'
        )
        
        # Here, we would typically redirect to a payment page
        # For now, just redirect to the order confirmation
        messages.success(request, f"Your order for {event.meal.name} has been placed. Please complete payment.")
        return redirect('view_chef_meal_order', order_id=chef_meal_order.id)
    
    context = {
        'event': event,
        'user_address': user_address,
    }
    return render(request, 'meals/place_chef_meal_order.html', context)

@login_required
def view_chef_meal_order(request, order_id):
    """View a specific chef meal order"""
    try:
        order = ChefMealOrder.objects.select_related('meal_event', 'meal_event__chef', 'meal_event__meal').get(
            id=order_id,
            customer=request.user
        )
    except ChefMealOrder.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('user_orders')
    
    context = {
        'order': order,
        'event': order.meal_event,
    }
    return render(request, 'meals/view_chef_meal_order.html', context)

@login_required
def user_chef_meal_orders(request):
    """View all chef meal orders for a user"""
    # Get upcoming and past orders
    upcoming_orders = ChefMealOrder.objects.filter(
        customer=request.user,
        meal_event__event_date__gte=timezone.now().date(),
        status__in=['placed', 'confirmed']
    ).select_related('meal_event', 'meal_event__meal', 'meal_event__chef').order_by('meal_event__event_date', 'meal_event__event_time')
    
    past_orders = ChefMealOrder.objects.filter(
        customer=request.user,
        meal_event__event_date__lt=timezone.now().date()
    ).select_related('meal_event', 'meal_event__meal', 'meal_event__chef').order_by('-meal_event__event_date', '-meal_event__event_time')
    
    # Get cancelled orders
    cancelled_orders = ChefMealOrder.objects.filter(
        customer=request.user,
        status__in=['cancelled', 'refunded']
    ).select_related('meal_event', 'meal_event__meal', 'meal_event__chef').order_by('-created_at')
    
    context = {
        'upcoming_orders': upcoming_orders,
        'past_orders': past_orders,
        'cancelled_orders': cancelled_orders,
    }
    return render(request, 'meals/user_chef_meal_orders.html', context)

@login_required
def cancel_chef_meal_order(request, order_id):
    """Cancel a chef meal order"""
    try:
        order = ChefMealOrder.objects.select_related('meal_event').get(
            id=order_id,
            customer=request.user
        )
    except ChefMealOrder.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('user_chef_meal_orders')
    
    # Check if order can be cancelled
    now = timezone.now()
    cutoff = timezone.datetime.combine(order.meal_event.event_date, order.meal_event.event_time, tzinfo=timezone.get_current_timezone()) - timezone.timedelta(hours=24)
    
    if now > cutoff:
        messages.error(request, "This order is too close to its scheduled date and cannot be cancelled.")
        return redirect('user_chef_meal_orders')
    
    if order.status not in ['placed', 'confirmed']:
        messages.error(request, "This order cannot be cancelled.")
        return redirect('user_chef_meal_orders')
    
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '')
        
        # Process cancellation
        success = order.cancel()
        
        if success:
            # Create payment log for refund
            PaymentLog.objects.create(
                chef_meal_order=order,
                user=request.user,
                chef=order.meal_event.chef,
                action='refund',
                amount=order.price_paid * order.quantity,
                status='pending',
                details={
                    'cancellation_reason': reason,
                    'cancelled_by': 'customer',
                    'order_id': order.id
                }
            )
            
            messages.success(request, "Your order has been cancelled. If you made a payment, you will receive a refund.")
        else:
            messages.error(request, "Could not cancel your order.")
        
        return redirect('user_chef_meal_orders')
    
    context = {
        'order': order,
        'event': order.meal_event,
    }
    return render(request, 'meals/cancel_chef_meal_order.html', context)

@login_required
def review_chef_meal(request, order_id):
    """Leave a review for a completed chef meal"""
    try:
        order = ChefMealOrder.objects.select_related('meal_event', 'meal_event__chef', 'meal_event__meal').get(
            id=order_id,
            customer=request.user,
            status='completed'
        )
    except ChefMealOrder.DoesNotExist:
        messages.error(request, "Order not found or not eligible for review.")
        return redirect('user_chef_meal_orders')
    
    # Check if review already exists
    existing_review = ChefMealReview.objects.filter(chef_meal_order=order).first()
    
    if existing_review:
        messages.info(request, "You have already reviewed this meal.")
        return redirect('user_chef_meal_orders')
    
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 5))
        comment = request.POST.get('comment', '')
        
        # Create the review
        review = ChefMealReview.objects.create(
            chef_meal_order=order,
            customer=request.user,
            chef=order.meal_event.chef,
            meal_event=order.meal_event,
            rating=rating,
            comment=comment
        )
        
        messages.success(request, "Thank you for your review!")
        return redirect('user_chef_meal_orders')
    
    context = {
        'order': order,
        'event': order.meal_event,
    }
    return render(request, 'meals/review_chef_meal.html', context)

# API Endpoints for Chef Meal functionality

class ChefMealEventPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class ChefMealEventViewSet(viewsets.ModelViewSet):
    pagination_class = ChefMealEventPagination
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by chef if we're looking at chef's own events
        if self.action in ['list', 'retrieve'] and self.request.query_params.get('my_events') == 'true':
            try:
                chef = Chef.objects.get(user=user)
                return ChefMealEvent.objects.filter(chef=chef).order_by('event_date', 'event_time')
            except Chef.DoesNotExist:
                return ChefMealEvent.objects.none()
                
        # Filter by postal code if provided
        postal_code = self.request.query_params.get('postal_code')
        if postal_code:
            # Find all chefs that serve this postal code
            chef_ids = ChefPostalCode.objects.filter(
                postal_code__code=postal_code
            ).values_list('chef_id', flat=True)
            
            # Filter events by these chefs and availability
            now = timezone.now()
            return ChefMealEvent.objects.filter(
                chef_id__in=chef_ids,
                status__in=['scheduled', 'open'],
                order_cutoff_time__gt=now,
                orders_count__lt=F('max_orders')
            ).order_by('event_date', 'event_time')
        
        # Default: show available events
        now = timezone.now()
        return ChefMealEvent.objects.filter(
            status__in=['scheduled', 'open'],
            order_cutoff_time__gt=now,
            orders_count__lt=F('max_orders')
        ).order_by('event_date', 'event_time')
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ChefMealEventCreateSerializer
        return ChefMealEventSerializer
    
    def perform_create(self, serializer):
        try:
            chef = Chef.objects.get(user=self.request.user)
        except Chef.DoesNotExist:
            return Response(
                {"error": "You must be a registered chef to create meal events"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save(chef=chef)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        event = self.get_object()
        
        # Check if the user is the owner of this event
        if event.chef.user != request.user:
            return Response(
                {"error": "You don't have permission to cancel this event"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if the event can be cancelled
        if event.status == 'cancelled':
            return Response(
                {"error": "This event is already cancelled"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if event.event_date < timezone.now().date():
            return Response(
                {"error": "You cannot cancel past events"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cancel the event and issue refunds
        try:
            event.cancel()
            return Response({"status": "Event cancelled successfully"})
        except Exception as e:
            return Response(
                {"error": f"Failed to cancel event: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChefMealOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Chef viewing their received orders
        if self.request.query_params.get('as_chef') == 'true':
            try:
                chef = Chef.objects.get(user=user)
                return ChefMealOrder.objects.filter(meal_event__chef=chef).order_by('-created_at')
            except Chef.DoesNotExist:
                return ChefMealOrder.objects.none()
        
        # Default: customer viewing their own orders
        return ChefMealOrder.objects.filter(customer=user).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action in ['create']:
            return ChefMealOrderCreateSerializer
        return ChefMealOrderSerializer
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        
        # Check if the user is the owner of this order
        if order.customer != request.user:
            return Response(
                {"error": "You don't have permission to cancel this order"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if the order can be cancelled
        if order.status not in ['placed', 'confirmed']:
            return Response(
                {"error": "This order cannot be cancelled in its current state"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if we're past the deadline
        event = order.meal_event
        now = timezone.now()
        if now > event.order_cutoff_time:
            return Response(
                {"error": "The cancellation period has passed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cancel the order
        try:
            order.cancel()
            return Response({"status": "Order cancelled successfully"})
        except Exception as e:
            return Response(
                {"error": f"Failed to cancel order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChefMealReviewViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ChefMealReviewSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by chef if requested
        chef_id = self.request.query_params.get('chef_id')
        if chef_id:
            return ChefMealReview.objects.filter(chef_id=chef_id).order_by('-created_at')
        
        # Filter by meal event if requested
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return ChefMealReview.objects.filter(meal_event_id=event_id).order_by('-created_at')
        
        # Default: return reviews left by this user
        return ChefMealReview.objects.filter(customer=user).order_by('-created_at')
    
    def perform_create(self, serializer):
        order = serializer.validated_data['chef_meal_order']
        
        # Ensure the user is the owner of this order
        if order.customer != self.request.user:
            raise PermissionDenied("You don't have permission to review this order")
        
        serializer.save(
            customer=self.request.user,
            chef=order.meal_event.chef,
            meal_event=order.meal_event
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_chef_dashboard_stats(request):
    """Get statistics for the chef dashboard"""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response(
            {"error": "You must be a registered chef to access dashboard stats"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get counts
    now = timezone.now()
    upcoming_events_count = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__gte=now.date(),
        status__in=['scheduled', 'open']
    ).count()
    
    active_orders_count = ChefMealOrder.objects.filter(
        meal_event__chef=chef,
        status__in=['placed', 'confirmed']
    ).count()
    
    past_events_count = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__lt=now.date()
    ).count()
    
    # Get revenue stats
    revenue_this_month = ChefMealOrder.objects.filter(
        meal_event__chef=chef,
        status__in=['completed'],
        created_at__year=now.year,
        created_at__month=now.month
    ).aggregate(total=Sum(F('price_paid') * F('quantity')))['total'] or 0
    
    # Get rating and reviews
    review_count = ChefMealReview.objects.filter(chef=chef).count()
    avg_rating = ChefMealReview.objects.filter(chef=chef).aggregate(
        avg=Avg('rating')
    )['avg'] or 0
    
    return Response({
        'upcoming_events_count': upcoming_events_count,
        'active_orders_count': active_orders_count,
        'past_events_count': past_events_count,
        'revenue_this_month': str(revenue_this_month),
        'review_count': review_count,
        'avg_rating': avg_rating
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_stripe_account_status(request):
    """Check if the chef has a Stripe Connect account"""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response(
            {"error": "You must be a registered chef to access Stripe account information"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        stripe_account = StripeConnectAccount.objects.get(chef=chef)
        return Response({
            'has_account': True,
            'is_active': stripe_account.is_active,
            'account_id': stripe_account.stripe_account_id
        })
    except StripeConnectAccount.DoesNotExist:
        return Response({'has_account': False})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_create_stripe_account_link(request):
    """Create a Stripe Connect onboarding link for the chef"""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return Response(
            {"error": "You must be a registered chef to create a Stripe account"},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check if we already have a Stripe account
    try:
        stripe_account = StripeConnectAccount.objects.get(chef=chef)
        account_id = stripe_account.stripe_account_id
    except StripeConnectAccount.DoesNotExist:
        # Create a new Stripe account
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        try:
            account = stripe.Account.create(
                type="express",
                country="US",
                email=request.user.email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                business_type="individual",
                business_profile={
                    "name": f"{request.user.first_name} {request.user.last_name}",
                    "product_description": "Chef prepared meals"
                }
            )
            
            # Save the account to our database
            stripe_account = StripeConnectAccount.objects.create(
                chef=chef,
                stripe_account_id=account.id,
                is_active=False
            )
            account_id = account.id
        except stripe.error.StripeError as e:
            return Response(
                {"error": f"Failed to create Stripe account: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Create an account link for onboarding
    try:
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=request.build_absolute_uri(reverse('meals:api_stripe_account_status')),
            return_url=request.build_absolute_uri(reverse('meals:api_stripe_account_status')),
            type="account_onboarding",
        )
        
        return Response({
            'url': account_link.url
        })
    except stripe.error.StripeError as e:
        return Response(
            {"error": f"Failed to create account link: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_process_chef_meal_payment(request, order_id):
    """Process payment for a chef meal order"""
    # Get the order
    order = get_object_or_404(ChefMealOrder, id=order_id, customer=request.user)
    
    # Check if the order can be paid for
    if order.status != 'placed':
        return Response(
            {"error": "This order cannot be paid for in its current state"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Initialize Stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Get the payment token from the request
    token = request.data.get('token')
    if not token:
        return Response(
            {"error": "Payment token is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get the platform fee percentage
    platform_fee_percentage = PlatformFeeConfig.get_active_fee()
    
    # Calculate the amount to charge
    amount = int(float(order.price_paid) * 100)  # Convert to cents
    platform_fee = int(amount * float(platform_fee_percentage) / 100)
    
    try:
        # Create a payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            payment_method=token,
            confirm=True,
            application_fee_amount=platform_fee,
            transfer_data={
                "destination": order.meal_event.chef.stripe_account.stripe_account_id,
            },
            metadata={
                "order_id": order.id,
                "customer_id": request.user.id,
                "chef_id": order.meal_event.chef.id,
                "event_id": order.meal_event.id
            }
        )
        
        # Update the order
        order.stripe_payment_intent_id = payment_intent.id
        order.status = 'confirmed'
        order.save()
        
        # Log the payment
        PaymentLog.objects.create(
            order=order.order,
            chef_meal_order=order,
            user=request.user,
            chef=order.meal_event.chef,
            action='charge',
            amount=order.price_paid,
            stripe_id=payment_intent.id,
            status='succeeded',
            details={
                'payment_intent_id': payment_intent.id,
                'platform_fee': platform_fee / 100  # Convert back to dollars
            }
        )
        
        return Response({
            'success': True,
            'order_id': order.id,
            'status': order.status,
            'payment_intent_id': payment_intent.id
        })
    except stripe.error.StripeError as e:
        return Response(
            {"error": f"Payment failed: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_process_meal_payment(request, order_id):
    """
    API endpoint for processing payments for regular meal orders.
    This is similar to the template-based process_payment view but adapted for API use.
    """
    # Get the order object
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    try:
        # Get payment token from request data instead of POST
        payment_token = request.data.get('payment_token')
        if not payment_token:
            return Response(
                {"error": "Payment token is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        charge = stripe.Charge.create(
            amount=int(order.total_price() * 100),  # amount in cents
            currency='usd',
            description=f'Order {order.id}',
            source=payment_token
        )
        
        if charge.paid:
            order.is_paid = True
            order.status = 'Completed'
            order.save()

            # After the order is marked as completed, process each meal in the order
            for order_meal in order.ordermeal_set.all():
                meal = order_meal.meal
                # Create calorie intake record if this model exists
                try:
                    from .models import CalorieIntake
                    CalorieIntake.objects.create(
                        user=request.user,
                        meal_name=meal.name,
                        meal_description=meal.description,
                        portion_size="1", 
                        date_recorded=timezone.now()
                    )
                except ImportError:
                    # CalorieIntake model might not exist, so we'll skip this
                    pass
            
            return Response({
                "status": "success",
                "message": "Payment processed successfully",
                "order_id": order.id
            })
        else:
            return Response(
                {"error": "Payment unsuccessful"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    except stripe.error.CardError as e:
        # The card has been declined
        body = e.json_body
        err = body.get('error', {})
        return Response(
            {"error": f"Card error: {err.get('message')}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": f"An unexpected error occurred: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_stripe_webhook(request):
    """
    Handles Stripe webhook events for both regular meal orders and chef meal orders.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Handle the event
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object
        
        # Look for chef meal orders with this payment intent
        try:
            chef_meal_order = ChefMealOrder.objects.get(stripe_payment_intent_id=payment_intent.id)
            chef_meal_order.status = 'confirmed'
            chef_meal_order.save()
            
            # Log the payment
            PaymentLog.objects.create(
                chef_meal_order=chef_meal_order,
                user=chef_meal_order.customer,
                chef=chef_meal_order.meal_event.chef,
                action='charge',
                amount=chef_meal_order.price_paid,
                stripe_id=payment_intent.id,
                status='succeeded',
                details={'payment_intent': payment_intent}
            )
        except ChefMealOrder.DoesNotExist:
            # Not a chef meal order, check if it's a regular order
            # Regular orders would need to have the stripe payment intent ID stored as well
            pass
            
    elif event.type == 'charge.refunded':
        refund = event.data.object
        payment_intent_id = refund.payment_intent
        
        # Look for chef meal orders with this payment intent
        try:
            chef_meal_order = ChefMealOrder.objects.get(stripe_payment_intent_id=payment_intent_id)
            chef_meal_order.status = 'refunded'
            chef_meal_order.stripe_refund_id = refund.id
            chef_meal_order.save()
            
            # Log the refund
            PaymentLog.objects.create(
                chef_meal_order=chef_meal_order,
                user=chef_meal_order.customer,
                chef=chef_meal_order.meal_event.chef,
                action='refund',
                amount=refund.amount / 100,  # Convert cents to dollars
                stripe_id=refund.id,
                status='succeeded',
                details={'refund': refund}
            )
        except ChefMealOrder.DoesNotExist:
            # Not a chef meal order, check if it's a regular order
            pass
    
    # Return a 200 response to acknowledge receipt of the event
    return Response({"status": "success"})