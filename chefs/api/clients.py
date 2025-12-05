"""
Chef Client Management API endpoints.

Provides endpoints for managing chef-customer relationships and interactions.
"""

import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from chefs.models import Chef
from chef_services.models import ChefCustomerConnection
from custom_auth.models import CustomUser
from crm.models import Lead, LeadInteraction
from chefs.services import get_client_stats, get_client_list_with_stats
from .serializers import (
    ClientListItemSerializer,
    ClientDetailSerializer,
    ClientNoteInputSerializer,
    ClientNoteSerializer,
)

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """
    Get the Chef instance for the authenticated user.
    Returns (chef, None) on success, (None, Response) on failure.
    """
    try:
        chef = Chef.objects.get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access client management."},
            status=403
        )


class ClientPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_list(request):
    """
    GET /api/chefs/me/clients/
    
    Returns paginated list of connected customers with basic stats.
    
    Query Parameters:
    - search: Search by username, email, or name
    - status: Filter by connection status (accepted, pending, declined, ended)
    - ordering: Sort field (connected_since, total_spent, total_orders, -connected_since, etc.)
    - page: Page number
    - page_size: Items per page (default: 20, max: 100)
    
    Response:
    ```json
    {
        "count": 24,
        "next": "...",
        "previous": null,
        "results": [
            {
                "customer_id": 42,
                "username": "johndoe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "connection_status": "accepted",
                "connected_since": "2024-01-15T10:30:00Z",
                "total_orders": 12,
                "total_spent": 450.00
            }
        ]
    }
    ```
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    try:
        # Get query params
        search = request.query_params.get('search', None)
        status = request.query_params.get('status', None)
        ordering = request.query_params.get('ordering', '-connected_since')
        
        # Get client list with stats
        clients = get_client_list_with_stats(chef, search=search, status=status)
        
        # Apply ordering
        reverse = ordering.startswith('-')
        sort_field = ordering.lstrip('-')
        
        valid_sort_fields = ['connected_since', 'total_spent', 'total_orders', 'username']
        if sort_field in valid_sort_fields:
            clients = sorted(
                clients,
                key=lambda x: x.get(sort_field) or ('' if sort_field == 'username' else 0),
                reverse=reverse
            )
        
        # Paginate
        paginator = ClientPagination()
        page = paginator.paginate_queryset(clients, request)
        
        if page is not None:
            serializer = ClientListItemSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ClientListItemSerializer(clients, many=True)
        return Response(serializer.data)
        
    except Exception as e:
        logger.exception(f"Error fetching client list for chef {chef.id}: {e}")
        return Response(
            {"error": "Failed to fetch client list. Please try again."},
            status=500
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def client_detail(request, customer_id):
    """
    GET /api/chefs/me/clients/{customer_id}/
    
    Returns detailed information about a specific client including:
    - Profile information
    - Connection status
    - Order statistics
    - Dietary preferences and allergies
    - Favorite services
    - Recent interaction notes
    
    Response:
    ```json
    {
        "customer_id": 42,
        "username": "johndoe",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "connection_status": "accepted",
        "connected_since": "2024-01-15T10:30:00Z",
        "total_orders": 12,
        "total_spent": 450.00,
        "last_order_date": "2024-03-01T14:00:00Z",
        "average_order_value": 37.50,
        "dietary_preferences": ["Vegetarian", "Gluten-Free"],
        "allergies": ["Peanuts"],
        "household_size": 3,
        "favorite_services": [{"id": 1, "name": "Weekly Meal Prep", "order_count": 8}],
        "notes": [...]
    }
    ```
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    # Verify customer exists
    try:
        customer = CustomUser.objects.get(id=customer_id)
    except CustomUser.DoesNotExist:
        return Response({"error": "Customer not found."}, status=404)
    
    try:
        connection = ChefCustomerConnection.objects.filter(
            chef=chef,
            customer=customer
        ).first()
        
        if not connection:
            return Response(
                {"error": "No connection found with this customer."},
                status=404
            )
        
        # Get client stats
        stats = get_client_stats(chef, customer)
        
        # Build response data
        data = {
            "customer_id": customer.id,
            "username": customer.username,
            "email": customer.email,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "connection_status": connection.status,
            "connected_since": connection.responded_at or connection.requested_at,
            **stats,
        }
        
        serializer = ClientDetailSerializer(data)
        return Response(serializer.data)
        
    except Exception as e:
        logger.exception(f"Error fetching client detail for chef {chef.id}, customer {customer_id}: {e}")
        return Response(
            {"error": "Failed to fetch client details. Please try again."},
            status=500
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def client_notes(request, customer_id):
    """
    GET /api/chefs/me/clients/{customer_id}/notes/
    Returns interaction notes for a client.
    
    POST /api/chefs/me/clients/{customer_id}/notes/
    Adds a new interaction note for a client.
    
    POST Body:
    ```json
    {
        "summary": "Discussed weekly menu preferences",
        "details": "Client prefers more vegetarian options...",
        "interaction_type": "call",
        "next_steps": "Send updated menu by Friday"
    }
    ```
    
    Response (POST):
    ```json
    {
        "id": 123,
        "interaction_type": "call",
        "summary": "Discussed weekly menu preferences",
        "details": "Client prefers more vegetarian options...",
        "happened_at": "2024-03-15T10:30:00Z",
        "next_steps": "Send updated menu by Friday",
        "author_name": "chefmike",
        "created_at": "2024-03-15T10:30:00Z"
    }
    ```
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    # Verify customer exists
    try:
        customer = CustomUser.objects.get(id=customer_id)
    except CustomUser.DoesNotExist:
        return Response({"error": "Customer not found."}, status=404)
    
    try:
        connection = ChefCustomerConnection.objects.filter(
            chef=chef,
            customer=customer
        ).first()
        
        if not connection:
            return Response(
                {"error": "No connection found with this customer."},
                status=404
            )
        
        # Get or create a Lead for this customer-chef relationship
        lead, _ = Lead.objects.get_or_create(
            owner=chef.user,
            email=customer.email,
            defaults={
                'first_name': customer.first_name or customer.username,
                'last_name': customer.last_name or '',
                'status': Lead.Status.WON,  # Existing connection = won lead
                'source': Lead.Source.WEB,
            }
        )
        
        if request.method == 'GET':
            # Return existing notes
            notes = LeadInteraction.objects.filter(
                lead=lead,
                is_deleted=False
            ).order_by('-happened_at')
            
            serializer = ClientNoteSerializer(notes, many=True)
            return Response(serializer.data)
        
        # POST - Create new note
        input_serializer = ClientNoteInputSerializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(input_serializer.errors, status=400)
        
        data = input_serializer.validated_data
        
        note = LeadInteraction.objects.create(
            lead=lead,
            author=request.user,
            interaction_type=data['interaction_type'],
            summary=data['summary'],
            details=data.get('details', ''),
            next_steps=data.get('next_steps', ''),
            happened_at=timezone.now(),
        )
        
        output_serializer = ClientNoteSerializer(note)
        return Response(output_serializer.data, status=201)
        
    except Exception as e:
        logger.exception(f"Error managing client notes for chef {chef.id}, customer {customer_id}: {e}")
        return Response(
            {"error": "Failed to manage client notes. Please try again."},
            status=500
        )


