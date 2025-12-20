"""
Sous Chef API endpoints.

Provides streaming and non-streaming endpoints for the family-focused
AI assistant that helps chefs plan and prepare meals.
"""

import json
import logging
import traceback
from typing import Generator

from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import BaseRenderer

from chefs.models import Chef
from customer_dashboard.models import SousChefThread, SousChefMessage
from custom_auth.models import CustomUser
from crm.models import Lead
from shared.utils import generate_family_context_for_chef

logger = logging.getLogger(__name__)


class EventStreamRenderer(BaseRenderer):
    """Renderer for Server-Sent Events (SSE)."""
    media_type = 'text/event-stream'
    format = 'sse'
    charset = 'utf-8'
    
    def render(self, data, media_type=None, renderer_context=None):
        return data


def _get_chef_or_403(request):
    """Get the Chef instance for the authenticated user."""
    try:
        chef = Chef.objects.select_related('user').get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access the Sous Chef assistant."},
            status=403
        )


def _validate_family_params(request, require_family: bool = False):
    """
    Validate and extract family_id and family_type from request.
    
    Args:
        request: The HTTP request
        require_family: If True, family_id is required. If False, returns (None, None, None) when not provided.
    
    Returns:
        (family_id, family_type, error_response) - error_response is None if valid
    """
    family_id = request.data.get('family_id') or request.query_params.get('family_id')
    family_type = request.data.get('family_type') or request.query_params.get('family_type', 'customer')
    
    # If no family_id provided
    if not family_id:
        if require_family:
            return None, None, Response(
                {"error": "family_id is required"},
                status=400
            )
        # General mode - no family selected
        return None, None, None
    
    try:
        family_id = int(family_id)
    except (ValueError, TypeError):
        return None, None, Response(
            {"error": "family_id must be an integer"},
            status=400
        )
    
    if family_type not in ('customer', 'lead'):
        return None, None, Response(
            {"error": "family_type must be 'customer' or 'lead'"},
            status=400
        )
    
    return family_id, family_type, None


def _sse_event(data: dict) -> str:
    """Format data as an SSE event."""
    return f"data: {json.dumps(data)}\n\n"


def _verify_family_access(chef, family_id, family_type):
    """
    Verify that the chef has access to the specified family.
    Returns (success, error_response).
    If family_id is None (general mode), returns (True, None).
    """
    if family_id is None:
        # General mode - no family to verify
        return True, None
    
    try:
        if family_type == 'customer':
            # Verify customer exists and chef has connection
            from chef_services.models import ChefCustomerConnection
            customer = CustomUser.objects.get(id=family_id)
            connection = ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).exists()
            if not connection:
                return False, Response(
                    {"error": "No active connection with this customer"},
                    status=403
                )
        else:
            # Verify lead exists and belongs to this chef
            Lead.objects.get(id=family_id, owner=chef.user)
        return True, None
    except (CustomUser.DoesNotExist, Lead.DoesNotExist):
        return False, Response({"error": "Family not found"}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@renderer_classes([EventStreamRenderer])
def sous_chef_stream_message(request):
    """
    POST /api/chefs/me/sous-chef/stream/
    
    Stream a message to the Sous Chef assistant. Family is optional.
    
    Request Body:
    {
        "message": "What should I make for the Johnsons this week?",
        "family_id": 123,        // optional - omit for general assistant mode
        "family_type": "customer"  // or "lead", required if family_id provided
    }
    
    Returns: Server-Sent Events stream
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request, require_family=False)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
    # Verify family access if family provided
    success, error_response = _verify_family_access(chef, family_id, family_type)
    if not success:
        return error_response
    
    def stream_generator() -> Generator[str, None, None]:
        """Generate SSE events from the assistant."""
        try:
            from meals.sous_chef_assistant import SousChefAssistant
            
            assistant = SousChefAssistant(
                chef_id=chef.id,
                family_id=family_id,
                family_type=family_type
            )
            
            for event in assistant.stream_message(message):
                yield _sse_event(event)
                
        except Exception as e:
            logger.error(f"Sous Chef stream error: {e}")
            logger.error(traceback.format_exc())
            yield _sse_event({"type": "error", "message": str(e)})
            yield _sse_event({"type": "response.completed"})
    
    response = StreamingHttpResponse(
        stream_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sous_chef_send_message(request):
    """
    POST /api/chefs/me/sous-chef/message/
    
    Send a message and get a complete response (non-streaming). Family is optional.
    
    Request Body:
    {
        "message": "What are the Johnsons' dietary restrictions?",
        "family_id": 123,        // optional - omit for general assistant mode
        "family_type": "customer"
    }
    
    Response:
    {
        "status": "success",
        "message": "The Johnson family has the following...",
        "response_id": "resp_xxx",
        "thread_id": 456
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request, require_family=False)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
    # Verify family access if family provided
    success, error_response = _verify_family_access(chef, family_id, family_type)
    if not success:
        return error_response
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=family_id,
            family_type=family_type
        )
        
        result = assistant.send_message(message)
        return Response(result)
        
    except Exception as e:
        logger.error(f"Sous Chef message error: {e}")
        logger.error(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sous_chef_structured_message(request):
    """
    POST /api/chefs/me/sous-chef/structured/
    
    Send a message and get a structured JSON response. Family is optional.
    Uses structured output for consistent formatting.
    
    Request Body:
    {
        "message": "What should I make for the Johnsons this week?",
        "family_id": 123,        // optional - omit for general assistant mode
        "family_type": "customer"
    }
    
    Response:
    {
        "status": "success",
        "content": {
            "blocks": [
                {"type": "text", "content": "Here are three options:"},
                {"type": "table", "headers": ["Option", "Dish"], "rows": [["A", "Salmon"]]},
                {"type": "text", "content": "Let me know your preference!"}
            ]
        },
        "thread_id": 456
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request, require_family=False)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
    # Verify family access if family provided
    success, error_response = _verify_family_access(chef, family_id, family_type)
    if not success:
        return error_response
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=family_id,
            family_type=family_type
        )
        
        result = assistant.send_structured_message(message)
        return Response(result)
        
    except Exception as e:
        logger.error(f"Sous Chef structured message error: {e}")
        logger.error(traceback.format_exc())
        return Response({"status": "error", "message": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sous_chef_new_conversation(request):
    """
    POST /api/chefs/me/sous-chef/new-conversation/
    
    Start a new conversation with the Sous Chef. Family is optional.
    This deactivates any existing active thread and creates a fresh one.
    
    Request Body:
    {
        "family_id": 123,        // optional - omit for general assistant mode
        "family_type": "customer"
    }
    
    Response:
    {
        "status": "success",
        "thread_id": 789,
        "family_name": "Johnson Family"  // or "General Assistant" if no family
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request, require_family=False)
    if error_response:
        return error_response
    
    # Verify family access if family provided
    success, error_response = _verify_family_access(chef, family_id, family_type)
    if not success:
        return error_response
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=family_id,
            family_type=family_type
        )
        
        result = assistant.new_conversation()
        return Response(result)
        
    except Exception as e:
        logger.error(f"Sous Chef new conversation error: {e}")
        return Response({"status": "error", "message": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sous_chef_thread_history(request, family_type, family_id):
    """
    GET /api/chefs/me/sous-chef/history/{family_type}/{family_id}/
    
    Get conversation history for a specific family or general mode.
    Use family_type="general" and family_id=0 for general assistant mode.
    
    Response:
    {
        "status": "success",
        "thread_id": 789,
        "family_name": "Johnson Family",  // or "General Assistant"
        "messages": [...]
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    # Handle general mode (no family)
    if family_type == 'general' and str(family_id) == '0':
        actual_family_id = None
        actual_family_type = None
    else:
        if family_type not in ('customer', 'lead'):
            return Response({"error": "Invalid family_type"}, status=400)
        
        try:
            actual_family_id = int(family_id)
        except (ValueError, TypeError):
            return Response({"error": "Invalid family_id"}, status=400)
        actual_family_type = family_type
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=actual_family_id,
            family_type=actual_family_type
        )
        
        history = assistant.get_conversation_history()
        thread = assistant._get_or_create_thread()
        
        # Get family name or "General Assistant" for no-family mode
        family_name = getattr(thread, 'family_name', None)
        if not family_name and not assistant.has_family_context:
            family_name = "General Assistant"
        
        return Response({
            "status": "success",
            "thread_id": thread.id,
            "family_name": family_name,
            "messages": history
        })
        
    except Exception as e:
        logger.error(f"Sous Chef history error: {e}")
        return Response({"status": "error", "message": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sous_chef_family_context(request, family_type, family_id):
    """
    GET /api/chefs/me/sous-chef/context/{family_type}/{family_id}/
    
    Get the family context summary for display in the UI.
    
    Response:
    {
        "status": "success",
        "family_name": "Johnson Family",
        "household_size": 4,
        "dietary_restrictions": ["Vegetarian", "Gluten-Free"],
        "allergies": ["Peanuts"],
        "members": [...]
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    # Handle general mode (no family)
    if family_type == 'general' and str(family_id) == '0':
        return Response({
            "status": "success",
            "family_name": "General Assistant",
            "family_type": "general",
            "family_id": None,
            "household_size": 0,
            "dietary_restrictions": [],
            "allergies": [],
            "members": [],
            "total_orders": 0,
            "total_spent": 0,
            "is_general_mode": True
        })
    
    if family_type not in ('customer', 'lead'):
        return Response({"error": "Invalid family_type"}, status=400)
    
    try:
        family_id = int(family_id)
    except (ValueError, TypeError):
        return Response({"error": "Invalid family_id"}, status=400)
    
    try:
        customer = None
        lead = None
        
        if family_type == 'customer':
            customer = CustomUser.objects.get(id=family_id)
            family_name = f"{customer.first_name} {customer.last_name}".strip() or customer.username
            household_size = getattr(customer, 'household_member_count', 1)
            
            dietary_restrictions = [p.name for p in customer.dietary_preferences.all()]
            allergies = list(customer.allergies or []) + list(customer.custom_allergies or [])
            
            members = []
            if hasattr(customer, 'household_members'):
                for member in customer.household_members.all():
                    m_prefs = [p.name for p in member.dietary_preferences.all()]
                    members.append({
                        "name": member.name,
                        "age": member.age,
                        "dietary_preferences": m_prefs,
                        "notes": member.notes
                    })
        else:
            lead = Lead.objects.get(id=family_id, owner=chef.user)
            family_name = f"{lead.first_name} {lead.last_name}".strip()
            household_size = lead.household_size
            
            dietary_restrictions = list(lead.dietary_preferences or [])
            allergies = list(lead.allergies or []) + list(lead.custom_allergies or [])
            
            members = []
            for member in lead.household_members.all():
                m_prefs = list(member.dietary_preferences or [])
                m_allergies = list(member.allergies or []) + list(member.custom_allergies or [])
                members.append({
                    "name": member.name,
                    "relationship": member.relationship,
                    "age": member.age,
                    "dietary_preferences": m_prefs,
                    "allergies": m_allergies,
                    "notes": member.notes
                })
        
        # Get stats if customer
        total_orders = 0
        total_spent = 0
        
        if customer:
            from chefs.services import get_client_stats
            stats = get_client_stats(chef, customer)
            total_orders = stats.get('total_orders', 0)
            total_spent = float(stats.get('total_spent', 0))
        
        return Response({
            "status": "success",
            "family_name": family_name,
            "family_type": family_type,
            "family_id": family_id,
            "household_size": household_size,
            "dietary_restrictions": dietary_restrictions,
            "allergies": allergies,
            "members": members,
            "stats": {
                "total_orders": total_orders,
                "total_spent": total_spent
            }
        })
        
    except CustomUser.DoesNotExist:
        return Response({"error": "Customer not found"}, status=404)
    except Lead.DoesNotExist:
        return Response({"error": "Lead not found"}, status=404)
    except Exception as e:
        logger.error(f"Sous Chef context error: {e}")
        return Response({"status": "error", "message": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sous_chef_get_suggestions(request):
    """
    POST /api/chefs/me/sous-chef/suggest/
    
    Get contextual suggestions based on current chef activity.
    Uses a hybrid approach: rule-based suggestions (fast, free) and 
    AI-powered suggestions (for complex scenarios when idle).
    
    Request Body:
    {
        "context": {
            "currentTab": "kitchen",
            "openForms": [{ "type": "dish", "fields": {...}, "completion": 0.4 }],
            "recentActions": ["created_ingredient", "viewed_events"],
            "timeOnScreen": 45000,
            "validationErrors": [],
            "isIdle": false
        }
    }
    
    Response:
    {
        "status": "success",
        "suggestions": [
            {
                "id": "dish_name_suggestion",
                "type": "field",
                "formType": "dish",
                "field": "name",
                "value": "Jamaican Jerk Chicken",
                "reason": "Based on your recent ingredients",
                "priority": "medium"
            },
            {
                "id": "create_first_dish",
                "type": "action",
                "action": "navigate",
                "target": "kitchen",
                "label": "Create your first dish",
                "reason": "Build your menu by adding dishes",
                "priority": "high"
            }
        ],
        "priority": "medium"
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    context = request.data.get('context', {})
    
    if not context:
        return Response({
            "status": "success",
            "suggestions": [],
            "priority": "low"
        })
    
    try:
        from meals.sous_chef_suggestions import SuggestionEngine
        
        engine = SuggestionEngine(chef)
        result = engine.get_suggestions(context)
        
        return Response({
            "status": "success",
            **result
        })
        
    except Exception as e:
        logger.error(f"Sous Chef suggestions error: {e}")
        logger.error(traceback.format_exc())
        return Response({
            "status": "error",
            "message": str(e),
            "suggestions": [],
            "priority": "low"
        }, status=500)
