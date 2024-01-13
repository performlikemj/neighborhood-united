from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from meals.models import Order, Dish, Meal, Cart, MealPlanMeal, MealPlan, Meal
from custom_auth.models import CustomUser, UserRole
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import GoalTracking, ChatThread, UserHealthMetrics
from .forms import GoalForm
import openai
from openai import NotFoundError, OpenAI, OpenAIError
import pytz
import json
import os
import re
import time
from django.conf import settings
from shared.utils import (get_user_info, post_review, update_review, delete_review, replace_meal_in_plan, 
                          remove_meal_from_plan, list_upcoming_meals, get_date, create_meal_plan, 
                          add_meal_to_plan, auth_get_meal_plan, auth_search_chefs, auth_search_dishes, 
                          approve_meal_plan, auth_search_ingredients, auth_search_meals_excluding_ingredient, 
                          search_meal_ingredients, suggest_alternative_meals,guest_search_ingredients ,
                          guest_get_meal_plan, guest_search_chefs, guest_search_dishes, 
                          generate_review_summary, sanitize_query, access_past_orders, get_goal, 
                          update_goal, adjust_week_shift)
from customer_dashboard.utils import (api_get_user_info, api_access_past_orders, api_adjust_current_week, 
                          api_adjust_week_shift)
from local_chefs.views import chef_service_areas, service_area_chefs
from django.core import serializers
from .serializers import ChatThreadSerializer, GoalTrackingSerializer, UserHealthMetricsSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .permissions import IsCustomer
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
import datetime

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_metrics(request):
    user = request.user

    if request.method == 'GET':
        user_metrics = UserHealthMetrics.objects.filter(user=user).order_by('-date_recorded')[:5]
        serializer = UserHealthMetricsSerializer(user_metrics, many=True)
        
        current_week_metrics = any(metric.is_current_week() for metric in user_metrics)
        print(f'Current week metrics: {current_week_metrics}')
        if not current_week_metrics:
            return Response({"message": "Please update your health metrics for the current week."})
        print(f'Serializer data: {serializer.data}')
        return Response(serializer.data)

    elif request.method == 'POST':
        date_recorded = request.data.get('date_recorded')
        date_recorded = datetime.datetime.strptime(date_recorded, '%Y-%m-%d').date()  # convert string to date

        # Try to get the existing metric for the specified date
        metric = UserHealthMetrics.objects.filter(user=user, date_recorded=date_recorded).first()

        if metric:
            # Update existing metric
            for key, value in request.data.items():
                setattr(metric, key, value)
            metric.save()
        else:
            # Create a new metric
            metric = UserHealthMetrics.objects.create(user=user, date_recorded=date_recorded, **request.data)

        return Response({"message": "Health metric updated."})



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_user_goal_view(request):
    # Fetch or create goal for the user
    print(f'Request: {request}')
    goal, created = GoalTracking.objects.get_or_create(user=request.user)
    serializer = GoalTrackingSerializer(goal)
    return Response(serializer.data)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_goal_management(request):
    if request.method == 'GET':
        goal, created = GoalTracking.objects.get_or_create(user=request.user)
        serializer = GoalTrackingSerializer(goal)
        return Response(serializer.data)

    elif request.method == 'POST':
        goal, created = GoalTracking.objects.get_or_create(user=request.user)
        serializer = GoalTrackingSerializer(goal, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'success': True, 'message': 'Goal updated successfully'})
        return Response(serializer.errors, status=400)



@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_history_page(request):
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')[:5]
    serializer = ChatThreadSerializer(chat_threads, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_thread_history(request):
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')
    paginator = PageNumberPagination()
    paginated_chat_threads = paginator.paginate_queryset(chat_threads, request)
    serializer = ChatThreadSerializer(paginated_chat_threads, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_thread_detail_view(request, openai_thread_id):
    # Assuming you have a function to handle the OpenAI communication
    client = OpenAI(api_key=settings.OPENAI_KEY)
    try:
        messages = client.beta.threads.messages.list(openai_thread_id)
        # Format and return the messages as per your requirement
        print(f'Messages: {messages}')
        chat_history = api_format_chat_history(messages)
        return Response({'chat_history': chat_history})
    except Exception as e:
        return Response({'error': str(e)}, status=400)

def api_format_chat_history(messages):
    formatted_messages = []
    for msg in messages.data:
        formatted_msg = {
            "role": msg.role,
            "content": msg.content[0].text.value,
            "created_at": msg.created_at,
        }
        formatted_messages.append(formatted_msg)
    return formatted_messages

def is_customer(user):
    if user.is_authenticated:
        try:
            user_role = UserRole.objects.get(user=user)
            return user_role.current_role == 'customer'
        except UserRole.DoesNotExist:
            return False
    return False



@login_required
@user_passes_test(is_customer)
def history(request):
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')[:5]  # Limit to 5 recent chats
    data = serializers.serialize('json', chat_threads)
    print(data)
    return JsonResponse({'chat_threads': data})

@login_required
@user_passes_test(is_customer)
def history_page(request):
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'customer_dashboard/history.html', {'chat_threads': chat_threads})

@login_required
@user_passes_test(is_customer)
def thread_detail(request, openai_thread_id):
    client = OpenAI(api_key=settings.OPENAI_KEY)
    try:
        messages = client.beta.threads.messages.list(openai_thread_id)
        chat_history = format_chat_history(messages)
        return render(request, 'customer_dashboard/thread_detail.html', {'chat_history': chat_history})
    except Exception as e:
        # Handle exceptions, possibly showing an error message
        return render(request, 'customer_dashboard/error.html', {'message': str(e)})

def format_chat_history(messages):
    # Format the messages for display. This could be as simple as concatenating them,
    # or you might add formatting to distinguish between user and assistant messages.
    return "\n\n".join([f"{msg.role.upper()}: {msg.content[0].text.value}" for msg in messages.data])

    
def create_openai_prompt(user_id):
    try:
        # Retrieve the user's goal
        user_goal = GoalTracking.objects.get(user_id=user_id).goal_description
    except GoalTracking.DoesNotExist:
        user_goal = "improving my diet"  # A generic goal if the user hasn't set one
    
    # Construct the prompt with the user's goal
    OPENAI_PROMPT = (
        """ Help customers find good food and follow their goals of {goal}.\n\n
        utilize the following functions:\n
        - auth_search_dishes\n
        - auth_search_chefs\n
        - auth_get_meal_plan\n
        - chef_service_areas\n
        - service_area_chefs\n
        - approve_meal_plan\n
        - auth_search_ingredients\n
        - auth_search_meals_excluding_ingredient\n
        - search_meal_ingredients\n
        - suggest_alternative_meals\n
        - add_meal_to_plan\n
        - create_meal_plan\n
        - get_date\n
        - list_upcoming_meals\n
        - remove_meal_from_plan\n
        - replace_meal_in_plan\n
        - post_review\n
        - update_review\n
        - delete_review\n
        - generate_review_summary\n
        - access_past_orders\n
        - get_user_info\n
        - get_goal\n
        - update_goal\n
        - adjust_week_shift\n,
        - api_get_user_info\n
        - api_access_past_orders\n
        - api_adjust_current_week\n
        - api_adjust_week_shift\n

        
        When asked about a meal plan or a dish, the assistant will check the attached file for the caloric information--noting the key is the food name and the value is the calories--and return the caloric information if it is available. If the caloric information is not available  the assistant will politely let the customer know that the information is not available. \n\n"""
    ).format(goal=user_goal)

    return OPENAI_PROMPT



@login_required
@user_passes_test(is_customer)
def api_order_history(request):
    week_shift = get_current_week_shift_context(request)

    current_date = timezone.now()
    start_week = current_date - timedelta(days=current_date.weekday(), weeks=week_shift)
    end_week = start_week + timedelta(days=6)

    orders = Order.objects.filter(
        customer=request.user,
        order_date__range=[start_week, end_week]
    ).order_by('order_date')

    orders_html = render_to_string('customer_dashboard/includes/order_history_rows.html', {'orders': orders})

    return JsonResponse({
        'orders_html': orders_html,
        'previous_week': week_shift - 1,
        'next_week': week_shift + 1,
        'current_week_start': start_week.strftime('%Y-%m-%d'),
        'current_week_end': end_week.strftime('%Y-%m-%d')
    })


@login_required
@user_passes_test(is_customer)
def update_week_shift_context(request, week_shift):
    user = request.user
    user.week_shift = week_shift
    user.save()

@login_required
@user_passes_test(is_customer)
def get_current_week_shift_context(request):
    user = request.user
    return user.week_shift
    
@login_required
@user_passes_test(is_customer)
def update_week_shift(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            week_shift = data.get('week_shift')
            update_week_shift_context(request, week_shift)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

# @login_required
# @user_passes_test(is_customer)
# @require_http_methods(["GET", "POST"])  # Only allow GET and POST requests.
# def api_meal_plan_details(request):
#     # Handle fetching meal plan details
#     if request.method == 'GET':
#         meal_plan_id = request.GET.get('meal_plan_id')
#         meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)
        
#         # Render the meal plan details using a template
#         meal_plan_html = render_to_string('customer_dashboard/includes/meal_plan_details.html', {'meal_plan': meal_plan})
        
#         return JsonResponse({
#             'meal_plan_html': meal_plan_html,
#         })

#     # Handle updating meal plan details
#     elif request.method == 'POST':
#         meal_plan_id = request.POST.get('meal_plan_id')
#         day = request.POST.get('day')
#         new_meal_id = request.POST.get('meal_id')

#         meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, user=request.user)
#         new_meal = get_object_or_404(Meal, id=new_meal_id)
        
#         # TODO: Check if the new meal is available and perform the update 

#         # Perform the update
#         meal_plan_meal = MealPlanMeal.objects.get(id=request.POST.get('meal_plan_meal_id'))
#         meal_plan_meal.meal = new_meal  # Assuming you have already checked the new meal's availability
#         meal_plan_meal.save()

#         # After updating, render the updated meal plan details
#         updated_meal_plan_html = render_to_string('customer_dashboard/includes/meal_plan_details.html', {'meal_plan': meal_plan})
        
#         return JsonResponse({
#             'updated_meal_plan_html': updated_meal_plan_html,
#         })


    
@login_required
@user_passes_test(is_customer)
def meal_plans(request):
    week_shift = get_current_week_shift_context(request)

    current_date = timezone.now()
    start_week = current_date - timedelta(days=current_date.weekday(), weeks=week_shift)
    end_week = start_week + timedelta(days=6)

    meal_plans_qs = MealPlan.objects.filter(
        user=request.user,
        week_start_date__gte=start_week,
        week_end_date__lte=end_week
    )

    meal_plans_data = []

    for meal_plan in meal_plans_qs:
        meal_plan_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan).select_related('meal')
        meals_data = []
        for meal_plan_meal in meal_plan_meals:
            meals_data.append({
                'name': meal_plan_meal.meal.name,
                'description': meal_plan_meal.meal.description,
                'price': meal_plan_meal.meal.price,
                'day': meal_plan_meal.day,
                # Include any other details you want to send to the frontend
            })
        meal_plans_data.append({
            'id': meal_plan.id,
            'week_start_date': meal_plan.week_start_date,
            'week_end_date': meal_plan.week_end_date,
            'meals': meals_data,
        })

    return JsonResponse({
        'meal_plans': meal_plans_data,
        'previous_week': week_shift - 1,
        'next_week': week_shift + 1,
        'current_week_start': start_week.strftime('%Y-%m-%d'),
        'current_week_end': end_week.strftime('%Y-%m-%d')
    }, safe=False)


@login_required
@user_passes_test(is_customer)
def customer_dashboard(request):
    current_date = timezone.now()
    start_week = current_date - timedelta(days=current_date.weekday())
    end_week = start_week + timedelta(days=6)
    goal, created = GoalTracking.objects.get_or_create(user=request.user)

    week_shift = request.GET.get('week_shift', 0)
    try:
        week_shift = int(week_shift)
    except ValueError:
        week_shift = 0

    start_week += timedelta(weeks=week_shift)
    end_week += timedelta(weeks=week_shift)

    orders = Order.objects.filter(
        customer=request.user,
        order_date__range=[start_week, end_week]
    ).order_by('order_date')

    # Handle form submission
    if request.method == 'POST':
        goal_form = GoalForm(request.POST, instance=goal)
        if goal_form.is_valid():
            goal_form.save()
            return redirect('customer_dashboard')  # Use the name you have assigned in urls.py for the dashboard view
    else:
        goal_form = GoalForm(instance=goal)

    context = {
        'goal_form': goal_form,
        'orders': orders,
        'previous_week': week_shift - 1,
        'next_week': week_shift + 1,
        'current_week_start': start_week.date(),
        'current_week_end': end_week.date()
    }

    return render(request, 'customer_dashboard/dashboard.html', context)


@login_required
@user_passes_test(is_customer)
def food_preferences(request):
    food_preferences, created = FoodPreferences.objects.get_or_create(user=request.user)
    form = FoodPreferencesForm(instance=food_preferences)
    return JsonResponse({
        'preferences': form.initial,
        'choices': dict(form.fields['dietary_preference'].choices),
    })


@login_required
@user_passes_test(is_customer)
def update_food_preferences(request):
    if request.method == 'POST':
        food_preferences, created = FoodPreferences.objects.get_or_create(user=request.user)
        form_data = json.loads(request.body)
        form = FoodPreferencesForm(form_data, instance=food_preferences)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Preferences updated successfully'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@user_passes_test(is_customer)
def track_goals(request):
    goals = GoalTracking.objects.filter(user=request.user).values(
        'goal_name', 'goal_description'
    )
    data = list(goals)
    return JsonResponse({'goals': data}, safe=False)


@login_required
@user_passes_test(is_customer)
def update_goal_api(request):
    if request.method == 'POST':
        goal, created = GoalTracking.objects.get_or_create(user=request.user)
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Goal updated successfully'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


functions = {
    "auth_search_dishes": auth_search_dishes,
    "auth_search_chefs": auth_search_chefs,
    "auth_get_meal_plan": auth_get_meal_plan,
    "chef_service_areas": chef_service_areas,
    "service_area_chefs": service_area_chefs,
    "approve_meal_plan": approve_meal_plan,
    "auth_search_ingredients": auth_search_ingredients,
    "search_meal_ingredients": search_meal_ingredients,
    "auth_search_meals_excluding_ingredient": auth_search_meals_excluding_ingredient,
    "suggest_alternative_meals": suggest_alternative_meals,
    "add_meal_to_plan": add_meal_to_plan,
    "create_meal_plan": create_meal_plan,
    "get_date": get_date,
    "list_upcoming_meals": list_upcoming_meals,
    "remove_meal_from_plan": remove_meal_from_plan,
    "replace_meal_in_plan": replace_meal_in_plan,
    "post_review": post_review,
    "update_review": update_review,
    "delete_review": delete_review,
    "generate_review_summary": generate_review_summary,
    "access_past_orders": access_past_orders,
    "get_user_info": get_user_info,
    "get_goal": get_goal,
    "update_goal": update_goal,
    "adjust_week_shift": adjust_week_shift,
}


def ai_call(tool_call, request):
    print(f"Tool call: {tool_call}")
    function = tool_call.function
    print(f"Function: {function}")
    name = function.name
    print(f"Name: {name}")
    arguments = json.loads(function.arguments)
    print(f"Arguments: {arguments}")
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    print(f"Arguments: {arguments}")
    return_value = functions[name](**arguments)
    print(f"Return value: {return_value}")
    tool_outputs = {
        "tool_call_id": tool_call.id,
        "output": return_value,
    }
    return tool_outputs

@api_view(['POST'])
def api_ai_call(request):
    print(f'From api_ai_call: {request.data}')
    tool_call = request.data.get('tool_call')
    print(f'Tool call: {tool_call}')
    user_info = request.data.get('user_info')
    # Add more parameters as needed

    function_name = tool_call.get('function_name')
    print(f"Function: {function_name}")
    arguments = tool_call.get('arguments', {})
    print(f"Arguments: {arguments}")
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    arguments['user_info'] = user_info
    print(f"Arguments: {arguments}")
    return_value = functions[function_name](**arguments)
    print(f"Return value: {return_value}")
    tool_outputs = {
        "tool_call_id": tool_call.get('id'),
        "output": return_value,
    }
    # Example response
    return Response({
        "status": "success",
        "data": tool_outputs,
    })

# @login_required
# @user_passes_test(is_customer)

@api_view(['POST'])
def chat_with_gpt(request):
    print("Chatting with GPT")
    assistant_id_file = "assistant_id.txt"
    ingredients_id_file = "ingredients_current_file_id.txt"
    # Set up OpenAI
    client = OpenAI(api_key=settings.OPENAI_KEY)    
    # Check if the assistant ID is already stored in a file

    user = CustomUser.objects.get(id=request.data.get('user_id'))

    if os.path.exists(ingredients_id_file):
        with open(ingredients_id_file, 'r') as f:
            file_id = f.read().strip()
            print(f"File ID: {file_id}")
            
    if os.path.exists(assistant_id_file):
        with open(assistant_id_file, 'r') as f:
            assistant_id = f.read().strip()
            print(f"Assistant ID: {assistant_id}")
        # assistant = client.beta.assistants.update(
        #     name="Food Expert",
        #     assistant_id=assistant_id,
        #     instructions=create_openai_prompt(request.user.id),
        #     # model="gpt-3.5-turbo-1106",
        #     model="gpt-4-1106-preview",
        #     tools=[ 
        #         {"type": "code_interpreter",},
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "auth_search_dishes",
        #                 "description": "Search dishes in the database",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for dishes",
        #                         },
        #                     },
        #                     "required": ["query"],
        #                 },
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "auth_search_chefs",
        #                 "description": "Search chefs in the database and get their info",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for chefs",
        #                         },
        #                     },
        #                     "required": ["query"],
        #                 },
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "auth_get_meal_plan",
        #                 "description": "Get a meal plan for the current week or a future week based on the user's week_shift. This function depends on the request object to access the authenticated user and their week_shift attribute.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "create_meal_plan",
        #                 "description": "Create a new meal plan for the user.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "chef_service_areas",
        #                 "description": "Retrieve service areas for a specified chef based on their name or identifier.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for a chef's service areas, typically using the chef's name or identifier."
        #                         }
        #                     },
        #                     "required": ["query"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "service_area_chefs",
        #                 "description": "Search for chefs serving a specific postal code area.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to find chefs serving a particular postal code."
        #                         }
        #                     },
        #                     "required": ["query"]
        #                 }
        #             }
        #         },  
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "approve_meal_plan",
        #                 "description": "Approve the meal plan and proceed to payment",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "meal_plan_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the meal plan to approve"
        #                         }
        #                     },
        #                     "required": ["meal_plan_id"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "auth_search_ingredients",
        #                 "description": "Search for ingredients in the database",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for ingredients",
        #                         },
        #                     },
        #                     "required": ["query"],
        #                 },
        #             }
        #         }, 
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "auth_search_meals_excluding_ingredient",
        #                 "description": "Search the database for meals that are excluding an ingredient",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for meals that exclude the ingredient",
        #                         },
        #                     },
        #                     "required": ["query"],
        #                 },
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "search_meal_ingredients",
        #                 "description": "Search the database for the ingredients of a meal",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "query": {
        #                             "type": "string",
        #                             "description": "The query to search for a meal's ingredients",
        #                         },
        #                     },
        #                     "required": ["query"],
        #                 },
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "suggest_alternative_meals",
        #                 "description": "Suggest alternative meals based on a list of meal IDs and corresponding days of the week. Each meal ID will have a corresponding day to find alternatives.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "meal_ids": {
        #                             "type": "array",
        #                             "items": {
        #                                 "type": "integer",
        #                                 "description": "A unique identifier for a meal."
        #                             },
        #                             "description": "List of meal IDs to exclude from suggestions."
        #                         },
        #                         "days_of_week": {
        #                             "type": "array",
        #                             "items": {
        #                                 "type": "string",
        #                                 "description": "The day of the week for a meal, e.g., 'Monday', 'Tuesday', etc."
        #                             },
        #                             "description": "List of days of the week corresponding to each meal ID."
        #                         }
        #                     },
        #                     "required": ["meal_ids", "days_of_week"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "add_meal_to_plan",
        #                 "description": "Add a meal to a specified day in the meal plan",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "meal_plan_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal plan"
        #                         },
        #                         "meal_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal to add"
        #                         },
        #                         "day": {
        #                             "type": "string",
        #                             "description": "The day to add the meal to"
        #                         }
        #                     },
        #                     "required": ["meal_plan_id", "meal_id", "day"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "get_date",
        #                 "description": "Get the current date and time. This function returns the current date and time in a user-friendly format, taking into account the server's time zone.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "list_upcoming_meals",
        #                 "description": "Lists upcoming meals for the current week, filtered by user's dietary preference and postal code. The meals are adjusted based on the user's week_shift to plan for future meals.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "remove_meal_from_plan",
        #                 "description": "Remove a meal from a specified day in the meal plan",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "meal_plan_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal plan"
        #                         },
        #                         "meal_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal to remove"
        #                         },
        #                         "day": {
        #                             "type": "string",
        #                             "description": "The day to remove the meal from"
        #                         }
        #                     },
        #                     "required": ["meal_plan_id", "meal_id", "day"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "replace_meal_in_plan",
        #                 "description": "Replace a meal with another meal on a specified day in the meal plan",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "meal_plan_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal plan"
        #                         },
        #                         "old_meal_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the meal to be replaced"
        #                         },
        #                         "new_meal_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the new meal"
        #                         },
        #                         "day": {
        #                             "type": "string",
        #                             "description": "The day to replace the meal on"
        #                         }
        #                     },
        #                     "required": ["meal_plan_id", "old_meal_id", "new_meal_id", "day"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "post_review",
        #                 "description": "Post a review for a meal or a chef.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the user posting the review."
        #                         },
        #                         "content": {
        #                             "type": "string",
        #                             "description": "The content of the review. Must be between 10 and 1000 characters."
        #                         },
        #                         "rating": {
        #                             "type": "integer",
        #                             "description": "The rating given in the review, from 1 (Poor) to 5 (Excellent)."
        #                         },
        #                         "item_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the item (meal or chef) being reviewed."
        #                         },
        #                         "item_type": {
        #                             "type": "string",
        #                             "enum": ["meal", "chef"],
        #                             "description": "The type of item being reviewed."
        #                         }
        #                     },
        #                     "required": ["user_id", "content", "rating", "item_id", "item_type"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "update_review",
        #                 "description": "Update an existing review.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "review_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the review to be updated."
        #                         },
        #                         "updated_content": {
        #                             "type": "string",
        #                             "description": "The updated content of the review. Must be between 10 and 1000 characters."
        #                         },
        #                         "updated_rating": {
        #                             "type": "integer",
        #                             "description": "The updated rating, from 1 (Poor) to 5 (Excellent)."
        #                         }
        #                     },
        #                     "required": ["review_id", "updated_content", "updated_rating"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "delete_review",
        #                 "description": "Delete a review.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "review_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the review to be deleted."
        #                         }
        #                     },
        #                     "required": ["review_id"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "generate_review_summary",
        #                 "description": "Generate a summary of all reviews for a specific object (meal or chef) using AI model.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "object_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the object (meal or chef) to summarize reviews for."
        #                         },
        #                         "category": {
        #                             "type": "string",
        #                             "enum": ["meal", "chef"],
        #                             "description": "The category of the object being reviewed."
        #                         }
        #                     },
        #                     "required": ["object_id", "category"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "access_past_orders",
        #                 "description": "Retrieve past orders for a user, optionally filtered by specific criteria.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the user whose past orders are being accessed."
        #                         },
        #                     },
        #                     "required": ["user_id"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "get_user_info",
        #                 "description": "Retrieve essential information about the user such as user ID, dietary preference, week shift, and postal code.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "get_goal",
        #                 "description": "Retrieve the user's goal to aide in making smart dietary decisions and offering advise.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {},
        #                     "required": []
        #                 }
        #             }    
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "update_goal",
        #                 "description": "Update the user's goal to aide in making smart dietary decisions and offering advise.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "goal_name": {
        #                             "type": "string",
        #                             "description": "The name of the goal."
        #                         },
        #                         "goal_description": {
        #                             "type": "string",
        #                             "description": "The description of the goal."
        #                         }
        #                     },
        #                     "required": ["goal_name", "goal_description"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "adjust_week_shift",
        #                 "description": "Adjust the week shift forward for meal planning, allowing users to plan for future meals. This function will not allow shifting to previous weeks. To be transparent, always let the user know the week they are working with at the start of the conversation, and asking them if they would like to work on this week's plan--changing the week shit to 0 if so.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "week_shift_increment": {
        #                             "type": "integer",
        #                             "description": "The number of weeks to shift forward. Must be a positive integer."
        #                         }
        #                     },
        #                     "required": ["week_shift_increment"]
        #                 }
        #             }
        #         },
        #     ],
        # )        


    else:
        print("Creating a new assistant")
        # Create an Assistant
        assistant = client.beta.assistants.create(
            name="Food Expert",
            instructions=create_openai_prompt(user.id),
            # model="gpt-3.5-turbo-1106",
            model="gpt-4-1106-preview",
            tools=[ 
                {"type": "code_interpreter",},
                {
                    "type": "function",
                    "function": {
                        "name": "auth_search_dishes",
                        "description": "Search dishes in the database",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for dishes",
                                },
                            },
                            "required": ["query"],
                        },
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "auth_search_chefs",
                        "description": "Search chefs in the database and get their info",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for chefs",
                                },
                            },
                            "required": ["query"],
                        },
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "auth_get_meal_plan",
                        "description": "Get a meal plan for the current week or a future week based on the user's week_shift. This function depends on the request object to access the authenticated user and their week_shift attribute.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_meal_plan",
                        "description": "Create a new meal plan for the user.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "chef_service_areas",
                        "description": "Retrieve service areas for a specified chef based on their name or identifier.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for a chef's service areas, typically using the chef's name or identifier."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "service_area_chefs",
                        "description": "Search for chefs serving a specific postal code area.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to find chefs serving a particular postal code."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                },  
                {
                    "type": "function",
                    "function": {
                        "name": "approve_meal_plan",
                        "description": "Approve the meal plan and proceed to payment",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_plan_id": {
                                    "type": "integer",
                                    "description": "The ID of the meal plan to approve"
                                }
                            },
                            "required": ["meal_plan_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "auth_search_ingredients",
                        "description": "Search for ingredients in the database",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for ingredients",
                                },
                            },
                            "required": ["query"],
                        },
                    }
                }, 
                {
                    "type": "function",
                    "function": {
                        "name": "auth_search_meals_excluding_ingredient",
                        "description": "Search the database for meals that are excluding an ingredient",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for meals that exclude the ingredient",
                                },
                            },
                            "required": ["query"],
                        },
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "search_meal_ingredients",
                        "description": "Search the database for the ingredients of a meal",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The query to search for a meal's ingredients",
                                },
                            },
                            "required": ["query"],
                        },
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "suggest_alternative_meals",
                        "description": "Suggest alternative meals based on a list of meal IDs and corresponding days of the week. Each meal ID will have a corresponding day to find alternatives.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_ids": {
                                    "type": "array",
                                    "items": {
                                        "type": "integer",
                                        "description": "A unique identifier for a meal."
                                    },
                                    "description": "List of meal IDs to exclude from suggestions."
                                },
                                "days_of_week": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "description": "The day of the week for a meal, e.g., 'Monday', 'Tuesday', etc."
                                    },
                                    "description": "List of days of the week corresponding to each meal ID."
                                }
                            },
                            "required": ["meal_ids", "days_of_week"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "add_meal_to_plan",
                        "description": "Add a meal to a specified day in the meal plan",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_plan_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal plan"
                                },
                                "meal_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal to add"
                                },
                                "day": {
                                    "type": "string",
                                    "description": "The day to add the meal to"
                                }
                            },
                            "required": ["meal_plan_id", "meal_id", "day"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_date",
                        "description": "Get the current date and time. This function returns the current date and time in a user-friendly format, taking into account the server's time zone.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "list_upcoming_meals",
                        "description": "Lists upcoming meals for the current week, filtered by user's dietary preference and postal code. The meals are adjusted based on the user's week_shift to plan for future meals.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "remove_meal_from_plan",
                        "description": "Remove a meal from a specified day in the meal plan",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_plan_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal plan"
                                },
                                "meal_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal to remove"
                                },
                                "day": {
                                    "type": "string",
                                    "description": "The day to remove the meal from"
                                }
                            },
                            "required": ["meal_plan_id", "meal_id", "day"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "replace_meal_in_plan",
                        "description": "Replace a meal with another meal on a specified day in the meal plan",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_plan_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal plan"
                                },
                                "old_meal_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal to be replaced"
                                },
                                "new_meal_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the new meal"
                                },
                                "day": {
                                    "type": "string",
                                    "description": "The day to replace the meal on"
                                }
                            },
                            "required": ["meal_plan_id", "old_meal_id", "new_meal_id", "day"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "post_review",
                        "description": "Post a review for a meal or a chef.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "integer",
                                    "description": "The ID of the user posting the review."
                                },
                                "content": {
                                    "type": "string",
                                    "description": "The content of the review. Must be between 10 and 1000 characters."
                                },
                                "rating": {
                                    "type": "integer",
                                    "description": "The rating given in the review, from 1 (Poor) to 5 (Excellent)."
                                },
                                "item_id": {
                                    "type": "integer",
                                    "description": "The ID of the item (meal or chef) being reviewed."
                                },
                                "item_type": {
                                    "type": "string",
                                    "enum": ["meal", "chef"],
                                    "description": "The type of item being reviewed."
                                }
                            },
                            "required": ["user_id", "content", "rating", "item_id", "item_type"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "update_review",
                        "description": "Update an existing review.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "review_id": {
                                    "type": "integer",
                                    "description": "The ID of the review to be updated."
                                },
                                "updated_content": {
                                    "type": "string",
                                    "description": "The updated content of the review. Must be between 10 and 1000 characters."
                                },
                                "updated_rating": {
                                    "type": "integer",
                                    "description": "The updated rating, from 1 (Poor) to 5 (Excellent)."
                                }
                            },
                            "required": ["review_id", "updated_content", "updated_rating"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_review",
                        "description": "Delete a review.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "review_id": {
                                    "type": "integer",
                                    "description": "The ID of the review to be deleted."
                                }
                            },
                            "required": ["review_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "generate_review_summary",
                        "description": "Generate a summary of all reviews for a specific object (meal or chef) using AI model.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "object_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the object (meal or chef) to summarize reviews for."
                                },
                                "category": {
                                    "type": "string",
                                    "enum": ["meal", "chef"],
                                    "description": "The category of the object being reviewed."
                                }
                            },
                            "required": ["object_id", "category"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "access_past_orders",
                        "description": "Retrieve past orders for a user, optionally filtered by specific criteria.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "integer",
                                    "description": "The ID of the user whose past orders are being accessed."
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["Placed", "In Progress", "Completed", "Cancelled", "Refunded", "Delayed"],
                                    "description": "The status of the orders to retrieve."
                                },
                                "delivery_method": {
                                    "type": "string",
                                    "enum": ["Pickup", "Delivery"],
                                    "description": "The delivery method of the orders to retrieve."
                                }
                            },
                            "required": ["user_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_user_info",
                        "description": "Retrieve essential information about the user such as user ID, dietary preference, week shift, and postal code.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_goal",
                        "description": "Retrieve the user's goal to aide in making smart dietary decisions and offering advise.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }    
                },
                {
                    "type": "function",
                    "function": {
                        "name": "update_goal",
                        "description": "Update the user's goal to aide in making smart dietary decisions and offering advise.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "goal_name": {
                                    "type": "string",
                                    "description": "The name of the goal."
                                },
                                "goal_description": {
                                    "type": "string",
                                    "description": "The description of the goal."
                                }
                            },
                            "required": ["goal_name", "goal_description"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "adjust_week_shift",
                        "description": "Adjust the week shift forward for meal planning, allowing users to plan for future meals. This function will not allow shifting to previous weeks. To be transparent, always let the user know the week they are working with at the start of the conversation, and asking them if they would like to work on this week's plan--changing the week shit to 0 if so.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "week_shift_increment": {
                                    "type": "integer",
                                    "description": "The number of weeks to shift forward. Must be a positive integer."
                                }
                            },
                            "required": ["week_shift_increment"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_get_user_info",
                        "description": "Retrieve detailed information about the current user.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_access_past_orders",
                        "description": "Access past orders of the current user.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_adjust_current_week",
                        "description": "Reset the user's week shift to the current week.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_adjust_week_shift",
                        "description": "Adjust the user's week shift for meal planning.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "week_shift_increment": {
                                    "type": "integer",
                                    "description": "The number of weeks to shift forward. Must be a positive integer."
                                }
                            },
                            "required": ["week_shift_increment"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_update_goal",
                        "description": "Update the user's dietary goal.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "goal_name": {
                                    "type": "string",
                                    "description": "The name of the goal."
                                },
                                "goal_description": {
                                    "type": "string",
                                    "description": "The description of the goal."
                                }
                            },
                            "required": ["goal_name", "goal_description"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "api_get_goal",
                        "description": "Retrieve the current dietary goal of the user.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
            ],
        )        
        assistant_id = assistant.id
        # Store the assistant ID in a file
        with open(assistant_id_file, 'w') as f:
            f.write(assistant_id)
        
    # Processing the POST request
    try:
        print("Processing POST request")
        try:
            print(f"Request data: {request.data}")
            data = request.data
            print(f"Data: {data}")
        except json.JSONDecodeError:
            return Response({'error': 'Failed to parse JSON'}, status=400)

        question = data.get('question')
        print(f"Question: {question}")
        thread_id = data.get('thread_id')
        print(f"Thread ID: {thread_id}")

        if not question:
            return Response({'error': 'No question provided'}, status=400)
        
        # Check if thread_id is safe
        if thread_id and not re.match("^thread_[a-zA-Z0-9]*$", thread_id):
            return Response({'error': 'Invalid thread_id'}, status=400)

        # Handle existing or new thread
        if thread_id:
            # Check if thread_id exists in the database
            if not ChatThread.objects.filter(openai_thread_id=thread_id).exists():
                return Response({'error': 'Thread_id does not exist'}, status=400)

            ChatThread.objects.filter(user=user).update(is_active=False)
            ChatThread.objects.filter(openai_thread_id=thread_id).update(is_active=True)
        else:
            openai_thread = client.beta.threads.create()
            thread_id = openai_thread.id
            print(f"New thread ID: {thread_id}")
            ChatThread.objects.create(
                user=user,
                openai_thread_id=thread_id,
                title=question,
                is_active=True
            )

        
        try:
            print("Creating a message")
            # Add a Message to a Thread
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=question
            )
            print("Message created")
        except Exception as e:
            return Response({'error': f'Failed to create message: {str(e)}'}, status=500)    
                

    
        # Variable to store tool call results
        formatted_outputs = []
            
        try:
            # Run the Assistant
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                # Optionally, you can add specific instructions here
            )
        except Exception as e:
            return Response({'error': f'Failed to create run: {str(e)}'}, status=500)

        # Check the status of the Run and retrieve responses
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )
            if run.status == 'completed':
                print('Run completed')
                break
            elif run.status == 'failed':
                print('Run failed')
                break
            elif run.status in ['expired', 'cancelled']:
                print(f'Run {run.status}')
                break
            elif run.status in ['failed', 'queued', 'in_progress']:
                time.sleep(0.5)
                continue
            elif run.status == "requires_action":
                tool_outputs = []
                print("Run requires action")
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    # Execute the function call and get the result
                    tool_call_result = ai_call(tool_call, request)
                    
                    # Extracting the tool_call_id and the output
                    tool_call_id = tool_call_result['tool_call_id']
                    output = tool_call_result['output']
                    
                    # Assuming 'output' needs to be serialized as a JSON string
                    # If it's already a string or another format is required, adjust this line accordingly
                    output_json = json.dumps(output)

                    # Prepare the output in the required format
                    formatted_output = {
                        "tool_call_id": tool_call_id,
                        "output": output_json
                    }
                    # print(f"Formatted tool output: {formatted_output}")
                    tool_outputs.append(formatted_output)

                    formatted_outputs.append(formatted_output)
                    
                # Submitting the formatted outputs
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
                continue


        try:
            # Retrieve messages and log them
            messages = client.beta.threads.messages.list(thread_id)
        except Exception as e:
            return Response({'error': f'Failed to list messages: {str(e)}'}, status=500)


        with open("messages.json", "w") as f:
            messages_json = messages.model_dump()
            json.dump(messages_json, f, indent=4)
            

        try:
            # Retrieve the run steps
            run_steps = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run.id)
        except Exception as e:
            return Response({'error': f'Failed to list run steps: {str(e)}'}, status=500)

        # Save the run steps to a file
        with open("run_steps.json", "w") as f:
            run_steps_json = run_steps.model_dump()
            json.dump(run.model_dump(), f, indent=4)
        


        response_data = {
            'last_assistant_message': next((msg.content[0].text.value for msg in (messages.data) if msg.role == 'assistant'), None),                
            'run_status': run.status,
            'new_thread_id': thread_id
        }

        print(thread_id)
        print(f'New thread ID: {thread_id}')

        print(f'message: {response_data["last_assistant_message"]}')
        
        # Wrap response_data in a Response object
        return Response(response_data)

    except Exception as e:
        # Return error message wrapped in Response
        return Response({'error': str(e)}, status=500)
