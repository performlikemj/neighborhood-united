# customer_dashboard > views.py
from uuid import uuid4
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from meals.models import Order, Dish, Meal, Cart, MealPlanMeal, MealPlan, Meal
from custom_auth.models import CustomUser, UserRole
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import (ChatThread, UserMessage, UserSummary, ToolCall, AssistantEmailToken, UserDailySummary, UserEmailSession)
import pytz
from zoneinfo import ZoneInfo
import json
import os
import re
import time
import requests
import traceback
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
                          analyze_nutritional_content, replace_meal_based_on_preferences, append_custom_dietary_preference)
from local_chefs.views import chef_service_areas, service_area_chefs
from django.core import serializers
from .serializers import ChatThreadSerializer
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.decorators import renderer_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsCustomer
from rest_framework import status
from rest_framework.response import Response
from django_countries.fields import Country
import decimal as _decimal
import datetime as _dt
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
import datetime
from asgiref.sync import async_to_sync
from hood_united.consumers import ToolCallConsumer
import asyncio
import logging
import threading
from django.views import View
from django.http import JsonResponse, StreamingHttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from meals.meal_assistant_implementation import (
    MealPlanningAssistant,
    OnboardingAssistant,
    generate_guest_id,
)
from meals.views import EventStreamRenderer
import traceback
from django.conf import settings
from asgiref.sync import async_to_sync
# Guest tool registration removed - customer standalone meal planning deprecated
from meals.tool_registration import get_all_tools, handle_tool_call
from meals.enhanced_email_processor import process_email_with_enhanced_formatting
from customer_dashboard.template_router import render_email_sections
from meals.feature_flags import legacy_meal_plan_enabled

class GuestChatThrottle(UserRateThrottle):
    rate = '100/day'  

class AuthChatThrottle(UserRateThrottle):
    rate = '1000/day'

logger = logging.getLogger(__name__) 

def _json_default(obj):
    """Safely coerce non-JSON types found in tool outputs into JSON.
    - Country → country code (or string)
    - Decimal → float
    - date/datetime → ISO8601 string
    - Fallback → str(obj)
    """
    try:
        if isinstance(obj, Country):
            try:
                return obj.code or str(obj)
            except Exception:
                return str(obj)
    except Exception:
        pass
    try:
        if isinstance(obj, _decimal.Decimal):
            return float(obj)
    except Exception:
        pass
    try:
        if isinstance(obj, (_dt.date, _dt.datetime)):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)

def _sse_json(data: dict) -> str:
    return json.dumps(data, default=_json_default)

@login_required
@require_http_methods(["POST"]) 
def send_message(request):
    """API endpoint for sending a message to the assistant"""
    try:
        data = json.loads(request.body)
        message = data.get('message')
        user_id = data.get('user_id')
        assistant = MealPlanningAssistant(user_id)
        if not message:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameter: message'
            }, status=400)
        

        
        # Send message to assistant
        result = assistant.send_message(message)
        
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to send message: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"]) 
def reset_conversation(request):
    """API endpoint for resetting a conversation with the assistant"""
    try:
        # Get user ID from the authenticated user
        user_id = request.data.get('user_id')
        assistant = MealPlanningAssistant(user_id)
        # Reset conversation
        result = assistant.reset_conversation()
        
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error resetting conversation: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to reset conversation: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"]) 
def get_conversation_history(request, user_id):
    """
    API endpoint for getting conversation history for a user.
    
    URL parameter:
    - user_id: The ID of the user
    
    Returns a JSON response with:
    - status: "success" or "error"
    - conversation_id: The ID of the conversation
    - messages: List of messages in the conversation
    - language: The language of the conversation
    """
    try:
        # Get conversation history
        assistant = MealPlanningAssistant(user_id)
        result = assistant.get_conversation_history()
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to get conversation history: {str(e)}'
        }, status=500)
    
# Email-based assistant view
@csrf_exempt
@api_view(['POST'])
def process_email(request):
    """API endpoint for processing emails from n8n"""
    try:
        # Parse the request body
        data = json.loads(request.body)
        sender_email = data.get('sender_email')
        token = data.get('token')  # Extracted from assistant+{token}@domain.com
        message_content = data.get('message_content')
        conversation_token = data.get('conversation_token')
        user_id = data.get('user_id')
        # Validate required parameters
        if not sender_email or not token or not message_content:
            logger.error(f"Missing required parameters: {data}")
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
        
        # Validate and get user from token
        is_valid, user, token_obj = AssistantEmailToken.validate_and_update_token(token)
        
        if not is_valid or not user:
            logger.error(f"Invalid token: {token}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid token'
            }, status=403)
        
        # Verify sender email matches token owner
        if user.email != sender_email:
            logger.warning(f"Email mismatch: token user {user.email}, sender {sender_email}")
            return JsonResponse({
                'status': 'error',
                'message': 'Sender email does not match token owner'
            }, status=403)
        
        # Process the message with the assistant
        assistant = MealPlanningAssistant(user_id)
        result = assistant.send_message(message_content)
        
        # Add the token to the result for n8n to use in the reply address
        result['token'] = token
        
        return JsonResponse(result)
    except Exception as e:
        logger.error(f"Error processing email: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to process email: {str(e)}'
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_recommend_follow_up(request):
    """
    Generate follow-up recommendations based on the most recent conversation.
    Updated to work with the OpenAI Responses API instead of the Assistants API.
    """
    user_id = request.data.get('user_id')
    user = get_object_or_404(CustomUser, id=user_id)

    # Step 1: Retrieve the most recent active chat thread for the user
    try:
        chat_thread = ChatThread.objects.filter(user=user, is_active=True).latest('created_at')
        # Ensure we always have the up‑to‑date history even if latest_response_id changed
    except ChatThread.DoesNotExist:
        return Response({'error': 'No active chat thread found.'}, status=404)

    # Step 2: Fetch the chat history from the database
    try:
        # Get a valid response ID using our helper function
        response_id = get_response_id_from_thread(chat_thread)
        
        if not response_id:
            return Response({'error': 'No response ID found for this conversation.'}, status=404)
        
        # Now we have a string response_id, not a list
        chat_history = []
        if response_id.startswith("resp_"):
            # Load from stored history in the DB
            raw_history = chat_thread.openai_input_history or []
            for item in raw_history:
                role = item.get("role")
                if role in (None, "system"):            # skip system + tool blobs
                    continue
                chat_history.append({
                    "role": role,
                    "content": item.get("content", "")
                })
        elif response_id.startswith("thread_"):
            # Legacy threads are no longer supported
            return Response({'error': 'Legacy threads are no longer supported.'}, status=400)
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        return Response({'error': f'Failed to fetch chat history'})

    # Step 3: Generate the context string from the chat history
    context = '\n'.join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

    # Step 4: Call the recommend_follow_up function to get follow-up prompts
    try:
        follow_up_recommendations = recommend_follow_up(request, context)
    except Exception as e:
        logger.error(f"Error generating follow-up recommendations: {e}")
        return Response({'error': f'Failed to generate follow-up recommendations'})

    # Step 5: Return the recommendations in the expected format
    return Response(follow_up_recommendations, status=200)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_summary_status(request):
    from meals.email_service import generate_user_summary
    if not request.user.is_authenticated:
        return Response({"status": "error", "message": "User is not authenticated"}, status=401)
    
    user_id = request.user.id
    
    # Find the most recent summary
    user_summary = UserDailySummary.objects.filter(
        user_id=user_id
    ).order_by('-summary_date').first()
    
    # Get the current date in the user's timezone
    user = request.user
    user_timezone = ZoneInfo(user.timezone if getattr(user, 'timezone', None) else 'UTC')
    today = timezone.now().astimezone(user_timezone).date()
    
    # If no summary exists or the most recent one is from before today, create a new one for today
    if not user_summary or user_summary.summary_date < today:
        user_summary = UserDailySummary.objects.create(
            user_id=user_id,
            summary_date=today,
            status=UserDailySummary.PENDING
        )
        # Queue the generation task
        generate_user_summary.delay(user_id, today.strftime('%Y-%m-%d'))
        return Response({"status": "pending", "message": "Summary generation started."}, status=202)
    
    # If most recent summary has error status, regenerate it
    if user_summary.status == UserDailySummary.ERROR:
        user_summary.status = UserDailySummary.PENDING
        user_summary.save(update_fields=["status"])
        generate_user_summary.delay(user_id, user_summary.summary_date.strftime('%Y-%m-%d'))
        return Response({"status": "pending", "message": "Summary generation restarted."}, status=202)

    # Return the appropriate status
    if user_summary.status == UserDailySummary.PENDING:
        return Response({"status": "pending", "message": "Summary is still being generated."}, status=202)
    elif user_summary.status == UserDailySummary.COMPLETED:
        return Response({"status": "completed"})
    else:
        return Response({"status": "error", "message": "An error occurred during summary generation."}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_user_summary(request):
    from meals.email_service import generate_user_summary
    if not request.user.is_authenticated:
        return Response({"status": "error", "message": "User is not authenticated"}, status=401)
    
    user_id = request.user.id
    
    # Find the most recent summary
    user_summary = UserDailySummary.objects.filter(
        user_id=user_id
    ).order_by('-summary_date').first()
    
    # Get the current date in the user's timezone
    user = request.user
    user_timezone = ZoneInfo(user.timezone if getattr(user, 'timezone', None) else 'UTC')
    today = timezone.now().astimezone(user_timezone).date()
    
    # If no summary exists or the most recent one is from before today, create a new one for today
    if not user_summary or user_summary.summary_date < today:
        user_summary = UserDailySummary.objects.create(
            user_id=user_id,
            summary_date=today,
            status=UserDailySummary.PENDING
        )
        # Queue the generation task
        generate_user_summary.delay(user_id, today.strftime('%Y-%m-%d'))
        return Response({
            "status": "pending",
            "message": "Summary generation started.",
            "summary_date": today.strftime('%Y-%m-%d')
        }, status=202)
    
    # If the most recent summary has error status, regenerate it
    if user_summary.status == UserDailySummary.ERROR:
        user_summary.status = UserDailySummary.PENDING
        user_summary.save(update_fields=["status"])
        generate_user_summary.delay(user_id, user_summary.summary_date.strftime('%Y-%m-%d'))
        return Response({
            "status": "pending", 
            "message": "Summary generation restarted.",
            "summary_date": user_summary.summary_date.strftime('%Y-%m-%d')
        }, status=202)
    
    # If the summary is still being generated
    if user_summary.status == UserDailySummary.PENDING:
        return Response({
            "status": "pending", 
            "message": "Summary is still being generated.",
            "summary_date": user_summary.summary_date.strftime('%Y-%m-%d')
        }, status=202)
    
    # If the summary is ready, return it
    return Response({
        "status": "completed",
        "summary": user_summary.summary,
        "summary_date": user_summary.summary_date.strftime('%Y-%m-%d'),
        "created_at": user_summary.created_at,
        "updated_at": user_summary.updated_at
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_history_page(request):
    """
    Get the 5 most recent chat threads for the user.
    This function doesn't directly interact with OpenAI API, so no changes needed.
    """
    chat_threads = (
        ChatThread.objects
        .filter(user=request.user)
        .order_by('-created_at')
    )
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')[:5]
    serializer = ChatThreadSerializer(chat_threads, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_thread_history(request):
    """
    Get paginated chat threads for the user.
    This function doesn't directly interact with OpenAI API, so no changes needed.
    """
    chat_threads = (
        ChatThread.objects
        .filter(user=request.user)
        .order_by('-created_at')
    )
    paginator = PageNumberPagination()
    paginated_chat_threads = paginator.paginate_queryset(chat_threads, request)
    serializer = ChatThreadSerializer(paginated_chat_threads, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_thread_detail_view(request, openai_thread_id):
    """
    Get the details of a chat thread **stored in the database**.

    We now persist every turn in `ChatThread.openai_input_history`, so we no
    longer need to round‑trip to the OpenAI Responses API.  
    The endpoint still receives `openai_thread_id` for backward compatibility –
    we simply look up that row and return the saved history.
    """
    try:
        logger.info(f"DEBUG THREAD LOOKUP - Looking up thread with ID: {openai_thread_id}")
        
        # Try looking up by latest_response_id first (most reliable)
        thread = ChatThread.objects.filter(
            user=request.user,
            latest_response_id=openai_thread_id
        ).first()
        
        if thread:
            logger.info(f"DEBUG THREAD LOOKUP - Found by latest_response_id: {thread.id}")
        else:
            # Try direct match on openai_thread_id field (exact string match)
            thread = ChatThread.objects.filter(
                user=request.user,
                openai_thread_id=openai_thread_id
            ).first()
            
            if thread:
                logger.info(f"DEBUG THREAD LOOKUP - Found by direct match on openai_thread_id: {thread.id}")
        
        # If still not found, do the more expensive list search operation
        if not thread:
            # Get all user threads and search manually
            user_threads = ChatThread.objects.filter(user=request.user)
            
            for t in user_threads:
                logger.info(f"DEBUG THREAD LOOKUP - Checking thread {t.id} with openai_thread_id: {t.openai_thread_id} (type: {type(t.openai_thread_id)})")
                
                if isinstance(t.openai_thread_id, list) and openai_thread_id in t.openai_thread_id:
                    thread = t
                    logger.info(f"DEBUG THREAD LOOKUP - Found match in list for thread {t.id}")
                    break
        
        # If this is the *first* turn of a brand‑new conversation, there may be
        # no DB row yet – go ahead and create one on the fly.
        if thread is None and openai_thread_id.startswith("resp_"):
            logger.info(f"DEBUG THREAD LOOKUP - Creating new thread for response ID: {openai_thread_id}")
            # Deactivate other threads
            ChatThread.objects.filter(
                user=request.user,
            ).update(is_active=False)
            thread = ChatThread.objects.create(
                user=request.user,
                openai_thread_id=[openai_thread_id],
                latest_response_id=openai_thread_id,
                openai_input_history=[]
            )
            logger.info(f"Created ChatThread for new response_id {openai_thread_id}")

        if thread is None:
            logger.info(f"DEBUG THREAD LOOKUP - No thread found for ID: {openai_thread_id}")
            return Response({'error': 'Thread not found.'}, status=404)
            
        
        chat_history = []
        if openai_thread_id.startswith('resp_'):
            # ── Primary path: use the saved JSON if it exists
            raw_history = thread.openai_input_history or []
            
            if raw_history:
                base_ts = int(thread.created_at.timestamp())
                for idx, item in enumerate(raw_history):
                    role = item.get('role')
                    if role in (None, 'system'):          # skip system & tool blobs
                        continue
                    chat_history.append({
                        'role': role,
                        'content': item.get('content', ''),
                        'created_at': base_ts + idx
                    })
        elif openai_thread_id.startswith('thread_'):
            # Legacy threads are no longer supported (OpenAI Assistants API removed)
            logger.warning(f"Legacy thread requested: {openai_thread_id} - no longer supported")
            return Response({'error': 'Legacy threads are no longer supported. Please start a new conversation.'}, status=400)

        thread.is_active = True
        thread.save()
        return Response({'chat_history': chat_history})
    except Exception as e:
        logger.error(f"Error retrieving thread detail: {str(e)}")
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": f"Error retrieving thread detail: {str(e)}", "source":"api_thread_detail_view", "traceback": traceback.format_exc()})
        return Response({'error': "Error retrieving message details"})

def api_format_chat_history_from_response(response):
    """
    Format the chat history from a response object from the Responses API.
    This is a new function to handle the different structure of the Responses API.
    """
    formatted_messages = []
    
    # Add the input messages (user messages)
    if hasattr(response, 'input'):
        if isinstance(response.input, list):
            for msg in response.input:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    formatted_messages.append({
                        'role': msg.role,
                        'content': msg.content,
                        'created_at': response.created_at  # Use response creation time as fallback
                    })
        else:
            # If input is a string, it's a user message
            formatted_messages.append({
                'role': 'user',
                'content': response.input,
                'created_at': response.created_at  # Use response creation time
            })
    
    # Add the output messages (assistant messages)
    if hasattr(response, 'output') and response.output:
        for output_item in response.output:
            if hasattr(output_item, 'type') and output_item.type == 'message':
                if hasattr(output_item, 'role') and hasattr(output_item, 'content'):
                    # Handle the nested content structure
                    content_text = ""
                    if isinstance(output_item.content, list):
                        for content_item in output_item.content:
                            if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                if hasattr(content_item, 'text'):
                                    content_text += content_item.text
                    else:
                        content_text = output_item.content
                        
                    # Get creation time if available, otherwise use response creation time
                    created_at = getattr(output_item, 'created_at', response.created_at)
                    
                    formatted_messages.append({
                        'role': output_item.role,
                        'content': content_text,
                        'created_at': created_at
                    })
    
    # Sort messages by creation time if available
    formatted_messages.sort(key=lambda x: x['created_at'])
    
    return formatted_messages

# Keep the original function for backward compatibility with any code that might still use it
def api_format_chat_history(messages):
    """
    Format the chat history from a messages object from the Assistants API.
    This function is kept for backward compatibility.
    """
    formatted_messages = []
    for msg in messages.data:
        formatted_msg = {
            "role": msg.role,
            "content": msg.content[0].text.value if hasattr(msg, 'content') and msg.content else "",
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
    logger.info(f"History page data: {data}")
    return JsonResponse({'chat_threads': data})

@login_required
@user_passes_test(is_customer)
def history_page(request):
    chat_threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'customer_dashboard/history.html', {'chat_threads': chat_threads})

@login_required
@user_passes_test(is_customer)
def thread_detail(request, openai_thread_id):
    """View thread details from database. Legacy OpenAI threads are no longer supported."""
    try:
        # Try to find thread in database
        thread = ChatThread.objects.filter(
            user=request.user,
            latest_response_id=openai_thread_id
        ).first()
        
        if not thread:
            thread = ChatThread.objects.filter(
                user=request.user,
                openai_thread_id__contains=openai_thread_id
            ).first()
        
        if not thread:
            return render(request, 'customer_dashboard/error.html', 
                         {'message': 'Thread not found. Legacy threads are no longer supported.'})
        
        # Format chat history from stored data
        raw_history = thread.openai_input_history or []
        chat_history = "\n\n".join([
            f"{item.get('role', 'unknown').upper()}: {item.get('content', '')}"
            for item in raw_history if item.get('role') not in (None, 'system')
        ])
        
        return render(request, 'customer_dashboard/thread_detail.html', {'chat_history': chat_history})
    except Exception as e:
        # Handle exceptions, possibly showing an error message
        return render(request, 'customer_dashboard/error.html', {'message': str(e)})

def format_chat_history(messages):
    # Format the messages for display. This could be as simple as concatenating them,
    # or you might add formatting to distinguish between user and assistant messages.
    return "\n\n".join([f"{msg.role.upper()}: {msg.content[0].text.value}" for msg in messages.data])

    
def create_openai_prompt(user_id):
    # Legacy function - health tracking removed
    user_goal = "improving my diet"  # Generic goal as health tracking is removed
    
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
    if not legacy_meal_plan_enabled():
        raise Http404("Legacy meal plans are disabled.")

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
    """Legacy customer dashboard - health tracking removed."""
    current_date = timezone.now()
    start_week = current_date - timedelta(days=current_date.weekday())
    end_week = start_week + timedelta(days=6)

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

    context = {
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
    """Legacy endpoint - goal tracking removed."""
    return JsonResponse({'goals': []}, safe=False)


@login_required
@user_passes_test(is_customer)
def update_goal_api(request):
    """Legacy endpoint - goal tracking removed."""
    return JsonResponse({'error': 'Goal tracking has been removed'}, status=410)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@renderer_classes([EventStreamRenderer])
def stream_message(request):
    """
    Stream a message from the assistant for logged‑in users via SSE.
    """
    user_id = request.user.id
    # Support both 'message' and legacy 'question' from frontend
    message = request.data.get('message') or request.data.get('question')
    thread_id = request.data.get('thread_id')  # Check if we're getting thread_id
    response_id = request.data.get('response_id')  # Check if we're getting response_id
    # Optional meal context from frontend
    chef_username = request.data.get('chef_username')
    topic = request.data.get('topic')
    meal_id = request.data.get('meal_id')
        
    # Use the correct ID - prefer thread_id if provided, fallback to response_id
    effective_thread_id = thread_id or response_id

    # If the front end requested a new conversation, ignore any provided ID once
    try:
        if request.session.pop('chat_reset', False):
            effective_thread_id = None
            request.session.save()
    except Exception:
        pass
    
    # Build an augmented message that includes optional meal context
    augmented_message = message or ""
    meal_context_lines = []
    meal_obj = None
    if meal_id:
        try:
            # Try integer IDs first
            meal_obj = Meal.objects.select_related('chef__user').filter(id=int(meal_id)).first()
        except (ValueError, TypeError):
            # Fall back gracefully if meal_id isn't an int
            meal_obj = Meal.objects.select_related('chef__user').filter(id=meal_id).first()

    try:
        if meal_obj:
            derived_chef_username = None
            try:
                derived_chef_username = getattr(getattr(meal_obj.chef, 'user', None), 'username', None)
            except Exception:
                derived_chef_username = None

            # Prefer explicit chef_username if provided; otherwise derive from meal
            final_chef_username = chef_username or derived_chef_username

            meal_context_lines.append("You are answering a question about a specific meal from our catalog.")
            if final_chef_username:
                meal_context_lines.append(f"Chef username: {final_chef_username}")
            meal_context_lines.append(f"Meal name: {meal_obj.name}")
            if meal_obj.price is not None:
                meal_context_lines.append(f"Price: ${meal_obj.price}")
            if topic:
                meal_context_lines.append(f"Topic: {topic}")
            if meal_obj.description:
                # Limit very long descriptions in the context
                desc = str(meal_obj.description)
                if len(desc) > 600:
                    desc = desc[:600] + "…"
                meal_context_lines.append(f"Description: {desc}")
        else:
            # If no meal object but we have some context, include a light preface
            light_ctx = []
            if chef_username:
                light_ctx.append(f"Chef username: {chef_username}")
            if topic:
                light_ctx.append(f"Topic: {topic}")
            if light_ctx:
                meal_context_lines.append("You are answering a question about a specific meal.")
                meal_context_lines.extend(light_ctx)
    except Exception as e:
        logger.warning(f"DEBUG STREAM - Error building meal context: {e}")

    if meal_context_lines:
        preface = "\n".join(meal_context_lines)
        augmented_message = f"[MEAL_CONTEXT]\n{preface}\n[/MEAL_CONTEXT]\n\nQuestion: {message or ''}"

    
    # Check if this thread exists before we start
    try:
        found_match = False
        threads = ChatThread.objects.filter(user=request.user)
        for t in threads:
            if (isinstance(t.openai_thread_id, list) and effective_thread_id in t.openai_thread_id) or \
               (t.latest_response_id == effective_thread_id):
                logger.info(f"DEBUG STREAM - Found existing thread {t.id} matching ID {effective_thread_id}")
                found_match = True
                break
        if effective_thread_id and not found_match:
            logger.info("DEBUG STREAM - No matching thread found for provided ID; starting new")
            effective_thread_id = None
    except Exception as e:
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'stream_message',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        logger.error(f"DEBUG STREAM - Error checking threads: {str(e)}")
    
    assistant = MealPlanningAssistant(user_id)
    def event_stream():
        emitted_id = False
        chunk_count = 0

        def _sse_log(kind: str, payload: dict):
            """Log SSE payloads with safe previews to help diagnose ordering/mixups."""
            try:
                preview = {}
                if isinstance(payload, dict):
                    preview.update(payload)
                    # Trim large text deltas
                    if isinstance(preview.get("delta"), dict) and isinstance(preview["delta"].get("text"), str):
                        t = preview["delta"]["text"]
                        preview["delta"]["text"] = (t[:200] + "…") if len(t) > 200 else t
                    # Trim tool outputs
                    if "output" in preview:
                        out = preview["output"]
                        if isinstance(out, dict) and isinstance(out.get("markdown"), str):
                            md = out["markdown"]
                            preview["output"] = {"markdown_preview": (md[:200] + "…") if len(md) > 200 else md}
                        elif isinstance(out, str):
                            preview["output"] = (out[:200] + "…") if len(out) > 200 else out
                logger.info(f"SSE AUTH [{chunk_count}] -> {kind}: {preview}")
                # Also print directly to stdout so it appears in container/terminal logs
                # stdout prints removed after debugging
            except Exception as e:
                logger.warning(f"SSE AUTH log error for {kind}: {e}")
        try:
            for chunk in assistant.stream_message(augmented_message, effective_thread_id):
                chunk_count += 1
                chunk_type = chunk.get("type", "unknown")
                
                
                # Skip if chunk is not a dictionary
                if not isinstance(chunk, dict):
                    continue
                    
                # initial response.created event
                if not emitted_id and chunk.get("type") == "response_id":
                    response_id = chunk.get("id")
                    logger.info(f"DEBUG STREAM - Got new response_id: {response_id}")
                    event_payload = {"type": "response.created", "id": response_id}
                    _sse_log("response.created", event_payload)
                    yield f"data: {_sse_json(event_payload)}\n\n"
                    emitted_id = True
                    continue

                # 2) tool_result events
                if chunk.get("type") == "tool_result":
                    payload = {
                        "type": "response.tool",
                        "id": chunk.get("tool_call_id"),
                        "name": chunk.get("name"),
                        "output": chunk.get("output"),
                    }
                    _sse_log("response.tool", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 3) assistant text deltas (always 'text')
                if chunk.get("type") == "text":
                    payload = {
                        "type": "response.output_text.delta",
                        "delta": {"text": chunk.get("content")},
                    }
                    _sse_log("response.output_text.delta", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 4) follow‑up assistant response (rare)
                if chunk.get("type") == "follow_up_response":
                    _sse_log("follow_up_response", chunk)
                    yield f"data: {_sse_json(chunk)}\n\n"
                    continue

                # 5) conversation completed
                if chunk.get("type") == "response.completed":
                    logger.info(f"DEBUG STREAM - Stream completed")
                    payload = {"type": "response.completed"}
                    _sse_log("response.completed", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 6) assistant wants to run *another* tool (rare edge case)
                if chunk.get("type") == "response.function_call":
                    payload = {
                        "type": "response.tool",
                        "name": chunk.get("name"),
                        "output": chunk.get("output"),
                    }
                    _sse_log("response.function_call", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue
            
        except Exception as e:
            logger.error(f"Error in stream_message: {str(e)}")
            traceback.print_exc()
            yield f"data: {_sse_json({'type': 'error', 'message': str(e)})}\n\n"
            
        # close the SSE stream
        yield 'event: close\n\n'
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@renderer_classes([EventStreamRenderer])
def guest_stream_message(request):
    """
    Stream a message from the assistant for guest users via SSE.
    """
    # Try to get guest_id from multiple sources in priority order:
    # 1. Request data
    # 2. Session
    # 3. Generate new (as last resort)
    guest_id = None
    
    # Check request data first (highest priority)
    if hasattr(request, 'data') and isinstance(request.data, dict):
        guest_id = request.data.get('guest_id')
        if guest_id:
            # Save to session for consistency across requests
            request.session['guest_id'] = guest_id
            request.session.save()
            logger.info(f"GUEST_STREAM: Using guest_id {guest_id} from request data")
    
    # If not in request data, try session
    if not guest_id:
        guest_id = request.session.get('guest_id')
        if guest_id:
            logger.info(f"GUEST_STREAM: Using guest_id {guest_id} from session")
    
    # Generate only as last resort
    if not guest_id:
        guest_id = generate_guest_id()
        request.session['guest_id'] = guest_id
        request.session.save()
        logger.info(f"GUEST_STREAM: Generated new guest_id {guest_id}")
    
    # Support both 'message' and legacy 'question' from frontend
    message = request.data.get('message') or request.data.get('question')
    thread_id = request.data.get('response_id')
    # If a guest reset was requested, ignore any prior response_id once
    try:
        if request.session.pop('guest_chat_reset', False):
            thread_id = None
            request.session.save()
    except Exception:
        pass
    
    assistant = MealPlanningAssistant(guest_id)
    def event_stream():
        emitted_id = False
        chunk_count = 0

        def _sse_log(kind: str, payload: dict):
            try:
                preview = {}
                if isinstance(payload, dict):
                    preview.update(payload)
                    if isinstance(preview.get("delta"), dict) and isinstance(preview["delta"].get("text"), str):
                        t = preview["delta"]["text"]
                        preview["delta"]["text"] = (t[:200] + "…") if len(t) > 200 else t
                    if "output" in preview:
                        out = preview["output"]
                        if isinstance(out, dict) and isinstance(out.get("markdown"), str):
                            md = out["markdown"]
                            preview["output"] = {"markdown_preview": (md[:200] + "…") if len(md) > 200 else md}
                        elif isinstance(out, str):
                            preview["output"] = (out[:200] + "…") if len(out) > 200 else out
                logger.info(f"SSE GUEST [{chunk_count}] -> {kind}: {preview}")
                # stdout prints removed after debugging
            except Exception as e:
                logger.warning(f"SSE GUEST log error for {kind}: {e}")
        try:
            for chunk in assistant.stream_message(message, thread_id):
                chunk_count += 1
                # Skip if chunk is not a dictionary
                if not isinstance(chunk, dict):
                    continue
                    
                # initial response.created event
                if not emitted_id and chunk.get("type") == "response_id":
                    payload = {"type": "response.created", "id": chunk.get("id")}
                    _sse_log("response.created", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    emitted_id = True
                    continue

                # 2) tool_result events
                if chunk.get("type") == "tool_result":
                    payload = {
                        "type": "response.tool",
                        "id": chunk.get("tool_call_id"),
                        "name": chunk.get("name"),
                        "output": chunk.get("output"),
                    }
                    _sse_log("response.tool", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 3) assistant text deltas (always 'text')
                if chunk.get("type") == "text":
                    payload = {
                        "type": "response.output_text.delta",
                        "delta": {"text": chunk.get("content")},
                    }
                    _sse_log("response.output_text.delta", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 4) follow‑up assistant response (rare)
                if chunk.get("type") == "follow_up_response":
                    _sse_log("follow_up_response", chunk)
                    yield f"data: {json.dumps(chunk)}\n\n"
                    continue

                # 5) conversation completed
                if chunk.get("type") == "response.completed":
                    payload = {"type": "response.completed"}
                    _sse_log("response.completed", payload)
                    yield f"data: {_sse_json(payload)}\n\n"
                    continue

                # 6) assistant wants to run *another* tool (rare edge case)
                if chunk.get("type") == "response.function_call":
                    payload = {
                        "type": "response.tool",
                        "name": chunk.get("name"),
                        "output": chunk.get("output"),
                    }
                    _sse_log("response.function_call", payload)
                    yield f"data: {json.dumps(payload)}\n\n"
                    continue
        except Exception as e:
            logger.error(f"Error in guest_stream_message: {str(e)}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            
        # close the SSE stream
        yield 'event: close\n\n'

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    response["X-Guest-ID"] = guest_id
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_gpt(request):
    """
    Send a message to the OpenAI Responses API and get a response.
    `
    This endpoint is for authenticated users and returns the full response
    along with the new response ID.
    """
    try:
        # Extract parameters from request (support 'message' or legacy 'question')
        message = request.data.get('message') or request.data.get('question')
        thread_id = request.data.get('thread_id')  # Previous response ID
        user_id = request.user.id
        
        # Initialize the MealPlanningAssistant
        assistant = MealPlanningAssistant(user_id)
        
        # Send the message and get the response
        result = assistant.send_message(message, thread_id)
        
        # Return the response
        return Response({
            'message': result.get('message', ''),
            'new_thread_id': result.get('response_id'),
            'recommend_follow_up': False  # Default value, can be updated if needed
        })
    except Exception as e:
        logger.error(f"Error in chat_with_gpt: {str(e)}")
        return Response({'error': str(e)}, status=500)

@csrf_exempt
@api_view(['POST'])
def guest_chat_with_gpt(request):
    """API endpoint for guest users to chat with the assistant"""
    logger.info(f"Request: {request}")
    try:
        data = request.data
        message = data.get('message')
        thread_id = data.get('thread_id')  # This is actually the response_id
        
        if not message:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameter: message'
            }, status=400)
        
        # Ensure session is created before accessing/setting guest_id
        if not request.session.session_key:
            request.session.create()
            
        # Try to get guest_id from request first, then session
        request_guest_id = data.get('guest_id')
        session_guest_id = request.session.get('guest_id')
        
        # Priority: request > session > generate new
        if request_guest_id:
            guest_id = request_guest_id
            # Store in session for future consistency
            request.session['guest_id'] = guest_id
            request.session.save()
            logger.info(f"GUEST_CHAT: Using guest_id {guest_id} from request")
        elif session_guest_id:
            guest_id = session_guest_id
            logger.info(f"GUEST_CHAT: Using guest_id {guest_id} from session")
        else:
            guest_id = generate_guest_id()
            request.session['guest_id'] = guest_id
            request.session.save()
            logger.info(f"GUEST_CHAT: Generated new guest_id {guest_id}")
        
        # Send message to assistant with thread_id parameter
        assistant = MealPlanningAssistant(guest_id)
        result = assistant.send_message(message, thread_id)
        
        # Return the response with the new thread_id (which is actually the response_id)
        return JsonResponse({
            'message': result.get('message', ''),
            'new_thread_id': result.get('response_id'),
            'recommend_follow_up': False  # Default value
        })
    except Exception as e:
        logger.error(f"Error in guest_chat_with_gpt: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to get response from assistant: {str(e)}'
        }, status=500)

@api_view(['POST'])
def ai_tool_call(request):
    """
    Adapter function for handling tool calls with the new MealPlanningAssistant.
    
    Note: The MealPlanningAssistant handles tool calls internally, but we need to
    maintain this endpoint for compatibility with the frontend.
    """
    try:
        # Debug prints removed
        user_id = request.data.get('user_id')
        user = CustomUser.objects.get(id=user_id)
        tool_call = request.data.get('tool_call')
        logger.info(f"Tool call received: {tool_call}")
        
        # Get the active thread for this user
        try:
            thread = ChatThread.objects.get(user=user, is_active=True)
        except ChatThread.DoesNotExist:
            return Response({'error': 'No active thread found'}, status=404)
        
        # The MealPlanningAssistant already handles tool calls internally,
        # but we need to maintain this endpoint for compatibility.
        # We'll use the assistant's handle_tool_call method directly.
        from meals.tool_registration import handle_tool_call
        
        # Create a tool call object that matches the expected format
        class ToolCallObj:
            def __init__(self, tc_data):
                self.id = tc_data['id']
                self.function = type('obj', (object,), {
                    'name': tc_data['function'],
                    'arguments': tc_data['arguments']
                })
        
        tool_call_obj = ToolCallObj(tool_call)
        
        # Handle the tool call
        tool_result = handle_tool_call(tool_call_obj)
        
        # Save the tool call to the database
        from customer_dashboard.models import ToolCall
        ToolCall.objects.create(
            user=user,
            function_name=tool_call['function'],
            arguments=tool_call['arguments'],
            response=tool_result
        )
        
        # Return the result in the format expected by the frontend
        return Response({
            "tool_call_id": tool_call['id'],
            "output": tool_result,
        })
        
    except Exception as e:
        # Handle errors
        logger.error(f'Error: {str(e)} - Tool call: {tool_call if "tool_call" in locals() else "N/A"}')
        return Response({'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"})

@api_view(['GET'])
def get_message_status(request, message_id):
    """
    Adapter function for checking message status.
    
    Note: With the MealPlanningAssistant, responses are immediate, but we maintain
    this endpoint for compatibility with the frontend.
    """
    try:
        user_id = request.query_params.get('user_id')
        user = CustomUser.objects.get(id=user_id)
        message = UserMessage.objects.get(id=message_id, user=user)
        
        # Check if the message has a response
        if message.response:
            return Response({
                'message_id': message.id,
                'response': message.response,
                'status': 'completed'
            })
        else:
            # With the MealPlanningAssistant, responses should be immediate,
            # but we'll maintain the pending status for compatibility
            return Response({
                'message_id': message.id,
                'status': 'pending'
            })
    except CustomUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    except UserMessage.DoesNotExist:
        return Response({'error': 'Message not found'}, status=404)


@api_view(['POST'])
def guest_ai_tool_call(request):
    """
    Adapter function for handling guest tool calls with the new MealPlanningAssistant.
    
    Note: The MealPlanningAssistant handles tool calls internally, but we need to
    maintain this endpoint for compatibility with the frontend.
    """
    try:
        tool_call = request.data.get('tool_call')
        logger.info(f"Guest tool call received: {tool_call}")
        
        # The MealPlanningAssistant already handles tool calls internally,
        # but we need to maintain this endpoint for compatibility.
        # We'll use the assistant's handle_tool_call method directly.
        from meals.tool_registration import handle_tool_call
        
        # Create a tool call object that matches the expected format
        class ToolCallObj:
            def __init__(self, tc_data):
                self.id = tc_data['id']
                self.function = type('obj', (object,), {
                    'name': tc_data['function'],
                    'arguments': tc_data['arguments']
                })
        
        tool_call_obj = ToolCallObj(tool_call)
        
        # Handle the tool call
        tool_result = handle_tool_call(tool_call_obj)
        
        # Return the result in the format expected by the frontend
        return Response({
            "tool_call_id": tool_call['id'],
            "output": tool_result,
            "function": tool_call['function'],
        })
        
    except Exception as e:
        # Handle errors
        logger.error(f'Error: {str(e)} - Tool call: {tool_call if "tool_call" in locals() else "N/A"}')
        return Response({'status': 'error', 'message': f"An unexpected error occurred: {str(e)}"})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def new_conversation(request):
    """
    Starts a fresh chat thread for the user:
    - Marks any existing active threads inactive in the DB
    - Resets in-memory assistant state
    - Returns a simple JSON success
    """
    try:
        user_id = str(request.user.id)

        # 1) Deactivate existing chat threads
        ChatThread.objects.filter(user=request.user, is_active=True) \
                          .update(is_active=False)

        # 2) Clear assistant's internal context
        assistant = MealPlanningAssistant(user_id)
        assistant.reset_conversation()

        # 2a) Instruct next SSE request to ignore any prior thread/response id
        try:
            request.session['chat_reset'] = True
            request.session.save()
        except Exception:
            pass

        # 3) Let front-end know we're ready for a new chat
        return JsonResponse({"status": "success", "message": "New conversation started."})
    except Exception as e:
        logger.error(f"Error starting new conversation for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to start new conversation: {str(e)}'
        }, status=500)

@api_view(['POST'])
def guest_new_conversation(request):
    """
    Starts a fresh guest chat by clearing the assistant's in-memory state
    """
    try:
        # Get guest_id from request (sent by Streamlit)
        guest_id = request.data.get('guest_id')
        
        if guest_id:
            # Store it in session for backward compatibility
            request.session['guest_id'] = guest_id
            request.session.save()
            # Debug prints removed
            
            # Reset the conversation for this guest_id
            assistant = MealPlanningAssistant(guest_id)
            assistant.reset_conversation()
            # Mark session so the next SSE ignores any prior response_id
            try:
                request.session['guest_chat_reset'] = True
                request.session.save()
            except Exception:
                pass
            
            return JsonResponse({
                "status": "success",
                "guest_id": guest_id,
                "message": "Guest conversation reset successfully."
            })
        else:
            # Fall back to existing session guest_id
            guest_id = request.session.get('guest_id')
            
            # Only generate a new guest_id if none exists
            if not guest_id:
                guest_id = generate_guest_id()
                request.session['guest_id'] = guest_id
                request.session.save()
                # Debug prints removed
            else:
                # Debug prints removed
                pass
                
            # Reset the conversation
            assistant = MealPlanningAssistant(guest_id)
            assistant.reset_conversation()
            try:
                request.session['guest_chat_reset'] = True
                request.session.save()
            except Exception:
                pass
            
            return JsonResponse({
                "status": "success",
                "guest_id": guest_id,
                "message": "Guest conversation reset successfully."
            })
    except Exception as e:
        logging.error(f"Error in guest_new_conversation: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to start new guest conversation: {str(e)}'
        }, status=500)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@renderer_classes([EventStreamRenderer])
def onboarding_stream_message(request):
    """Stream onboarding chat messages for guest users via SSE."""
    import traceback
    import requests
    import os
    
    try:
        # Validate request method
        if request.method != 'POST':
            logger.error(f"onboarding_stream_message: Invalid method {request.method}, expected POST")
            return JsonResponse({
                'status': 'error',
                'message': f'Method {request.method} not allowed. Use POST.'
            }, status=405)
        
        # Check request data access
        try:
            request_data = request.data
        except Exception as data_error:
            logger.error(f"onboarding_stream_message: Error accessing request.data: {str(data_error)}", exc_info=True)
            # Try to access request.POST as fallback
            try:
                request_data = request.POST
            except Exception as post_error:
                logger.error(f"onboarding_stream_message: Error accessing request.POST: {str(post_error)}", exc_info=True)
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": f"Data access error: {str(data_error)}, POST error: {str(post_error)}", 
                        "source": "onboarding_stream_message.data_access", 
                        "request_method": request.method,
                        "content_type": request.content_type,
                        "raw_body": str(request.body),
                        "traceback": traceback.format_exc()
                    })
                return JsonResponse({
                    'status': 'error',
                    'message': 'Unable to parse request data'
                }, status=400)
        
        # Check session access
        try:
            session_data = dict(request.session)
        except Exception as session_error:
            logger.error(f"onboarding_stream_message: Error accessing session: {str(session_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(session_error), 
                    "source": "onboarding_stream_message.session_access", 
                    "traceback": traceback.format_exc()
                })
            session_data = {}
        
        # Ensure session exists
        try:
            if not request.session.session_key:
                request.session.create()
        except Exception as session_create_error:
            logger.error(f"onboarding_stream_message: Error creating session: {str(session_create_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(session_create_error), 
                    "source": "onboarding_stream_message.session_create", 
                    "traceback": traceback.format_exc()
                })
        
        # Extract guest_id
        try:
            guest_id = request_data.get('guest_id') if hasattr(request_data, 'get') else None
            if not guest_id and hasattr(request, 'session'):
                guest_id = request.session.get('guest_id')
        except Exception as guest_id_error:
            logger.error(f"onboarding_stream_message: Error extracting guest_id: {str(guest_id_error)}", exc_info=True)
            guest_id = None
        
        # Generate guest_id if needed
        if not guest_id:
            try:
                from meals.meal_assistant_implementation import generate_guest_id
                guest_id = generate_guest_id()
                if hasattr(request, 'session'):
                    request.session['guest_id'] = guest_id
                    request.session.save()
            except Exception as generate_error:
                logger.error(f"onboarding_stream_message: Error generating guest_id: {str(generate_error)}", exc_info=True)
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": str(generate_error), 
                        "source": "onboarding_stream_message.generate_guest_id", 
                        "traceback": traceback.format_exc()
                    })
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to generate guest ID'
                }, status=500)
        
        # Extract message and thread_id
        try:
            message = request_data.get('message') if hasattr(request_data, 'get') else None
            thread_id = request_data.get('response_id') if hasattr(request_data, 'get') else None
        except Exception as extract_error:
            logger.error(f"onboarding_stream_message: Error extracting message/thread_id: {str(extract_error)}", exc_info=True)
            message = None
            thread_id = None
        
        # Validate message
        if not message:
            logger.error(f"onboarding_stream_message: Missing message parameter")
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameter: message'
            }, status=400)
        
        # Clear any existing conversation history to prevent context confusion
        # (In case this is the first onboarding message without calling new_conversation first)
        try:
            from meals.meal_assistant_implementation import GLOBAL_GUEST_STATE
            if guest_id in GLOBAL_GUEST_STATE:
                del GLOBAL_GUEST_STATE[guest_id]
                logger.info(f"onboarding_stream_message: Cleared existing conversation history for guest_id={guest_id}")
        except Exception as clear_error:
            logger.warning(f"onboarding_stream_message: Failed to clear existing history for guest_id={guest_id}: {str(clear_error)}")
            # Don't fail the request for this - just log and continue
        
        # Create OnboardingAssistant
        try:
            from meals.meal_assistant_implementation import OnboardingAssistant
            assistant = OnboardingAssistant(guest_id)
        except Exception as assistant_error:
            logger.error(f"onboarding_stream_message: Error creating OnboardingAssistant: {str(assistant_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(assistant_error), 
                    "source": "onboarding_stream_message.create_assistant", 
                    "guest_id": guest_id,
                    "traceback": traceback.format_exc()
                })
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to create onboarding assistant: {str(assistant_error)}'
            }, status=500)

        def event_stream():
            emitted_id = False
            chunk_count = 0

            def _sse_log(kind: str, payload: dict):
                try:
                    preview = {}
                    if isinstance(payload, dict):
                        preview.update(payload)
                        if isinstance(preview.get("delta"), dict) and isinstance(preview["delta"].get("text"), str):
                            t = preview["delta"]["text"]
                            preview["delta"]["text"] = (t[:200] + "…") if len(t) > 200 else t
                        if "output" in preview:
                            out = preview["output"]
                            if isinstance(out, dict) and isinstance(out.get("markdown"), str):
                                md = out["markdown"]
                                preview["output"] = {"markdown_preview": (md[:200] + "…") if len(md) > 200 else md}
                            elif isinstance(out, str):
                                preview["output"] = (out[:200] + "…") if len(out) > 200 else out
                    logger.info(f"SSE ONBOARD [{chunk_count}] -> {kind}: {preview}")
                    # stdout prints removed after debugging
                except Exception as e:
                    logger.warning(f"SSE ONBOARD log error for {kind}: {e}")
            
            try:
                for chunk in assistant.stream_message(message, thread_id):
                    chunk_count += 1
                    if not isinstance(chunk, dict):
                        continue

                    chunk_type = chunk.get("type", "unknown")
                    
                    if not emitted_id and chunk.get("type") == "response_id":
                        response_id = chunk.get('id')
                    payload = {'type': 'response.created', 'id': response_id}
                    _sse_log('response.created', payload)
                    yield f"data: {json.dumps(payload)}\n\n"
                    emitted_id = True
                    continue

                    if chunk.get("type") == "tool_result":
                        tool_call_id = chunk.get("tool_call_id")
                        tool_name = chunk.get("name")
                        tool_output = chunk.get("output")
                        
                        payload = {
                            "type": "response.tool",
                            "id": tool_call_id,
                            "name": tool_name,
                            "output": tool_output,
                        }
                        _sse_log('response.tool', payload)
                        yield f"data: {_sse_json(payload)}\n\n"
                        continue

                    if chunk.get("type") == "text":
                        text_content = chunk.get('content')
                        
                        payload = {
                            "type": "response.output_text.delta",
                            "delta": {"text": text_content},
                        }
                        _sse_log('response.output_text.delta', payload)
                        yield f"data: {_sse_json(payload)}\n\n"
                        continue

                    if chunk.get("type") == "password_request":
                        is_password_request = chunk.get('is_password_request', False)
                        
                        payload = {
                            "type": "password_request",
                            "is_password_request": is_password_request,
                        }
                        _sse_log('password_request', payload)
                        yield f"data: {_sse_json(payload)}\n\n"
                        continue

                    if chunk.get("type") == "response.completed":
                        payload = {'type': 'response.completed'}
                        _sse_log('response.completed', payload)
                        yield f"data: {_sse_json(payload)}\n\n"
                        continue
                    
                    if chunk.get("type") == "error":
                        error_message = chunk.get('message', 'Unknown error')
                        logger.error(f"onboarding_stream_message: Error chunk received: {error_message}")
                        yield f"data: {_sse_json(chunk)}\n\n"
                        continue
                    
            except Exception as stream_error:
                logger.error(f"onboarding_stream_message: Exception in event_stream for guest_id {guest_id}: {str(stream_error)}", exc_info=True)
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": str(stream_error), 
                        "source": "onboarding_stream_message.event_stream", 
                        "guest_id": guest_id,
                        "message": message,
                        "thread_id": thread_id,
                        "traceback": traceback.format_exc()
                    })
                yield f"data: {_sse_json({'type': 'error', 'message': str(stream_error)})}\n\n"

            yield 'event: close\n\n'

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache, no-transform'
        response['X-Accel-Buffering'] = 'no'
        response["X-Guest-ID"] = guest_id
        return response
        
    except Exception as e:
        logger.error(f"onboarding_stream_message: Unhandled exception: {str(e)}", exc_info=True)
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "onboarding_stream_message.unhandled", 
                    "request_method": request.method if hasattr(request, 'method') else 'unknown',
                    "content_type": request.content_type if hasattr(request, 'content_type') else 'unknown',
                    "traceback": traceback.format_exc()
                })
            except Exception as webhook_error:
                logger.error(f"onboarding_stream_message: Failed to send error to n8n webhook: {str(webhook_error)}")
        
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to process onboarding stream: {str(e)}'
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def onboarding_new_conversation(request):
    """Start a fresh onboarding chat."""
    import traceback
    import requests
    import os
    
    try:
        # Validate request method
        if request.method != 'POST':
            logger.error(f"onboarding_new_conversation: Invalid method {request.method}, expected POST")
            return JsonResponse({
                'status': 'error',
                'message': f'Method {request.method} not allowed. Use POST.'
            }, status=405)
        
        # Check request data access
        try:
            request_data = request.data
        except Exception as data_error:
            logger.error(f"onboarding_new_conversation: Error accessing request.data: {str(data_error)}", exc_info=True)
            # Try to access request.POST as fallback
            try:
                request_data = request.POST
            except Exception as post_error:
                logger.error(f"onboarding_new_conversation: Error accessing request.POST: {str(post_error)}", exc_info=True)
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": f"Data access error: {str(data_error)}, POST error: {str(post_error)}", 
                        "source": "onboarding_new_conversation.data_access", 
                        "request_method": request.method,
                        "content_type": request.content_type,
                        "raw_body": str(request.body),
                        "traceback": traceback.format_exc()
                    })
                return JsonResponse({
                    'status': 'error',
                    'message': 'Unable to parse request data'
                }, status=400)
        
        # Check session access
        try:
            session_data = dict(request.session)
        except Exception as session_error:
            logger.error(f"onboarding_new_conversation: Error accessing session: {str(session_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(session_error), 
                    "source": "onboarding_new_conversation.session_access", 
                    "traceback": traceback.format_exc()
                })
            session_data = {}
        
        # Ensure session exists
        try:
            if not request.session.session_key:
                request.session.create()
        except Exception as session_create_error:
            logger.error(f"onboarding_new_conversation: Error creating session: {str(session_create_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(session_create_error), 
                    "source": "onboarding_new_conversation.session_create", 
                    "traceback": traceback.format_exc()
                })
        
        # Extract guest_id
        try:
            guest_id = request_data.get('guest_id') if hasattr(request_data, 'get') else None
            if not guest_id and hasattr(request, 'session'):
                guest_id = request.session.get('guest_id')

        except Exception as guest_id_error:
            logger.error(f"onboarding_new_conversation: Error extracting guest_id: {str(guest_id_error)}", exc_info=True)
            guest_id = None
        
        # Generate guest_id if needed
        if not guest_id:
            try:
                from meals.meal_assistant_implementation import generate_guest_id
                guest_id = generate_guest_id()
                if hasattr(request, 'session'):
                    request.session['guest_id'] = guest_id
                    request.session.save()

            except Exception as generate_error:
                logger.error(f"onboarding_new_conversation: Error generating guest_id: {str(generate_error)}", exc_info=True)
                # n8n traceback
                n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
                if n8n_traceback_url:
                    requests.post(n8n_traceback_url, json={
                        "error": str(generate_error), 
                        "source": "onboarding_new_conversation.generate_guest_id", 
                        "traceback": traceback.format_exc()
                    })
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to generate guest ID'
                                }, status=500)
        
        # Clear any existing conversation history to prevent context confusion
        try:
            from meals.meal_assistant_implementation import GLOBAL_GUEST_STATE
            if guest_id in GLOBAL_GUEST_STATE:
                del GLOBAL_GUEST_STATE[guest_id]
                logger.info(f"onboarding_new_conversation: Cleared existing conversation history for guest_id={guest_id}")
        except Exception as clear_error:
            logger.warning(f"onboarding_new_conversation: Failed to clear existing history for guest_id={guest_id}: {str(clear_error)}")
            # Don't fail the request for this - just log and continue
        
        # Create OnboardingAssistant
        try:

            from meals.meal_assistant_implementation import OnboardingAssistant
            assistant = OnboardingAssistant(guest_id)

        except Exception as assistant_error:
            logger.error(f"onboarding_new_conversation: Error creating OnboardingAssistant: {str(assistant_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(assistant_error), 
                    "source": "onboarding_new_conversation.create_assistant", 
                    "guest_id": guest_id,
                    "traceback": traceback.format_exc()
                })
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to create onboarding assistant: {str(assistant_error)}'
            }, status=500)
        
        # Reset conversation
        try:

            reset_result = assistant.reset_conversation()

        except Exception as reset_error:
            logger.error(f"onboarding_new_conversation: Error resetting conversation: {str(reset_error)}", exc_info=True)
            # n8n traceback
            n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
            if n8n_traceback_url:
                requests.post(n8n_traceback_url, json={
                    "error": str(reset_error), 
                    "source": "onboarding_new_conversation.reset_conversation", 
                    "guest_id": guest_id,
                    "traceback": traceback.format_exc()
                })
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to reset conversation: {str(reset_error)}'
            }, status=500)
        
        

        return JsonResponse({
            "status": "success",
            "guest_id": guest_id,
            "message": "Onboarding conversation reset successfully."
        })
        
    except Exception as e:
        logger.error(f"onboarding_new_conversation: Unhandled exception: {str(e)}", exc_info=True)
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={
                    "error": str(e), 
                    "source": "onboarding_new_conversation.unhandled", 
                    "request_method": request.method if hasattr(request, 'method') else 'unknown',
                    "content_type": request.content_type if hasattr(request, 'content_type') else 'unknown',
                    "traceback": traceback.format_exc()
                })
            except Exception as webhook_error:
                logger.error(f"onboarding_new_conversation: Failed to send error to n8n webhook: {str(webhook_error)}")
        
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to start new onboarding conversation: {str(e)}'
        }, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_threads(request):
    """
    Debug endpoint to inspect and fix thread data structure issues.
    Shows all threads for the user and their structure.
    """
    try:
        # Get all threads for this user
        threads = ChatThread.objects.filter(user=request.user).order_by('-created_at')
        
        # Collect debug information
        thread_info = []
        for thread in threads:
            # Check the openai_thread_id field structure
            if not isinstance(thread.openai_thread_id, list):
                # Fix if not a list - convert to list
                if thread.openai_thread_id:
                    if isinstance(thread.openai_thread_id, str):
                        thread.openai_thread_id = [thread.openai_thread_id]
                    else:
                        thread.openai_thread_id = [str(thread.openai_thread_id)]
                else:
                    thread.openai_thread_id = []
                thread.save()
                
            # Get history info without full content
            history_count = len(thread.openai_input_history) if thread.openai_input_history else 0
            
            # Create thread info entry
            thread_info.append({
                'id': thread.id,
                'created_at': thread.created_at,
                'is_active': thread.is_active,
                'openai_thread_id': thread.openai_thread_id,
                'latest_response_id': thread.latest_response_id,
                'history_count': history_count
            })
        
        return Response({
            'status': 'success',
            'thread_count': len(thread_info),
            'threads': thread_info
        })
    except Exception as e:
        logger.error(f"Error in debug_threads: {str(e)}")
        traceback.print_exc()
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

def get_response_id_from_thread(thread):
    """
    Helper function to safely extract a response ID from a ChatThread.
    Handles both list and string formats of openai_thread_id.
    
    Args:
        thread: ChatThread object
    
    Returns:
        String response ID or None if no valid ID found
    """
    # First check for latest_response_id which is always a string
    if thread.latest_response_id:
        return thread.latest_response_id
    
    # If no latest_response_id, try openai_thread_id
    if isinstance(thread.openai_thread_id, list):
        # Pick the most recent (last) ID from the list if it exists
        if thread.openai_thread_id:
            return thread.openai_thread_id[-1]
        return None
    elif thread.openai_thread_id:  # If it's a string
        return thread.openai_thread_id
    
    return None

def preview_assistant_email(request):
    """DEBUG-only: Render assistant email templates locally without sending emails.
    Query params:
      - key: template_key (e.g., shopping_list, emergency_supply, system_update,
             payment_confirmation, refund_notification, order_cancellation)
      - user_id: optional; defaults to current user
      - meal_plan_id: for shopping_list to use real data
      - order_id: for payment/refund/cancellation contexts
    """
    if not settings.DEBUG:
        return HttpResponseForbidden("Previews are only available in DEBUG mode.")

    template_key = request.GET.get('key') or request.GET.get('template_key') or 'system_update'

    # Resolve user (optional)
    user = None
    try:
        user_id_param = request.GET.get('user_id')
        if user_id_param:
            user = CustomUser.objects.get(id=int(user_id_param))
        elif getattr(request.user, 'is_authenticated', False):
            user = request.user
    except Exception:
        user = None

    # Compute safe display name
    safe_user_name = 'there'
    if user is not None:
        try:
            full_name = getattr(user, 'get_full_name', None)
            if callable(full_name):
                fn = full_name()
                if fn:
                    safe_user_name = fn
            if safe_user_name == 'there':
                uname = getattr(user, 'username', None)
                if not uname and hasattr(user, 'get_username'):
                    try:
                        uname = user.get_username()
                    except Exception:
                        uname = None
                if uname:
                    safe_user_name = uname
        except Exception:
            pass

    # Base section HTML if the template-specific context doesn't fully populate sections
    section_html = {
        'main': '<p>Sample main content</p>',
        'data': '<p>No structured data provided.</p>',
        'final': '<p>Thanks for using sautai.</p>',
    }

    extra_ctx = {}

    # Build context by template_key
    if template_key == 'shopping_list':
        # Provide a sample categorized shopping table
        sample_tables = [
            {
                'category': 'Produce',
                'items': [
                    {'ingredient': 'Spinach', 'quantity': '2', 'unit': 'bunches', 'notes': ''},
                    {'ingredient': 'Bananas', 'quantity': '6', 'unit': 'pieces', 'notes': ''},
                    {'ingredient': 'Cherry Tomatoes', 'quantity': '1', 'unit': 'pint', 'notes': ''},
                ],
            },
            {
                'category': 'Dairy',
                'items': [
                    {'ingredient': 'Greek Yogurt', 'quantity': '32', 'unit': 'oz', 'notes': ''},
                    {'ingredient': 'Cheddar Cheese', 'quantity': '8', 'unit': 'oz', 'notes': ''},
                ],
            },
            {
                'category': 'Meat',
                'items': [
                    {'ingredient': 'Chicken Breast', 'quantity': '2', 'unit': 'lb', 'notes': ''},
                    {'ingredient': 'Ground Turkey', 'quantity': '1', 'unit': 'lb', 'notes': ''},
                ],
            },
            {
                'category': 'Grains',
                'items': [
                    {'ingredient': 'Brown Rice', 'quantity': '2', 'unit': 'lb', 'notes': ''},
                    {'ingredient': 'Whole Wheat Bread', 'quantity': '1', 'unit': 'loaf', 'notes': ''},
                ],
            },
            {
                'category': 'Frozen',
                'items': [
                    {'ingredient': 'Mixed Vegetables', 'quantity': '16', 'unit': 'oz', 'notes': ''},
                    {'ingredient': 'Berries', 'quantity': '12', 'unit': 'oz', 'notes': ''},
                ],
            },
            {
                'category': 'Condiments',
                'items': [
                    {'ingredient': 'Olive Oil', 'quantity': '16', 'unit': 'oz', 'notes': ''},
                    {'ingredient': 'Balsamic Vinegar', 'quantity': '8', 'unit': 'oz', 'notes': ''},
                ],
            },
            {
                'category': 'Snacks',
                'items': [
                    {'ingredient': 'Almonds', 'quantity': '12', 'unit': 'oz', 'notes': ''},
                    {'ingredient': 'Whole Grain Crackers', 'quantity': '1', 'unit': 'box', 'notes': ''},
                ],
            },
            {
                'category': 'Beverages',
                'items': [
                    {'ingredient': 'Sparkling Water', 'quantity': '12', 'unit': 'cans', 'notes': ''},
                ],
            },
            {
                'category': 'Bakery',
                'items': [
                    {'ingredient': 'Whole Wheat Tortillas', 'quantity': '10', 'unit': 'pieces', 'notes': ''},
                ],
            },
            {
                'category': 'Miscellaneous',
                'items': [
                    {'ingredient': 'Sea Salt', 'quantity': '1', 'unit': 'jar', 'notes': ''},
                    {'ingredient': 'Black Pepper', 'quantity': '1', 'unit': 'jar', 'notes': ''},
                ],
            },
        ]

        extra_ctx.update({
            'has_categories': True,
            'household_member_count': (getattr(user, 'household_member_count', None) or 2) if user is not None else 2,
            'week_start': (timezone.now().date()).strftime('%B %d, %Y'),
            'week_end': (timezone.now().date() + timedelta(days=6)).strftime('%B %d, %Y'),
            'shopping_tables': sample_tables,
        })

    elif template_key == 'daily_prep_instructions':
        # Sample based on a typical daily prep structure
        extra_ctx.update({
            'sections_by_day': {
                'Monday': [
                    {'meal_type': 'Dinner', 'description': 'Thaw <strong>chicken breast</strong> in the refrigerator.'},
                    {'meal_type': 'Lunch', 'description': 'Cook <strong>brown rice</strong> (2 cups dry) for the week and refrigerate.'},
                    {'meal_type': 'Lunch', 'description': 'Wash and chop <strong>spinach</strong> and <strong>cherry tomatoes</strong>.'}
                ],
                'Tuesday': [
                    {'meal_type': 'Dinner', 'description': 'Marinate chicken with <em>olive oil</em>, garlic, and herbs (20 min).'},
                    {'meal_type': 'Dinner', 'description': 'Roast <strong>mixed vegetables</strong> at 400°F (200°C) for 20–25 min.'}
                ],
                'Wednesday': [
                    {'meal_type': 'Breakfast', 'description': 'Prepare <strong>Greek yogurt</strong> parfait jars with berries and almonds (3 jars).'}
                ],
                'Thursday': [
                    {'meal_type': 'Dinner', 'description': 'Cook <strong>ground turkey</strong> and season to taste; store for tacos/wraps.'}
                ],
                'Friday': [
                    {'meal_type': 'Lunch', 'description': 'Top‑up rice if needed (1 cup dry).'},
                    {'meal_type': 'Dinner', 'description': 'Make <strong>balsamic vinaigrette</strong> (olive oil + vinegar).'} 
                ],
            }
        })

    elif template_key == 'bulk_prep_instructions':
        # Sample grouped prep in batches
        extra_ctx.update({
            'batch_sections': {
                'Proteins': [
                    'Grill chicken breasts: season with salt, pepper, olive oil. Grill 6–7 min/side.',
                    'Brown ground turkey in skillet; drain and season. Portion into 3 containers.'
                ],
                'Carbs': [
                    'Cook brown rice in rice cooker (2:1 water:rice). Fluff and cool.',
                    'Warm whole wheat tortillas in a dry pan, stack, and wrap in foil.'
                ],
                'Veggies': [
                    'Roast mixed vegetables (broccoli, carrots, peppers) at 400°F for 20–25 minutes.',
                    'Rinse and portion salad greens; store with paper towel to keep crisp.'
                ]
            }
        })

    elif template_key == 'emergency_supply':
        # Sample derived from EmergencySupplyItem schema
        extra_ctx.update({
            'supplies_by_category': [
                {
                    'category': 'Water & Beverages',
                    'items': [
                        {'ingredient': 'Bottled Water', 'quantity': '10', 'unit': 'liters', 'notes': 'At least 1 gal/person/day'},
                        {'ingredient': 'Electrolyte Drink', 'quantity': '6', 'unit': 'bottles', 'notes': ''},
                    ]
                },
                {
                    'category': 'Canned & Dry Goods',
                    'items': [
                        {'ingredient': 'Canned Beans', 'quantity': '8', 'unit': 'cans', 'notes': 'Easy‑open lids preferred'},
                        {'ingredient': 'Peanut Butter', 'quantity': '1', 'unit': 'jar', 'notes': 'If nut‑free household, swap for seed butter'},
                        {'ingredient': 'Rice', 'quantity': '5', 'unit': 'lb', 'notes': ''},
                    ]
                },
                {
                    'category': 'Medical & Misc',
                    'items': [
                        {'ingredient': 'First Aid Kit', 'quantity': '1', 'unit': None, 'notes': 'Bandages, antiseptics, medications'},
                        {'ingredient': 'Flashlight + Batteries', 'quantity': '2', 'unit': 'sets', 'notes': ''},
                    ]
                },
            ]
        })

    elif template_key in ('emergency_supply', 'system_update', 'payment_confirmation', 'refund_notification', 'order_cancellation'):
        # These rely mostly on main/data/final wrappers; leave defaults but allow caller to inject
        pass

    # Render the per-section wrappers
    rendered_sections, css_classes = render_email_sections(
        template_key=template_key,
        section_html=section_html,
        extra_context=extra_ctx,
    )

    # Final email shell
    html = render_to_string(
        'customer_dashboard/assistant_email_template.html',
        {
            'user_name': safe_user_name,
            'email_body_main': rendered_sections['main'],
            'email_body_data': rendered_sections['data'],
            'email_body_final': rendered_sections['final'],
            'profile_url': request.build_absolute_uri('/'),
            'personal_assistant_email': getattr(user, 'personal_assistant_email', None) if user is not None else None,
            'css_classes': css_classes,
        }
    )

    return HttpResponse(html)

def preview_index(request):
    """Simple index of available assistant email previews (DEBUG-only)."""
    if not settings.DEBUG:
        return HttpResponseForbidden("Previews are only available in DEBUG mode.")

    # Try to pick a default MealPlan for convenience when authenticated
    default_meal_plan_id = None
    try:
        if getattr(request.user, 'is_authenticated', False):
            mp = MealPlan.objects.filter(user=request.user).order_by('-created_date').first()
            if mp:
                default_meal_plan_id = mp.id
    except Exception:
        default_meal_plan_id = None

    return render(request, 'customer_dashboard/preview_index.html', {
        'default_meal_plan_id': default_meal_plan_id,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsCustomer])
def api_stream_user_summary(request):
    """
    Stream the user summary generation process.
    
    Returns:
        StreamingHttpResponse: A streaming response with events for the summary generation process
    """
    # Get optional date parameter (defaults to today in user's timezone if not provided)
    summary_date = request.GET.get('date', None)
    
    # Initialize the assistant with the authenticated user
    assistant = MealPlanningAssistant(user_id=request.user.id)
    
    # Create a generator function that yields SSE-formatted events
    def event_stream():
        try:
            for event in assistant.stream_user_summary(summary_date):
                # Format as SSE event
                event_json = json.dumps(event)
                yield f"data: {event_json}\n\n"
        except Exception as e:
            error_event = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_event}\n\n"
        finally:
            # End of stream
            yield f"data: {json.dumps({'type': 'end'})}\n\n"
    
    # Return a streaming response
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    # Add required headers for SSE
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'  # For Nginx
    
    return response
