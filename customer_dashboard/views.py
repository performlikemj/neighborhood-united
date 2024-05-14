from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from meals.tasks import process_user_message
from meals.models import Order, Dish, Meal, Cart, MealPlanMeal, MealPlan, Meal
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
from django.conf import settings
from shared.utils import (get_user_info, post_review, update_review, delete_review, replace_meal_in_plan, 
                          remove_meal_from_plan, list_upcoming_meals, get_date, create_meal_plan, create_meal, 
                          add_meal_to_plan, auth_get_meal_plan, auth_search_chefs, auth_search_dishes, 
                          approve_meal_plan, auth_search_ingredients, auth_search_meals_excluding_ingredient, 
                          search_meal_ingredients, suggest_alternative_meals,guest_search_ingredients ,
                          guest_get_meal_plan, guest_search_chefs, guest_search_dishes, 
                          generate_review_summary, access_past_orders, get_goal, 
                          update_goal, adjust_week_shift, get_unupdated_health_metrics, 
                          update_health_metrics, check_allergy_alert, provide_nutrition_advice, 
                          recommend_follow_up, find_nearby_supermarkets,
                          search_healthy_meal_options, provide_healthy_meal_suggestions, 
                          understand_dietary_choices, is_question_relevant)
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
import asyncio
import logging
import threading
from decimal import Decimal
import traceback
# Load configuration from config.json
with open('/etc/config.json') as config_file:
    config = json.load(config_file)


logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_summary(request):
    logger.info(f"Generating user summary for user {request.user.id}")
    user = get_object_or_404(CustomUser, id=request.user.id)
    try:
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
            ]
        }
    except UserSummary.DoesNotExist:
        summary = "For me to be more useful, please update your goals in your profile and update your calories and health data"
        updated_at = int(time.time())  # Use current time if no summary

        data = {
            "data": [
                {
                    "content": [
                        {
                            "text": {
                                "annotations": [],
                                "value": summary
                            },
                            "type": "text"
                        }
                    ],
                    
                    "role": "assistant",
                },
            ]
        }
    return Response(data)


def generate_user_summary(user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    logger.warning(f"Generating user summary for user {user_id}")
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
            f"Date: {metric.date_recorded}, Weight: {metric.weight} kg ({metric.weight * Decimal('2.20462')} lbs), BMI: {metric.bmi}, Mood: {metric.mood}, Energy Level: {metric.energy_level}"
            for metric in user_health_metrics
        ] if user_health_metrics else ["No health metrics found."],
        "Calorie Intake": [f"Meal: {intake.meal_name}, Description: {intake.meal_description}, Portion Size: {intake.portion_size}, Date: {intake.date_recorded}" for intake in calorie_intake] if calorie_intake else ["No calorie intake data found."],
    }
    logger.warning(f"Formatted data: {formatted_data}")
    message = "No data found for the past month."
    client = OpenAI(api_key=settings.OPENAI_KEY) # Initialize OpenAI client
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", 
                 "content": f"Generate a detailed summary based on the following data that gives the user a high level view of their goals, health data, and how their caloric intake relates to those goals. Start the response off with a friendly welcoming tone.: {formatted_data}. If there is no data, please respond with the following message: {message}"
                 },
            ],
        )
        summary_text = response.choices[0].message.content
        print(f"Summary generated: {summary_text}")
    except Exception as e:
        # Handle exceptions or log errors
        return {"message": f"An error occurred trying to generate the summary. We are working to resolve the issue."}

    UserSummary.objects.update_or_create(user=user, defaults={'summary': summary_text})

    return {"message": "Summary generated successfully."}

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
        return Response({"error": 'An error occurred trying to update the record. We are working to resolve the issue'}, status=400)

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
        return Response({"error": 'An error occurred trying to fetch your records. We are working to resolve the issue'}, status=400)
    

@api_view(['POST'])  # This should only be a POST request
@permission_classes([IsAuthenticated, IsCustomer])
def api_add_calorie_intake(request):
    # TODO: Have a function that uses the AI model to calculate the calories and save it to a model
    try:
        data = request.data.copy()  # Make a mutable copy of the data
        data['user'] = request.user.id  # Add the user ID to the data
        serializer = CalorieIntakeSerializer(data=data)  # Pass the data to the serializer
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    except Exception as e:
        return Response({"error": 'An error occurred trying to add your record. We are working to resolve the issue'}, status=400)

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
        logger.warning(e)
        logger.warning(traceback.format_exc())
        return Response({"error": "An error occurred trying to delete the record. We are working to resolve the issue."}, status=400)



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
@permission_classes([IsAuthenticated, IsCustomer])
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
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    # Assuming you have a function to handle the OpenAI communication
    client = OpenAI(api_key=settings.OPENAI_KEY)
    try:
        messages = client.beta.threads.messages.list(openai_thread_id, extra_headers=headers)
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
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    client = OpenAI(api_key=settings.OPENAI_KEY)
    try:
        messages = client.beta.threads.messages.list(openai_thread_id, extra_headers=headers)
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

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_KEY}",
        "Content-Type": "application/json"
    }  
    
    client = OpenAI(api_key=settings.OPENAI_KEY)    
    # Check if the assistant ID is already stored in a file
  

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

        relevant = is_question_relevant(question)

        if not relevant:
            guest_assistant_id = config["NAUGHTY_ASSISTANT_ID"]
        else:   
            guest_assistant_id = config["GUEST_ASSISTANT_ID"]

        if not question:
            return Response({'error': 'No question provided'}, status=400)
        
        # Check if thread_id is safe
        if thread_id and not re.match("^thread_[a-zA-Z0-9]*$", thread_id):
            return Response({'error': 'Invalid thread_id'}, status=400)

        # Handle existing or new thread
        if not thread_id:
            openai_thread = client.beta.threads.create(extra_headers=headers)
            thread_id = openai_thread.id
    
        try:
            print("Creating a message")
            # Add a Message to a Thread
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=question,
                extra_headers=headers
            )
            print("Message created")
        except Exception as e:
            logger.error(f'Failed to create message: {str(e)}')
            return Response({'error': f'Failed to create message: {str(e)}'}, status=500)    
                

    
        # Variable to store tool call results
        formatted_outputs = []
            
        try:
            # Run the Assistant
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=guest_assistant_id,
                extra_headers=headers
                # Optionally, you can add specific instructions here
            )
        except Exception as e:
            logger.error(f'Failed to create run: {str(e)}')
            return Response({'error': f'Failed to create run: {str(e)}'}, status=500)
        if relevant:
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
    # Set up OpenAI
    client = OpenAI(api_key=settings.OPENAI_KEY)    
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    # Check if the assistant ID is already stored in a file

    user = CustomUser.objects.get(id=request.data.get('user_id'))

        
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

        if not question:
            return Response({'error': 'No question provided'}, status=400)
        user_message = UserMessage.objects.create(
            user=user,
            message=question
        )
        relevant = is_question_relevant(question)

        if not relevant:
            assistant_id = config["NAUGHTY_ASSISTANT_ID"]
        else:   
            assistant_id = config["AUTH_ASSISTANT_ID"]

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
            openai_thread = client.beta.threads.create(extra_headers=headers)
            thread_id = openai_thread.id
            print(f"New thread ID: {thread_id}")
            ChatThread.objects.create(
                user=user,
                openai_thread_id=thread_id,
                title=question[:255],  # Truncate question to 255 characters
                is_active=True
            )

            user.week_shift = 0

        thread = ChatThread.objects.get(openai_thread_id=thread_id)
        user_message.thread = thread
        user_message.save()
        # Variable to store tool call results
        formatted_outputs = []

        if relevant:
            client.beta.threads.messages.create(thread_id, role='user', content=question, extra_headers=headers)
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
        # Return error message wrapped in Response
        logger.error(f'Error: {str(e)}')
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
    user_id = request.data.get('user_id')
    user = CustomUser.objects.get(id=user_id)
    tool_call = request.data.get('tool_call')
    print(f"Tool call: {tool_call}")
    name = tool_call['function']
    arguments = json.loads(tool_call['arguments'])  # Get arguments from tool_call
    if arguments is None:  # Check if arguments is None
        arguments = {}  # Assign an empty dictionary to arguments
    # Ensure that 'request' is included in the arguments if needed
    arguments['request'] = request
    return_value = functions[name](**arguments)
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

    return Response(tool_outputs)