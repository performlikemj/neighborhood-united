"""
API endpoints for customer's view of chef-created meal plans.

These endpoints support the collaborative meal planning experience
where customers can view plans and suggest changes.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chef_services.models import ChefCustomerConnection
from meals.models import (
    ChefMealPlan, 
    ChefMealPlanDay, 
    ChefMealPlanItem,
    MealPlanSuggestion
)


def _serialize_plan_item(item):
    """Serialize a ChefMealPlanItem for API response."""
    return {
        'id': item.id,
        'meal_type': item.meal_type,
        'meal_type_display': item.get_meal_type_display(),
        'name': item.display_name,
        'description': item.display_description,
        'servings': item.servings,
        'notes': item.notes,
        'meal_id': item.meal_id,
    }


def _serialize_plan_day(day):
    """Serialize a ChefMealPlanDay for API response."""
    return {
        'id': day.id,
        'date': day.date.isoformat(),
        'is_skipped': day.is_skipped,
        'skip_reason': day.skip_reason,
        'notes': day.notes,
        'items': [_serialize_plan_item(item) for item in day.items.all()],
    }


def _serialize_plan(plan, include_days=False):
    """Serialize a ChefMealPlan for API response."""
    result = {
        'id': plan.id,
        'title': plan.title or f"Meal Plan for {plan.start_date}",
        'start_date': plan.start_date.isoformat(),
        'end_date': plan.end_date.isoformat(),
        'status': plan.status,
        'notes': plan.notes,
        'published_at': plan.published_at.isoformat() if plan.published_at else None,
        'pending_suggestions': plan.pending_suggestions_count,
        'chef': {
            'id': plan.chef.id,
            'username': plan.chef.user.username,
            'display_name': f"{plan.chef.user.first_name} {plan.chef.user.last_name}".strip() or plan.chef.user.username,
        }
    }
    
    if include_days:
        result['days'] = [_serialize_plan_day(day) for day in plan.days.prefetch_related('items').all()]
    
    return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_plans(request):
    """
    Get all active meal plans for the current customer across all chefs.
    
    Query params:
        chef_id: Filter by specific chef (optional)
        status: Filter by status (optional, default: published)
        include_archived: Include archived plans (optional, default: false)
    """
    chef_id = request.query_params.get('chef_id')
    status_filter = request.query_params.get('status', ChefMealPlan.STATUS_PUBLISHED)
    include_archived = request.query_params.get('include_archived', 'false').lower() == 'true'
    
    # Get customer's connected chefs
    connected_chef_ids = ChefCustomerConnection.objects.filter(
        customer=request.user,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    ).values_list('chef_id', flat=True)
    
    plans = ChefMealPlan.objects.filter(
        customer=request.user,
        chef_id__in=connected_chef_ids
    ).select_related('chef__user')
    
    if chef_id:
        plans = plans.filter(chef_id=chef_id)
    
    if not include_archived:
        if status_filter:
            plans = plans.filter(status=status_filter)
        else:
            plans = plans.exclude(status=ChefMealPlan.STATUS_ARCHIVED)
    
    plans = plans.order_by('-start_date')
    
    return Response({
        'plans': [_serialize_plan(plan) for plan in plans],
        'count': plans.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_plan_detail(request, plan_id):
    """
    Get detailed information about a specific meal plan.
    
    Includes all days and items.
    """
    plan = get_object_or_404(
        ChefMealPlan.objects.select_related('chef__user').prefetch_related(
            'days__items__meal'
        ),
        id=plan_id,
        customer=request.user
    )
    
    # Verify customer still has connection with this chef
    connection_exists = ChefCustomerConnection.objects.filter(
        customer=request.user,
        chef=plan.chef,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    ).exists()
    
    if not connection_exists and plan.status != ChefMealPlan.STATUS_ARCHIVED:
        return Response(
            {'error': 'You no longer have a connection with this chef.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    return Response(_serialize_plan(plan, include_days=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_suggestion(request, plan_id):
    """
    Submit a suggestion for a meal plan change.
    
    Request body:
        {
            'suggestion_type': 'swap_meal' | 'skip_day' | 'add_day' | 'dietary_note' | 'general',
            'description': str,
            'target_item_id': int (optional - for swap_meal),
            'target_day_id': int (optional - for skip_day)
        }
    """
    plan = get_object_or_404(
        ChefMealPlan,
        id=plan_id,
        customer=request.user,
        status=ChefMealPlan.STATUS_PUBLISHED
    )
    
    suggestion_type = request.data.get('suggestion_type')
    description = request.data.get('description', '').strip()
    target_item_id = request.data.get('target_item_id')
    target_day_id = request.data.get('target_day_id')
    
    # Validate suggestion type
    valid_types = [choice[0] for choice in MealPlanSuggestion.SUGGESTION_TYPE_CHOICES]
    if suggestion_type not in valid_types:
        return Response(
            {'error': f'Invalid suggestion_type. Must be one of: {", ".join(valid_types)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not description:
        return Response(
            {'error': 'Description is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate target references
    target_item = None
    target_day = None
    
    if target_item_id:
        target_item = get_object_or_404(
            ChefMealPlanItem,
            id=target_item_id,
            day__plan=plan
        )
    
    if target_day_id:
        target_day = get_object_or_404(
            ChefMealPlanDay,
            id=target_day_id,
            plan=plan
        )
    
    # Create the suggestion
    suggestion = MealPlanSuggestion.objects.create(
        plan=plan,
        customer=request.user,
        suggestion_type=suggestion_type,
        description=description,
        target_item=target_item,
        target_day=target_day
    )
    
    return Response({
        'id': suggestion.id,
        'suggestion_type': suggestion.suggestion_type,
        'description': suggestion.description,
        'status': suggestion.status,
        'created_at': suggestion.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_suggestions(request, plan_id):
    """
    Get all suggestions the customer has submitted for a plan.
    """
    plan = get_object_or_404(
        ChefMealPlan,
        id=plan_id,
        customer=request.user
    )
    
    suggestions = plan.suggestions.filter(
        customer=request.user
    ).select_related('target_item', 'target_day').order_by('-created_at')
    
    results = []
    for s in suggestions:
        results.append({
            'id': s.id,
            'suggestion_type': s.suggestion_type,
            'suggestion_type_display': s.get_suggestion_type_display(),
            'description': s.description,
            'status': s.status,
            'status_display': s.get_status_display(),
            'chef_response': s.chef_response,
            'target_item': {
                'id': s.target_item.id,
                'name': s.target_item.display_name,
            } if s.target_item else None,
            'target_day': {
                'id': s.target_day.id,
                'date': s.target_day.date.isoformat(),
            } if s.target_day else None,
            'created_at': s.created_at.isoformat(),
            'reviewed_at': s.reviewed_at.isoformat() if s.reviewed_at else None,
        })
    
    return Response({
        'suggestions': results,
        'count': len(results)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_plan(request):
    """
    Get the current/active meal plan for the customer.
    
    Query params:
        chef_id: Get plan from specific chef (optional)
    
    Returns the most recent published plan that includes today's date,
    or the next upcoming plan if no current plan exists.
    """
    chef_id = request.query_params.get('chef_id')
    today = timezone.now().date()
    
    # Get connected chef IDs
    connected_chef_ids = ChefCustomerConnection.objects.filter(
        customer=request.user,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    ).values_list('chef_id', flat=True)
    
    base_qs = ChefMealPlan.objects.filter(
        customer=request.user,
        chef_id__in=connected_chef_ids,
        status=ChefMealPlan.STATUS_PUBLISHED
    ).select_related('chef__user')
    
    if chef_id:
        base_qs = base_qs.filter(chef_id=chef_id)
    
    # Try to find a plan that includes today
    current_plan = base_qs.filter(
        start_date__lte=today,
        end_date__gte=today
    ).order_by('-start_date').first()
    
    # If no current plan, get the next upcoming one
    if not current_plan:
        current_plan = base_qs.filter(
            start_date__gt=today
        ).order_by('start_date').first()
    
    if not current_plan:
        return Response({'plan': None})
    
    return Response({
        'plan': _serialize_plan(current_plan, include_days=True)
    })


