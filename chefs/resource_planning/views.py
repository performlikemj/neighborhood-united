"""
API Views for Chef Resource Planning.

Provides endpoints for:
- Creating and managing prep plans
- Viewing shopping lists by date or category
- Marking items as purchased
- On-demand shelf life lookups
"""
import logging
from datetime import date, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef
from chefs.resource_planning.models import (
    ChefPrepPlan,
    ChefPrepPlanItem,
)
from chefs.resource_planning.serializers import (
    ChefPrepPlanCreateSerializer,
    ChefPrepPlanDetailSerializer,
    ChefPrepPlanItemSerializer,
    ChefPrepPlanListSerializer,
    MarkPurchasedSerializer,
    ShelfLifeLookupSerializer,
    ShelfLifeResultSerializer,
)
from chefs.resource_planning.services import (
    generate_prep_plan,
    get_shopping_list_by_category,
    get_shopping_list_by_date,
)
from chefs.resource_planning.shelf_life import get_ingredient_shelf_lives

logger = logging.getLogger(__name__)


def _get_chef_or_403(user):
    """Get Chef instance for authenticated user or raise 403."""
    try:
        return user.chef
    except Chef.DoesNotExist:
        return None


# =============================================================================
# Prep Plan CRUD
# =============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def prep_plan_list(request):
    """
    GET: List all prep plans for the authenticated chef.
    POST: Create a new prep plan.
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Get query params for filtering
        status_filter = request.query_params.get('status')
        
        plans = ChefPrepPlan.objects.filter(chef=chef)
        
        if status_filter:
            plans = plans.filter(status=status_filter)
        
        plans = plans.order_by('-plan_start_date')[:20]
        
        serializer = ChefPrepPlanListSerializer(plans, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = ChefPrepPlanCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            prep_plan = generate_prep_plan(
                chef=chef,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                notes=serializer.validated_data.get('notes', '')
            )
            
            return Response(
                ChefPrepPlanDetailSerializer(prep_plan).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Failed to generate prep plan: {e}")
            return Response(
                {'error': f'Failed to generate prep plan: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def prep_plan_detail(request, plan_id):
    """
    GET: Get prep plan details.
    PATCH: Update prep plan (notes, status).
    DELETE: Delete a prep plan.
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    prep_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    if request.method == 'GET':
        serializer = ChefPrepPlanDetailSerializer(prep_plan)
        return Response(serializer.data)
    
    elif request.method == 'PATCH':
        # Only allow updating notes and status
        allowed_fields = {'notes', 'status'}
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        if 'status' in update_data:
            valid_statuses = ['draft', 'generated', 'in_progress', 'completed']
            if update_data['status'] not in valid_statuses:
                return Response(
                    {'error': f'Invalid status. Must be one of: {valid_statuses}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        for key, value in update_data.items():
            setattr(prep_plan, key, value)
        
        prep_plan.save()
        
        return Response(ChefPrepPlanDetailSerializer(prep_plan).data)
    
    elif request.method == 'DELETE':
        prep_plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def prep_plan_regenerate(request, plan_id):
    """
    Regenerate an existing prep plan with fresh data.
    
    Useful when orders change or new commitments are added.
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    old_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    try:
        # Generate new plan with same date range
        new_plan = generate_prep_plan(
            chef=chef,
            start_date=old_plan.plan_start_date,
            end_date=old_plan.plan_end_date,
            notes=old_plan.notes
        )
        
        # Delete old plan
        old_plan.delete()
        
        return Response(
            ChefPrepPlanDetailSerializer(new_plan).data,
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Failed to regenerate prep plan: {e}")
        return Response(
            {'error': f'Failed to regenerate prep plan: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Shopping List Views
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prep_plan_shopping_list(request, plan_id):
    """
    Get shopping list for a prep plan.
    
    Query params:
    - group_by: 'date' or 'category' (default: 'date')
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    prep_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    group_by = request.query_params.get('group_by', 'date')
    
    if group_by == 'category':
        shopping_list = get_shopping_list_by_category(prep_plan)
    else:
        shopping_list = get_shopping_list_by_date(prep_plan)
    
    return Response({
        'plan_id': plan_id,
        'group_by': group_by,
        'shopping_list': shopping_list
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_items_purchased(request, plan_id):
    """
    Mark shopping list items as purchased.
    
    Request body:
    {
        "item_ids": [1, 2, 3],
        "purchased_date": "2024-01-15"  // optional, defaults to today
    }
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    prep_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    serializer = MarkPurchasedSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    item_ids = serializer.validated_data['item_ids']
    purchased_date = serializer.validated_data.get('purchased_date', date.today())
    
    # Update items
    items = ChefPrepPlanItem.objects.filter(
        prep_plan=prep_plan,
        id__in=item_ids
    )
    
    updated_count = items.update(
        is_purchased=True,
        purchased_date=purchased_date
    )
    
    return Response({
        'updated': updated_count,
        'purchased_date': purchased_date.isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unmark_items_purchased(request, plan_id):
    """
    Unmark shopping list items as purchased.
    
    Request body:
    {
        "item_ids": [1, 2, 3]
    }
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    prep_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    item_ids = request.data.get('item_ids', [])
    if not item_ids:
        return Response(
            {'error': 'item_ids is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update items
    items = ChefPrepPlanItem.objects.filter(
        prep_plan=prep_plan,
        id__in=item_ids
    )
    
    updated_count = items.update(
        is_purchased=False,
        purchased_date=None,
        purchased_quantity=None
    )
    
    return Response({'updated': updated_count})


# =============================================================================
# Batch Suggestions
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prep_plan_batch_suggestions(request, plan_id):
    """
    Get batch cooking suggestions for a prep plan.
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    prep_plan = get_object_or_404(ChefPrepPlan, id=plan_id, chef=chef)
    
    return Response({
        'plan_id': plan_id,
        'batch_suggestions': prep_plan.batch_suggestions or {
            'suggestions': [],
            'general_tips': []
        }
    })


# =============================================================================
# Shelf Life Utilities
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def shelf_life_lookup(request):
    """
    Look up shelf life for a list of ingredients.
    
    Request body:
    {
        "ingredients": ["chicken breast", "lettuce", "rice"],
        "storage_preference": "refrigerated"  // optional
    }
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = ShelfLifeLookupSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        response = get_ingredient_shelf_lives(
            ingredient_names=serializer.validated_data['ingredients'],
            storage_preference=serializer.validated_data.get('storage_preference')
        )
        
        results = [
            ShelfLifeResultSerializer(ing).data
            for ing in response.ingredients
        ]
        
        return Response({'ingredients': results})
        
    except Exception as e:
        logger.error(f"Shelf life lookup failed: {e}")
        return Response(
            {'error': f'Failed to look up shelf life: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Quick Actions
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_generate_prep_plan(request):
    """
    Quickly generate a prep plan for the next 7 days.
    
    Convenience endpoint that doesn't require specifying dates.
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    days_ahead = int(request.data.get('days', 7))
    if days_ahead < 1 or days_ahead > 30:
        return Response(
            {'error': 'days must be between 1 and 30'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    today = date.today()
    end_date = today + timedelta(days=days_ahead - 1)
    
    try:
        prep_plan = generate_prep_plan(
            chef=chef,
            start_date=today,
            end_date=end_date,
            notes=request.data.get('notes', '')
        )
        
        return Response(
            ChefPrepPlanDetailSerializer(prep_plan).data,
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"Failed to generate quick prep plan: {e}")
        return Response(
            {'error': f'Failed to generate prep plan: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def prep_plan_summary(request):
    """
    Get a summary of prep planning status for the chef.
    
    Returns:
    - Active plans count
    - Items needing purchase today
    - Upcoming commitments count
    """
    chef = _get_chef_or_403(request.user)
    if not chef:
        return Response(
            {'error': 'You must be a chef to access this resource.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    today = date.today()
    
    # Active plans
    active_plans = ChefPrepPlan.objects.filter(
        chef=chef,
        plan_end_date__gte=today,
        status__in=['generated', 'in_progress']
    ).count()
    
    # Items to purchase today
    items_today = ChefPrepPlanItem.objects.filter(
        prep_plan__chef=chef,
        prep_plan__status__in=['generated', 'in_progress'],
        suggested_purchase_date=today,
        is_purchased=False
    ).count()
    
    # Items overdue (purchase date passed but not purchased)
    items_overdue = ChefPrepPlanItem.objects.filter(
        prep_plan__chef=chef,
        prep_plan__status__in=['generated', 'in_progress'],
        suggested_purchase_date__lt=today,
        is_purchased=False
    ).count()
    
    # Get latest active plan
    latest_plan = ChefPrepPlan.objects.filter(
        chef=chef,
        plan_end_date__gte=today,
        status__in=['generated', 'in_progress']
    ).order_by('-plan_start_date').first()
    
    return Response({
        'active_plans_count': active_plans,
        'items_to_purchase_today': items_today,
        'items_overdue': items_overdue,
        'latest_plan': ChefPrepPlanListSerializer(latest_plan).data if latest_plan else None
    })


