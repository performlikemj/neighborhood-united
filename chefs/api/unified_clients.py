"""
Unified Clients API - Combines platform users and manual contacts.

Provides a single view of all clients a chef works with, regardless of
whether they're registered on the platform or manually tracked.
"""

import logging
from django.db.models import Q, Value, CharField, IntegerField
from django.db.models.functions import Concat, Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from chefs.models import Chef
from chef_services.models import ChefCustomerConnection
from crm.models import Lead
from custom_auth.models import CustomUser, HouseholdMember

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """Get the Chef instance for the authenticated user."""
    try:
        chef = Chef.objects.get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access clients."},
            status=403
        )


class UnifiedClientPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _serialize_platform_client(connection, customer):
    """Serialize a platform user client."""
    # Get dietary preferences
    dietary_prefs = list(customer.dietary_preferences.values_list('name', flat=True))
    allergies = customer.allergies if customer.allergies else []
    
    # Get household members
    household_members = []
    for member in customer.household_members.all():
        member_prefs = list(member.dietary_preferences.values_list('name', flat=True))
        household_members.append({
            'id': f'platform_member_{member.id}',
            'name': member.name,
            'age': member.age,
            'relationship': None,  # Platform HouseholdMember doesn't have this
            'dietary_preferences': member_prefs,
            'allergies': [],  # Platform members don't have separate allergies
            'notes': member.notes or '',
        })
    
    return {
        'id': f'platform_{customer.id}',
        'source_type': 'platform',
        'source_label': 'Platform User',
        
        # Identity
        'name': f"{customer.first_name} {customer.last_name}".strip() or customer.username,
        'first_name': customer.first_name,
        'last_name': customer.last_name,
        'email': customer.email,
        'phone': customer.phone_number or '',
        
        # Connection info
        'status': connection.status if connection else 'unknown',
        'connected_since': connection.requested_at.isoformat() if connection and connection.requested_at else None,
        'last_activity': customer.last_login.isoformat() if customer.last_login else None,
        
        # Dietary
        'dietary_preferences': dietary_prefs,
        'allergies': allergies,
        'custom_allergies': customer.custom_allergies if hasattr(customer, 'custom_allergies') else [],
        
        # Household
        'household_size': customer.household_member_count,
        'household_members': household_members,
        
        # Notes (from connection if available)
        'notes': connection.notes if connection and hasattr(connection, 'notes') else '',
        
        # Platform-specific
        'customer_id': customer.id,
        'has_orders': True,  # Can check ChefMealOrder/ChefServiceOrder if needed
    }


def _serialize_manual_contact(lead):
    """Serialize a manual contact (Lead)."""
    # Get household members
    household_members = []
    for member in lead.household_members.all():
        household_members.append({
            'id': f'contact_member_{member.id}',
            'name': member.name,
            'age': member.age,
            'relationship': member.relationship,
            'dietary_preferences': member.dietary_preferences or [],
            'allergies': member.allergies or [],
            'custom_allergies': member.custom_allergies or [],
            'notes': member.notes or '',
        })
    
    return {
        'id': f'contact_{lead.id}',
        'source_type': 'contact',
        'source_label': 'Manual Contact',
        
        # Identity
        'name': f"{lead.first_name} {lead.last_name}".strip(),
        'first_name': lead.first_name,
        'last_name': lead.last_name,
        'email': lead.email or '',
        'phone': lead.phone or '',
        
        # Connection info
        'status': lead.status,
        'connected_since': lead.created_at.isoformat() if lead.created_at else None,
        'last_activity': lead.last_interaction_at.isoformat() if lead.last_interaction_at else None,
        
        # Dietary
        'dietary_preferences': lead.dietary_preferences or [],
        'allergies': lead.allergies or [],
        'custom_allergies': lead.custom_allergies or [],
        
        # Household
        'household_size': lead.household_size,
        'household_members': household_members,
        
        # Notes
        'notes': lead.notes or '',
        
        # Contact-specific
        'lead_id': lead.id,
        'has_orders': False,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unified_client_list(request):
    """
    GET /api/chefs/me/all-clients/
    
    Returns a unified list of all clients - both platform users
    and manually tracked contacts.
    
    Query Parameters:
    - source: Filter by source ('platform', 'contact', or omit for all)
    - search: Search by name or email
    - dietary: Filter by dietary preference (e.g., 'Vegan')
    - allergy: Filter by allergy (e.g., 'Peanuts')
    - ordering: Sort field ('name', '-name', 'connected_since', '-connected_since', '-last_activity')
    - page: Page number
    - page_size: Items per page (default: 20)
    
    Response:
    ```json
    {
        "count": 25,
        "next": "...",
        "previous": null,
        "summary": {
            "total": 25,
            "platform": 10,
            "contacts": 15,
            "dietary_breakdown": {"Vegan": 5, "Gluten-Free": 3},
            "allergy_breakdown": {"Peanuts": 4, "Shellfish": 2}
        },
        "results": [
            {
                "id": "platform_123",
                "source_type": "platform",
                "name": "John Doe",
                "dietary_preferences": ["Vegan"],
                "allergies": ["Peanuts"],
                "household_size": 4,
                "household_members": [...]
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
        source_filter = request.query_params.get('source')
        search = request.query_params.get('search', '').strip()
        dietary_filter = request.query_params.get('dietary')
        allergy_filter = request.query_params.get('allergy')
        ordering = request.query_params.get('ordering', '-connected_since')
        
        # =================================================================
        # STEP 1: Calculate TOTAL summary stats (before any source filter)
        # This ensures stats always show total counts regardless of filter
        # =================================================================
        total_platform_count = 0
        total_contact_count = 0
        total_dietary_breakdown = {}
        total_allergy_breakdown = {}
        
        # Count all platform clients
        all_connections = ChefCustomerConnection.objects.filter(
            chef=chef,
            status='accepted'
        ).select_related('customer')
        
        for conn in all_connections:
            customer = conn.customer
            if not customer:
                continue
            total_platform_count += 1
            # Aggregate dietary/allergy for summary
            for pref in customer.dietary_preferences.values_list('name', flat=True):
                total_dietary_breakdown[pref] = total_dietary_breakdown.get(pref, 0) + 1
            for allergy in (customer.allergies or []):
                if allergy and allergy != 'None':
                    total_allergy_breakdown[allergy] = total_allergy_breakdown.get(allergy, 0) + 1
        
        # Count all manual contacts
        all_leads = Lead.objects.filter(
            owner=chef.user,
            is_deleted=False,
            status='won'
        )
        
        for lead in all_leads:
            total_contact_count += 1
            for pref in (lead.dietary_preferences or []):
                total_dietary_breakdown[pref] = total_dietary_breakdown.get(pref, 0) + 1
            for allergy in (lead.allergies or []):
                if allergy and allergy != 'None':
                    total_allergy_breakdown[allergy] = total_allergy_breakdown.get(allergy, 0) + 1
        
        # =================================================================
        # STEP 2: Build filtered results list (applies source filter)
        # =================================================================
        unified_clients = []
        
        # Get platform clients (if not filtered to contacts only)
        if not source_filter or source_filter == 'platform':
            connections = ChefCustomerConnection.objects.filter(
                chef=chef,
                status='accepted'
            ).select_related('customer')
            
            for conn in connections:
                customer = conn.customer
                if not customer:
                    continue
                
                # Apply search filter
                if search:
                    full_name = f"{customer.first_name} {customer.last_name}".lower()
                    if search.lower() not in full_name and search.lower() not in customer.email.lower():
                        continue
                
                client_data = _serialize_platform_client(conn, customer)
                
                # Apply dietary filter
                if dietary_filter and dietary_filter not in client_data['dietary_preferences']:
                    # Also check household members
                    has_dietary = any(
                        dietary_filter in m.get('dietary_preferences', [])
                        for m in client_data['household_members']
                    )
                    if not has_dietary:
                        continue
                
                # Apply allergy filter
                if allergy_filter and allergy_filter not in client_data['allergies']:
                    has_allergy = any(
                        allergy_filter in m.get('allergies', [])
                        for m in client_data['household_members']
                    )
                    if not has_allergy:
                        continue
                
                unified_clients.append(client_data)
        
        # Get manual contacts (if not filtered to platform only)
        if not source_filter or source_filter == 'contact':
            leads = Lead.objects.filter(
                owner=chef.user,
                is_deleted=False,
                status='won'  # Only "won" leads are actual clients
            ).prefetch_related('household_members')
            
            for lead in leads:
                # Apply search filter
                if search:
                    full_name = f"{lead.first_name} {lead.last_name}".lower()
                    if search.lower() not in full_name and search.lower() not in (lead.email or '').lower():
                        continue
                
                client_data = _serialize_manual_contact(lead)
                
                # Apply dietary filter
                if dietary_filter and dietary_filter not in client_data['dietary_preferences']:
                    has_dietary = any(
                        dietary_filter in m.get('dietary_preferences', [])
                        for m in client_data['household_members']
                    )
                    if not has_dietary:
                        continue
                
                # Apply allergy filter
                if allergy_filter and allergy_filter not in client_data['allergies']:
                    has_allergy = any(
                        allergy_filter in m.get('allergies', [])
                        for m in client_data['household_members']
                    )
                    if not has_allergy:
                        continue
                
                unified_clients.append(client_data)
        
        # Sort results
        reverse = ordering.startswith('-')
        sort_key = ordering.lstrip('-')
        
        def get_sort_value(client):
            if sort_key == 'name':
                return client['name'].lower()
            elif sort_key == 'connected_since':
                return client['connected_since'] or ''
            elif sort_key == 'last_activity':
                return client['last_activity'] or ''
            elif sort_key == 'household_size':
                return client['household_size']
            return client['name'].lower()
        
        unified_clients.sort(key=get_sort_value, reverse=reverse)
        
        # Paginate
        paginator = UnifiedClientPagination()
        page = paginator.paginate_queryset(unified_clients, request)
        
        if page is not None:
            response_data = paginator.get_paginated_response(page).data
            response_data['summary'] = {
                # Use TOTAL counts (not filtered) so stats remain constant
                'total': total_platform_count + total_contact_count,
                'platform': total_platform_count,
                'contacts': total_contact_count,
                'dietary_breakdown': dict(sorted(total_dietary_breakdown.items(), key=lambda x: -x[1])[:10]),
                'allergy_breakdown': dict(sorted(total_allergy_breakdown.items(), key=lambda x: -x[1])[:10]),
            }
            return Response(response_data)
        
        return Response({
            'count': len(unified_clients),
            'next': None,
            'previous': None,
            'summary': {
                # Use TOTAL counts (not filtered) so stats remain constant
                'total': total_platform_count + total_contact_count,
                'platform': total_platform_count,
                'contacts': total_contact_count,
                'dietary_breakdown': total_dietary_breakdown,
                'allergy_breakdown': total_allergy_breakdown,
            },
            'results': unified_clients
        })
        
    except Exception as e:
        logger.exception(f"Error fetching unified clients for chef {chef.id}: {e}")
        return Response(
            {"error": "Failed to fetch clients. Please try again."},
            status=500
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unified_client_detail(request, client_id):
    """
    GET /api/chefs/me/all-clients/{client_id}/
    
    Get detailed info for a single client.
    
    The client_id should be prefixed:
    - 'platform_123' for platform users
    - 'contact_456' for manual contacts
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    try:
        if client_id.startswith('platform_'):
            customer_id = int(client_id.replace('platform_', ''))
            connection = ChefCustomerConnection.objects.filter(
                chef=chef,
                customer_id=customer_id,
                status='accepted'
            ).select_related('customer').first()
            
            if not connection or not connection.customer:
                return Response({"error": "Client not found."}, status=404)
            
            return Response(_serialize_platform_client(connection, connection.customer))
        
        elif client_id.startswith('contact_'):
            lead_id = int(client_id.replace('contact_', ''))
            lead = Lead.objects.filter(
                id=lead_id,
                owner=chef.user,
                is_deleted=False
            ).prefetch_related('household_members').first()
            
            if not lead:
                return Response({"error": "Client not found."}, status=404)
            
            return Response(_serialize_manual_contact(lead))
        
        else:
            return Response({"error": "Invalid client ID format."}, status=400)
        
    except (ValueError, TypeError):
        return Response({"error": "Invalid client ID."}, status=400)
    except Exception as e:
        logger.exception(f"Error fetching client {client_id} for chef {chef.id}: {e}")
        return Response(
            {"error": "Failed to fetch client. Please try again."},
            status=500
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dietary_summary(request):
    """
    GET /api/chefs/me/dietary-summary/
    
    Get a summary of all dietary preferences and allergies across all clients.
    Useful for menu planning and understanding client needs.
    
    Response:
    ```json
    {
        "total_clients": 25,
        "total_people": 78,
        "dietary_preferences": {
            "Vegan": {"count": 5, "people": ["John D.", "Jane S. (Child)"]},
            "Gluten-Free": {"count": 8, "people": [...]}
        },
        "allergies": {
            "Peanuts": {"count": 4, "severity": "high", "people": [...]},
            "Shellfish": {"count": 2, "people": [...]}
        },
        "households_with_mixed_diets": 12
    }
    ```
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    try:
        dietary_data = {}  # pref -> list of people
        allergy_data = {}  # allergy -> list of people
        total_people = 0
        households_with_mixed = 0
        
        # Process platform clients
        connections = ChefCustomerConnection.objects.filter(
            chef=chef,
            status='accepted'
        ).select_related('customer')
        
        for conn in connections:
            customer = conn.customer
            if not customer:
                continue
            
            household_diets = set()
            name = f"{customer.first_name} {customer.last_name}".strip() or customer.username
            total_people += 1
            
            # Primary user dietary
            for pref in customer.dietary_preferences.values_list('name', flat=True):
                if pref not in dietary_data:
                    dietary_data[pref] = []
                dietary_data[pref].append(name)
                household_diets.add(pref)
            
            # Primary user allergies
            for allergy in (customer.allergies or []):
                if allergy and allergy != 'None':
                    if allergy not in allergy_data:
                        allergy_data[allergy] = []
                    allergy_data[allergy].append(name)
            
            # Household members
            for member in customer.household_members.all():
                total_people += 1
                member_name = f"{member.name} ({name}'s household)"
                
                for pref in member.dietary_preferences.values_list('name', flat=True):
                    if pref not in dietary_data:
                        dietary_data[pref] = []
                    dietary_data[pref].append(member_name)
                    household_diets.add(pref)
            
            if len(household_diets) > 1:
                households_with_mixed += 1
        
        # Process manual contacts
        leads = Lead.objects.filter(
            owner=chef.user,
            is_deleted=False,
            status='won'
        ).prefetch_related('household_members')
        
        for lead in leads:
            household_diets = set()
            name = f"{lead.first_name} {lead.last_name}".strip()
            total_people += 1
            
            # Primary contact dietary
            for pref in (lead.dietary_preferences or []):
                if pref not in dietary_data:
                    dietary_data[pref] = []
                dietary_data[pref].append(name)
                household_diets.add(pref)
            
            # Primary contact allergies
            for allergy in (lead.allergies or []):
                if allergy and allergy != 'None':
                    if allergy not in allergy_data:
                        allergy_data[allergy] = []
                    allergy_data[allergy].append(name)
            
            # Household members
            for member in lead.household_members.all():
                total_people += 1
                member_name = f"{member.name} ({name}'s household)"
                
                for pref in (member.dietary_preferences or []):
                    if pref not in dietary_data:
                        dietary_data[pref] = []
                    dietary_data[pref].append(member_name)
                    household_diets.add(pref)
                
                for allergy in (member.allergies or []):
                    if allergy and allergy != 'None':
                        if allergy not in allergy_data:
                            allergy_data[allergy] = []
                        allergy_data[allergy].append(member_name)
            
            if len(household_diets) > 1:
                households_with_mixed += 1
        
        # Format response
        total_clients = connections.count() + leads.count()
        
        dietary_summary = {
            pref: {
                'count': len(people),
                'people': people[:5] + (['...'] if len(people) > 5 else [])
            }
            for pref, people in sorted(dietary_data.items(), key=lambda x: -len(x[1]))
        }
        
        allergy_summary = {
            allergy: {
                'count': len(people),
                'people': people[:5] + (['...'] if len(people) > 5 else [])
            }
            for allergy, people in sorted(allergy_data.items(), key=lambda x: -len(x[1]))
        }
        
        return Response({
            'total_clients': total_clients,
            'total_people': total_people,
            'dietary_preferences': dietary_summary,
            'allergies': allergy_summary,
            'households_with_mixed_diets': households_with_mixed,
        })
        
    except Exception as e:
        logger.exception(f"Error fetching dietary summary for chef {chef.id}: {e}")
        return Response(
            {"error": "Failed to fetch dietary summary. Please try again."},
            status=500
        )

