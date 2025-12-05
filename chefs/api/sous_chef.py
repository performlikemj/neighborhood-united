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


def _validate_family_params(request):
    """Validate and extract family_id and family_type from request."""
    family_id = request.data.get('family_id') or request.query_params.get('family_id')
    family_type = request.data.get('family_type') or request.query_params.get('family_type', 'customer')
    
    if not family_id:
        return None, None, Response(
            {"error": "family_id is required"},
            status=400
        )
    
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@renderer_classes([EventStreamRenderer])
def sous_chef_stream_message(request):
    """
    POST /api/chefs/me/sous-chef/stream/
    
    Stream a message to the Sous Chef assistant for a specific family.
    
    Request Body:
    {
        "message": "What should I make for the Johnsons this week?",
        "family_id": 123,
        "family_type": "customer"  // or "lead"
    }
    
    Returns: Server-Sent Events stream
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
    # Verify family exists and chef has access
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
                return Response(
                    {"error": "No active connection with this customer"},
                    status=403
                )
        else:
            # Verify lead exists and belongs to this chef
            lead = Lead.objects.get(id=family_id, owner=chef.user)
    except (CustomUser.DoesNotExist, Lead.DoesNotExist):
        return Response({"error": "Family not found"}, status=404)
    
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
    
    Send a message and get a complete response (non-streaming).
    
    Request Body:
    {
        "message": "What are the Johnsons' dietary restrictions?",
        "family_id": 123,
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
    
    family_id, family_type, error_response = _validate_family_params(request)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
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
    
    Send a message and get a structured JSON response.
    Uses OpenAI's structured output for consistent formatting.
    
    Request Body:
    {
        "message": "What should I make for the Johnsons this week?",
        "family_id": 123,
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
    
    family_id, family_type, error_response = _validate_family_params(request)
    if error_response:
        return error_response
    
    message = request.data.get('message', '').strip()
    if not message:
        return Response({"error": "message is required"}, status=400)
    
    # Verify family exists and chef has access
    try:
        if family_type == 'customer':
            from chef_services.models import ChefCustomerConnection
            customer = CustomUser.objects.get(id=family_id)
            connection = ChefCustomerConnection.objects.filter(
                chef=chef,
                customer=customer,
                status=ChefCustomerConnection.STATUS_ACCEPTED
            ).exists()
            if not connection:
                return Response(
                    {"error": "No active connection with this customer"},
                    status=403
                )
        else:
            lead = Lead.objects.get(id=family_id, owner=chef.user)
    except (CustomUser.DoesNotExist, Lead.DoesNotExist):
        return Response({"error": "Family not found"}, status=404)
    
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
    
    Start a new conversation with the Sous Chef for a specific family.
    This deactivates any existing active thread and creates a fresh one.
    
    Request Body:
    {
        "family_id": 123,
        "family_type": "customer"
    }
    
    Response:
    {
        "status": "success",
        "thread_id": 789,
        "family_name": "Johnson Family"
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    family_id, family_type, error_response = _validate_family_params(request)
    if error_response:
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
    
    Get conversation history for a specific family.
    
    Response:
    {
        "status": "success",
        "thread_id": 789,
        "family_name": "Johnson Family",
        "messages": [
            {
                "role": "chef",
                "content": "What should I make?",
                "created_at": "2024-01-15T10:30:00Z"
            },
            {
                "role": "assistant",
                "content": "Based on the family's preferences...",
                "created_at": "2024-01-15T10:30:05Z"
            }
        ]
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    if family_type not in ('customer', 'lead'):
        return Response({"error": "Invalid family_type"}, status=400)
    
    try:
        family_id = int(family_id)
    except (ValueError, TypeError):
        return Response({"error": "Invalid family_id"}, status=400)
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=family_id,
            family_type=family_type
        )
        
        history = assistant.get_conversation_history()
        thread = assistant._get_or_create_thread()
        
        return Response({
            "status": "success",
            "thread_id": thread.id,
            "family_name": thread.family_name,
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

