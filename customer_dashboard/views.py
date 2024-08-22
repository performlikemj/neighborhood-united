from uuid import uuid4
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from meals.models import Order, Dish, Meal, Cart, MealPlanMeal, MealPlan, Meal
from meals.tasks import generate_user_summary
from custom_auth.models import CustomUser, UserRole
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import GoalTracking, ChatThread, UserHealthMetrics, CalorieIntake, UserMessage, UserSummary, ToolCall
from .forms import GoalForm
import openai
from openai import NotFoundError, OpenAI, OpenAIError
import pytz
import json
import os
import re
import time

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
                          understand_dietary_choices, is_question_relevant, create_meal, generate_summary_title, 
                          analyze_nutritional_content, replace_meal_based_on_preferences)
from local_chefs.views import chef_service_areas, service_area_chefs
from django.core import serializers
from .serializers import ChatThreadSerializer, GoalTrackingSerializer, UserHealthMetricsSerializer, CalorieIntakeSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .permissions import IsCustomer
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
import datetime
from asgiref.sync import async_to_sync
from hood_united.consumers import ToolCallConsumer
import asyncio
import logging
import threading
from django.views import View
import traceback
from django.conf import settings
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

# Use logger as needed
# example: logger.warning("This is a warning message")

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_recommend_follow_up(request):
    user_id = request.user.id
    user = get_object_or_404(CustomUser, id=user_id)

    # Step 1: Retrieve the most recent active chat thread for the user
    try:
        print(f'Recommend follow-up for user: {user}')
        chat_thread = ChatThread.objects.filter(user=user, is_active=True).latest('created_at')
    except ChatThread.DoesNotExist:
        return Response({'error': 'No active chat thread found.'}, status=404)

    # Step 2: Fetch the chat history using the openai_thread_id
    try:
        client = OpenAI(api_key=settings.OPENAI_KEY)
        messages = client.beta.threads.messages.list(chat_thread.openai_thread_id)
        chat_history = api_format_chat_history(messages)
    except Exception as e:
        return Response({'error': f'Failed to fetch chat history: {str(e)}'}, status=400)

    # Step 3: Generate the context string from the chat history
    context = '\n'.join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

    # Step 4: Call the recommend_follow_up function to get follow-up prompts
    try:
        follow_up_recommendations = recommend_follow_up(request, context)
    except Exception as e:
        logger.error(f"Error generating follow-up recommendations: {e}")
        return Response({'error': f'Failed to generate follow-up recommendations'})

    # Step 5: Return the recommendations in the expected format
    return Response(follow_up_recommendations)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_summary(request):
    user_id = request.user.id  # Use request.user.id to get the authenticated user's ID
    user = get_object_or_404(CustomUser, id=user_id)


    # Check if the user has an existing summary
    try:
        user_summary_obj = UserSummary.objects.get(user=user)
        user_summary = user_summary_obj.summary
    except UserSummary.DoesNotExist:
        user_summary = "No summary available."

    # Provide a fallback template if the user has no summary data
    if user_summary.strip() == "No summary available.":
        fallback_template = "Create a meal plan for the week including breakfast, lunch, and dinner for a {person/family of 3, etc.}, {that want to lower their sugar intake/that want to eat healthy while saving money}. {The meals should also take into account that one of us fasts breakfast and starts eating at 11am}."
        recommend_prompt = fallback_template
    else:
        # Generate a recommended prompt based on the user's summary and context
        recommend_prompt = recommend_follow_up(request, user_summary)

    # Generate or update the user summary
    generate_user_summary(user_id)
    
    # Fetch the updated summary
    user_summary = UserSummary.objects.get(user=user)
    
    data = {
        "data": [
            {
                "content": [
                    {
                        "text": {
                            "annotations": [],
                            "value": user_summary.summary
                        },
                        "type": "text"
                    }
                ],
                "created_at": int(user_summary.updated_at.timestamp()),
                "role": "assistant",
            },
        ],
        "recommend_prompt": recommend_prompt
    }
    return Response(data)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_update_calorie_intake(request):
    try:
        record_id = request.data.record_id
        calorie_record = CalorieIntake.objects.get(id=record_id, user=request.user)
        serializer = CalorieIntakeSerializer(calorie_record, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)
    except CalorieIntake.DoesNotExist:
        return Response({"error": "Record not found."}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_get_calories(request):
    try:
        print("Getting calories")
        user = CustomUser.objects.get(id=request.data.get('user_id'))
        date_recorded = request.data.get('date')
        # Using request.user.id to get the authenticated user's ID
        calorie_records = CalorieIntake.objects.filter(user=user)
        if date_recorded:
            print("date was recorded")
            calorie_records = calorie_records.filter(date_recorded=date_recorded)
        serializer = CalorieIntakeSerializer(calorie_records, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({"error": str(e)}, status=400)
    

@api_view(['POST'])  # This should only be a POST request
@permission_classes([IsAuthenticated, IsCustomer])
def api_add_calorie_intake(request):
    try:
        data = request.data.copy()  # Make a mutable copy of the data
        data['user'] = request.user.id  # Add the user ID to the data
        serializer = CalorieIntakeSerializer(data=data)  # Pass the data to the serializer
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    except Exception as e:
        print(f"Exception in api_add_calorie_intake: {e}")
        print(traceback.format_exc())
        return Response({"error": str(e)}, status=400)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_delete_calorie_intake(request, record_id):
    try:
        calorie_record = CalorieIntake.objects.get(id=record_id, user=request.user)
        calorie_record.delete()
        return Response({"message": "Calorie intake record deleted successfully."}, status=200)
    except CalorieIntake.DoesNotExist:
        return Response({"error": "Record not found."}, status=404)
    except Exception as e:
        print(f"Exception in api_delete_calorie_intake: {e}")
        print(traceback.format_exc())
        return Response({"error": str(e)}, status=400)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_metrics(request):
    user = request.user

    if request.method == 'GET':
        user_metrics = UserHealthMetrics.objects.filter(user=user).order_by('-date_recorded')[:5]
        serializer = UserHealthMetricsSerializer(user_metrics, many=True)
        current_week_metrics = any(metric.is_current_week() for metric in user_metrics)
        if not current_week_metrics:
            return Response({"message": "Please update your health metrics for the current week."}, status=200)
        return Response(serializer.data)

    elif request.method == 'POST':
        date_recorded = request.data.pop('date_recorded', None)
        if date_recorded:
            date_recorded = datetime.datetime.strptime(date_recorded, '%Y-%m-%d').date()  # convert string to date

        # Remove 'id' from request.data
        request.data.pop('id', None)

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
        - get_unupdated_health_metrics\n
        - update_health_metrics\n
        - check_allergy_alert\n
        - provide_nutrition_advice\n
        - find_nearby_supermarkets\n
        - search_healthy_meal_options\n
        - provide_healthy_meal_suggestions\n
       \n\n"""
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

guest_functions = {
    "guest_search_dishes": guest_search_dishes,
    "guest_search_chefs": guest_search_chefs,
    "guest_get_meal_plan": guest_get_meal_plan,
    "guest_search_ingredients": guest_search_ingredients,
    "chef_service_areas": chef_service_areas,
}

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
    "get_unupdated_health_metrics": get_unupdated_health_metrics,
    "update_health_metrics": update_health_metrics,
    "check_allergy_alert": check_allergy_alert,
    "provide_nutrition_advice": provide_nutrition_advice,
    "find_nearby_supermarkets": find_nearby_supermarkets,
    "search_healthy_meal_options": search_healthy_meal_options,
    "provide_healthy_meal_suggestions": provide_healthy_meal_suggestions,
    "understand_dietary_choices": understand_dietary_choices,
    "create_meal": create_meal,
    "analyze_nutritional_content": analyze_nutritional_content,
    "replace_meal_based_on_preferences": replace_meal_based_on_preferences,
    
}

def ai_call(tool_call, request):
    function = tool_call.function
    name = function.name
    arguments = json.loads(function.arguments)
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    return_value = functions[name](**arguments)
    tool_outputs = {
        "tool_call_id": tool_call.id,
        "output": return_value,
        "function": name,
    }
    return tool_outputs

def guest_ai_call(tool_call, request):
    function = tool_call.function
    name = function.name
    arguments = json.loads(function.arguments)
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    return_value = guest_functions[name](**arguments)
    tool_outputs = {
        "tool_call_id": tool_call.id,
        "output": return_value,
        "function": name,
    }
    return tool_outputs


@api_view(['POST'])
def guest_chat_with_gpt(request):
    print("Chatting with Guest GPT")
    guest_assistant_id_file = "guest_assistant_id.txt"
    # Set up OpenAI
    client = OpenAI(api_key=settings.OPENAI_KEY)    
    # Check if the assistant ID is already stored in a file
  
    if os.path.exists(guest_assistant_id_file):
        with open(guest_assistant_id_file, 'r') as f:
            guest_assistant_id = f.read().strip()


    else:
        print("Creating a new assistant")
        # Create an Assistant
        assistant = client.beta.assistants.create(
            name="Guest Food Expert",
            instructions='You help guests understand the functionality of the app and help them find good food, chefs, and ingredients.',
            model="gpt-4-1106-preview",
            tools=[ 
                {"type": "code_interpreter"},
                {
                    "type": "function",
                    "function": {
                        "name": "guest_search_dishes",
                        "description": "Search dishes in the database",
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
                        "name": "guest_search_chefs",
                        "description": "Search chefs in the database and get their info",
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
                        "name": "guest_get_meal_plan",
                        "description": "Get a meal plan for the current week",
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
                        "name": "guest_search_ingredients",
                        "description": "Search ingredients used in dishes in the database and get their info.",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                },
            ]
        )      
        guest_assistant_id = assistant.id
        # Store the assistant ID in a file
        with open(guest_assistant_id_file, 'w') as f:
            f.write(guest_assistant_id)

    try:
        print("Processing POST request")
        data = request.data
        print(f"Data: {data}")

        question = data.get('question')
        thread_id = data.get('thread_id')

        if not question:
            return Response({'error': 'No question provided'}, status=400)


        relevant = is_question_relevant(question)

        if thread_id and not re.match("^thread_[a-zA-Z0-9]*$", thread_id):
            return Response({'error': 'Invalid thread_id'}, status=400)

        if not thread_id:
            openai_thread = client.beta.threads.create()
            thread_id = openai_thread.id

        if relevant:
            try:
                client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=question
                )
            except OpenAIError as e:
                print(f'Error: {e}')
                if 'Can\'t add messages to thread' in str(e) and 'while a run' in str(e) and 'is active' in str(e):
                    # Extract the run ID from the error message
                    match = re.search(r'run (\w+)', str(e))
                    if match:
                        run_id = match.group(1)
                        # Cancel the active run
                        client.beta.threads.runs.cancel(run_id, thread_id=thread_id)
                        # Try to create the message again
                        client.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=question
                        )
                else:
                    logger.error(f'Failed to create message: {str(e)}')
                    return  # Stopping the task if message creation fails
            response_data = {
                'new_thread_id': thread_id,
                'recommend_follow_up': False,
            }
            return Response(response_data)
        else:
            response_data = {
                'last_assistant_message': "I'm sorry, I cannot help with that.",
                'new_thread_id': thread_id,
                'recommend_follow_up': False,
            }
            return Response(response_data)

    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return Response({'error': str(e)}, status=500)


# @login_required
# @user_passes_test(is_customer)
@api_view(['POST'])
def chat_with_gpt(request):
    print("Chatting with GPT")
    assistant_id_file = "assistant_id.txt"
    # Set up OpenAI
    client = OpenAI(api_key=settings.OPENAI_KEY)    
    # Check if the assistant ID is already stored in a file

    user = CustomUser.objects.get(id=request.data.get('user_id'))
            
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
        #                     "properties": {},
        #                     "required": []
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
        #                     "properties": {},
        #                     "required": []
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
        #                     "properties": {},
        #                     "required": []
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
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "get_unupdated_health_metrics",
        #                 "description": "Get the health metrics that have not been updated in the last week for a specific user",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the user to get the unupdated health metrics for"
        #                         },
        #                     },
        #                     "required": ["user_id"],
        #                 },
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "check_allergy_alert",
        #                 "description": "Check for potential allergens in a meal by checking the user's list of allergies against the meal or dish and informing the user if there are possible allergens to be concerned about.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The unique identifier of the user."
        #                         }
        #                     },
        #                     "required": ["user_id"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "track_calorie_intake",
        #                 "description": "Track and log the user's daily calorie intake.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the user logging the intake."
        #                         },
        #                         "meal_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the meal consumed."
        #                         },
        #                         "portion_size": {
        #                             "type": "string",
        #                             "description": "The portion size of the meal consumed."
        #                         }
        #                     },
        #                     "required": ["user_id", "meal_id", "portion_size"]
        #                 }
        #             }
        #         },
        #         {
        #             "type": "function",
        #             "function": {
        #                 "name": "provide_nutrition_advice",
        #                 "description": "Offer personalized nutrition advice based on user's dietary preferences and health goals.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "user_id": {
        #                             "type": "integer",
        #                             "description": "The ID of the user seeking advice."
        #                         }
        #                     },
        #                     "required": ["user_id"]
        #                 }
        #             }
        #         },
        #         {
        #         "type": "function",
        #         "function": {
        #             "name": "find_nearby_supermarkets",
        #             "description": "Find nearby supermarkets based on the user's postal code.",
        #             "parameters": {
        #                 "type": "object",
        #                 "properties": {
        #                     "postal_code": {
        #                         "type": "string",
        #                         "description": "The postal code to find nearby supermarkets."
        #                     }
        #                 },
        #                 "required": ["postal_code"]
        #             }
        #         }
        #     },
        #     {
        #         "type": "function",
        #         "function": {
        #             "name": "search_healthy_meal_options",
        #             "description": "Search for healthy meal options at a specified supermarket location.",
        #             "parameters": {
        #                 "type": "object",
        #                 "properties": {
        #                     "location_id": {
        #                         "type": "string",
        #                         "description": "The unique identifier of the supermarket location."
        #                     },
        #                     "search_term": {
        #                         "type": "string",
        #                         "description": "The search term to find healthy meal options (e.g., 'gluten-free', 'organic vegetables')."
        #                     },
        #                     "limit": {
        #                         "type": "integer",
        #                         "description": "The number of products to retrieve in the search."
        #                     }
        #                 },
        #                 "required": ["search_term", "location_id"]
        #             }
        #         }
        #     },
        #     {
        #         "type": "function",
        #         "function": {
        #             "name": "provide_healthy_meal_suggestions",
        #             "description": "If requested or no meals are available, provide healthy meal suggestions based on the user's dietary preferences and health goals filtered by days of the week. If the user is in a location where a supermarket is available, provide healthy meal suggestions based on what is available at the supermarket.",
        #             "parameters": {
        #                 "type": "object",
        #                 "properties": {
        #                     "user_id": {
        #                         "type": "integer",
        #                         "description": "The ID of the user seeking meal suggestions."
        #                     }
        #                 },
        #                 "required": ["user_id"]
        #             }
        #         }
        #     },
        #     {
        #         "type": "function",
        #         "function": {
        #             "name": "understand_dietary_choices",
        #             "description": "Understand the available dietary choices that all users have access to. Use this to create more precise queries.",
        #             "parameters": {
        #                 "type": "object",
        #                 "properties": {},
        #                 "required": []
        #             }
        #         }
        #     },
        # ],
        # )        


    else:
        print("Creating a new assistant")
        # Create an Assistant
        assistant = client.beta.assistants.create(
            name="Food Expert",
            instructions=create_openai_prompt(user.id),
            # model="gpt-3.5-turbo-1106",
            model="gpt-4o",
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
                            "properties": {},
                            "required": []
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
                        "name": "update_health_metrics",
                        "description": "Update the health metrics for a user including weight, BMI, mood, and energy level.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the user."
                                },
                                "weight": {
                                    "type": "number",
                                    "description": "The updated weight of the user."
                                },
                                "bmi": {
                                    "type": "number",
                                    "description": "The updated Body Mass Index (BMI) of the user."
                                },
                                "mood": {
                                    "type": "string",
                                    "description": "The updated mood of the user."
                                },
                                "energy_level": {
                                    "type": "number",
                                    "description": "The updated energy level of the user."
                                }
                            },
                            "required": ["user_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_nutritional_content",
                        "description": "Analyze the nutritional content of a specified dish.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "dish_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the dish to analyze."
                                }
                            },
                            "required": ["dish_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "check_allergy_alert",
                        "description": "Check for potential allergens in a meal by checking the user's list of allergies against the meal and informing the user if there are possible allergens to be concerned about.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal to check."
                                },
                                "dish_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the dish to check."
                                },
                                "user_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the user."
                                }
                            },
                            "required": ["user_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "provide_nutrition_advice",
                        "description": "Offer personalized nutrition advice based on user's dietary preferences and health goals.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "integer",
                                    "description": "The ID of the user seeking advice."
                                }
                            },
                            "required": ["user_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "understand_dietary_choices",
                        "description": "Understand the available dietary choices that all users have access to. Use this to create more precise queries.",
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
                        "name": "create_meal",
                        "description": "Create custom meals in the database that will be used as part of meal plans.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "The name of the meal."
                                },
                                "dietary_preference": {
                                    "type": "string",
                                    "description": "The dietary preference category of the meal.",
                                    "enum": [
                                        "Vegan",
                                        "Vegetarian",
                                        "Pescatarian",
                                        "Gluten-Free",
                                        "Keto",
                                        "Paleo",
                                        "Halal",
                                        "Kosher",
                                        "Low-Calorie",
                                        "Low-Sodium",
                                        "High-Protein",
                                        "Dairy-Free",
                                        "Nut-Free",
                                        "Raw Food",
                                        "Whole 30",
                                        "Low-FODMAP",
                                        "Diabetic-Friendly",
                                        "Everything"
                                    ]
                                },
                                "description": {
                                    "type": "string",
                                    "description": "A brief description of the meal."
                                }
                            },
                            "required": [
                                "name",
                                "dietary_preference",
                                "description"
                            ]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "replace_meal_based_on_preferences",
                        "description": "Replace one or more meals in a user's meal plan based on their dietary preferences and restrictions. If no suitable alternative meal is found, a new meal is created.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "meal_plan_id": {
                                    "type": "integer",
                                    "description": "The unique identifier of the meal plan."
                                },
                                "old_meal_ids": {
                                    "type": "array",
                                    "items": {
                                        "type": "integer",
                                        "description": "A unique identifier for a meal."
                                    },
                                    "description": "List of unique identifiers of the meals to be replaced."
                                },
                                "days_of_week": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "description": "The day of the week on which the meal is scheduled, e.g., 'Monday', 'Tuesday', etc."
                                    },
                                    "description": "List of days of the week corresponding to each meal ID."
                                },
                                "meal_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "description": "The type of the meals, e.g., 'Breakfast', 'Lunch', 'Dinner'.",
                                        "enum": [
                                            "Breakfast",
                                            "Lunch",
                                            "Dinner"
                                        ]
                                    },
                                    "description": "List of meal types corresponding to each meal ID."
                                }
                            },
                            "required": [
                                "meal_plan_id",
                                "old_meal_ids",
                                "days_of_week",
                                "meal_types"
                            ]
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
        thread_id = data.get('thread_id')



        if not question:
            return Response({'error': 'No question provided'}, status=400)
        user_message = UserMessage.objects.create(
            user=user,
            message=question
        )
        relevant = is_question_relevant(question)
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
            summarized_title = generate_summary_title(question)
            print(f"New thread ID: {thread_id}")
            ChatThread.objects.create(
                user=user,
                openai_thread_id=thread_id,
                title=summarized_title[:254],
                is_active=True
            )

            user.week_shift = 0

        thread = ChatThread.objects.get(openai_thread_id=thread_id)
        user_message.thread = thread
        user_message.save()
        # Variable to store tool call results
        formatted_outputs = []

        if relevant:
            try:
                client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=question,
                )
            except OpenAIError as e:
                print(f'Error: {e}')
                if 'Can\'t add messages to thread' in str(e) and 'while a run' in str(e) and 'is active' in str(e):
                    # Extract the run ID from the error message
                    match = re.search(r'run (\w+)', str(e))
                    if match:
                        run_id = match.group(1)
                        # Cancel the active run
                        client.beta.threads.runs.cancel(run_id, thread_id=thread_id)
                        # Try to create the message again
                        client.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=question
                        )
                else:
                    logger.error(f'Failed to create message: {str(e)}')
                    user_message.response = f"Sorry, I was unable to send your message. Please try again."
                    user_message.save()
                    return  # Stopping the task if message creation fails
            response_data = {
                'new_thread_id': thread_id,
                'recommend_follow_up': False,
            }
            return Response(response_data)  
        else:
            response_data = {
                'last_assistant_message': "I'm sorry, I cannot help with that.",
                'new_thread_id': thread_id,
                'recommend_follow_up': False,
            }
            return Response(response_data)
        #TODO: Tie this function with the shared task, and with a listener that checks whether the message.response is ready
    
    except Exception as e:
        # Return error message wrapped in Response
        tb = traceback.format_exc()
        # Log the detailed error message
        logger.error(f'Error: {str(e)}\nTraceback: {tb}')
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_message_status(request, message_id):
    try:
        user_id = request.query_params.get('user_id')  # Use query_params for GET requests
        user = CustomUser.objects.get(id=user_id)
        message = UserMessage.objects.get(id=message_id, user=user)
        
        # Check if the message has a response
        if message.response:
            return Response({
                'message_id': message.id,
                'response': message.response,
                'status': 'completed'  # Indicate that the message has been processed
            })
        else:
            return Response({
                'message_id': message.id,
                'status': 'pending'  # Indicate that the message is still being processed
            })
    except CustomUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserMessage.DoesNotExist:
        return Response({'error': 'Message not found'}, status=404)

@api_view(['POST'])
def guest_ai_tool_call(request):
    tool_call = request.data.get('tool_call')
    print(f"Guest tool call: {tool_call}")
    name = tool_call['function']
    arguments = json.loads(tool_call['arguments'])  # Get arguments from tool_call
    if arguments is None:  # Check if arguments is None
        arguments = {}  # Assign an empty dictionary to arguments
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    return_value = guest_functions[name](**arguments)
    tool_outputs = {
        "tool_call_id": tool_call['id'],
        "output": return_value,
        "function": name,
    }

    return Response(tool_outputs)


@api_view(['POST'])
def ai_tool_call(request):
    try:
        user_id = request.data.get('user_id')
        user = CustomUser.objects.get(id=user_id)
        tool_call = request.data.get('tool_call')
        logger.info(f"Tool call received: {tool_call}")
        
        name = tool_call['function']
        logger.info(f"Function to call: {name}")

        try:
            arguments = json.loads(tool_call['arguments'])  # Get arguments from tool_call
            logger.info(f"Parsed arguments: {arguments}")
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON decode error: {json_err} - Raw arguments: {tool_call['arguments']}")
            return Response({'status': 'error', 'message': f"JSON decode error: {json_err}"})

        if arguments is None:  # Check if arguments is None
            arguments = {}  # Assign an empty dictionary to arguments
        
        # Ensure that 'request' is included in the arguments if needed
        arguments['request'] = request

        try:
            # This inner try block specifically catches TypeError that may occur 
            # when calling the function with incorrect arguments
            return_value = functions[name](**arguments)
            logger.info(f"Function {name} executed successfully with return value: {return_value}")
        except TypeError as e:
            # Handle unexpected arguments or missing arguments
            logger.error(f'Function call error: {str(e)} - Function: {name}, Arguments: {arguments}')
            return Response({'status': 'error', 'message': f"Function call error: {str(e)}"})
        except Exception as e:
            # Catch other unexpected errors
            logger.error(f'Tool Call Error: {str(e)} - Function: {name}, Arguments: {arguments}')
            return Response({'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"})
        
        tool_outputs = {
            "tool_call_id": tool_call['id'],
            "output": return_value,
        }

        # Create a new ToolCall instance
        tool_call_instance = ToolCall.objects.create(
            user=user,
            function_name=name,
            arguments=tool_call['arguments'],
            response=tool_outputs['output']
        )
        logger.info(f"Tool call logged successfully: {tool_call_instance.id}")

        return Response(tool_outputs)
    except Exception as e:
        # Handle errors that occur outside the function call
        logger.error(f'Error: {str(e)} - Tool call: {tool_call}')
        return Response({'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"})
