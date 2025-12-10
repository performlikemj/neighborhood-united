"""
API endpoints for customer's connected chefs (multi-chef support).

These endpoints support the Client Portal experience where customers
can view and interact with their connected chefs.
"""
from django.db.models import Max
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chef_services.models import ChefCustomerConnection
from meals.models import ChefMealPlan, Order


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_chefs(request):
    """
    Get all connected chefs for the current customer, ordered by recent activity.
    
    Single-chef users will get just one chef in the list, which the frontend
    can use for smart redirect to skip the list page.
    
    Returns:
        {
            'chefs': [...],
            'count': int
        }
    """
    connections = ChefCustomerConnection.objects.filter(
        customer=request.user,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    ).annotate(
        last_activity=Coalesce(
            Greatest('last_order_at', 'last_message_at', 'last_plan_update_at'),
            'requested_at'  # Fallback to connection date
        )
    ).select_related('chef__user').order_by('-last_activity')
    
    chefs = []
    for conn in connections:
        chef = conn.chef
        user = chef.user
        
        # Get chef's profile photo URL
        photo_url = None
        if hasattr(chef, 'profile_photo') and chef.profile_photo:
            photo_url = chef.profile_photo.url
        
        # Calculate average rating
        avg_rating = None
        if hasattr(chef, 'meal_reviews'):
            from django.db.models import Avg
            avg_rating = chef.meal_reviews.aggregate(Avg('rating'))['rating__avg']
        
        chefs.append({
            'id': chef.id,
            'username': user.username,
            'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'photo': photo_url,
            'specialty': getattr(chef, 'specialty', None),
            'bio': getattr(chef, 'bio', ''),
            'rating': round(avg_rating, 1) if avg_rating else None,
            'connected_since': conn.requested_at.isoformat() if conn.requested_at else None,
            'last_activity': conn.last_activity.isoformat() if conn.last_activity else None,
        })
    
    return Response({
        'chefs': chefs,
        'count': len(chefs)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chef_hub(request, chef_id):
    """
    Get aggregated data for a specific chef's hub page.
    
    This is the main data endpoint for the individual chef view
    when a customer is viewing their relationship with a specific chef.
    
    Args:
        chef_id: The ID of the chef to get data for
        
    Returns:
        {
            'chef': {...},
            'connected_since': str,
            'current_plan': {...} or null,
            'upcoming_orders': [...],
            'pending_suggestions': int
        }
    """
    connection = get_object_or_404(
        ChefCustomerConnection.objects.select_related('chef__user'),
        customer=request.user,
        chef_id=chef_id,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    )
    
    chef = connection.chef
    user = chef.user
    
    # Get chef info
    photo_url = None
    if hasattr(chef, 'profile_photo') and chef.profile_photo:
        photo_url = chef.profile_photo.url
    
    # Get average rating
    avg_rating = None
    review_count = 0
    if hasattr(chef, 'meal_reviews'):
        from django.db.models import Avg, Count
        stats = chef.meal_reviews.aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        avg_rating = stats['avg_rating']
        review_count = stats['count'] or 0
    
    chef_data = {
        'id': chef.id,
        'username': user.username,
        'display_name': f"{user.first_name} {user.last_name}".strip() or user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'photo': photo_url,
        'specialty': getattr(chef, 'specialty', None),
        'bio': getattr(chef, 'bio', ''),
        'rating': round(avg_rating, 1) if avg_rating else None,
        'review_count': review_count,
    }
    
    # Get current/upcoming meal plan
    today = timezone.now().date()
    current_plan = ChefMealPlan.objects.filter(
        chef=chef,
        customer=request.user,
        status=ChefMealPlan.STATUS_PUBLISHED,
        end_date__gte=today
    ).order_by('start_date').first()
    
    plan_data = None
    pending_suggestions = 0
    if current_plan:
        plan_data = {
            'id': current_plan.id,
            'title': current_plan.title or f"Plan for {current_plan.start_date}",
            'start_date': current_plan.start_date.isoformat(),
            'end_date': current_plan.end_date.isoformat(),
            'notes': current_plan.notes,
            'published_at': current_plan.published_at.isoformat() if current_plan.published_at else None,
        }
        pending_suggestions = current_plan.pending_suggestions_count
    
    # Get upcoming orders with this chef (limited to 3)
    upcoming_orders = []
    # Check for ChefMealOrder or chef_meal_orders on Order
    from meals.models import ChefMealOrder
    chef_orders = ChefMealOrder.objects.filter(
        customer=request.user,
        meal_event__chef=chef,
        status__in=['placed', 'confirmed']
    ).select_related('meal_event__meal').order_by('meal_event__event_date')[:3]
    
    for order in chef_orders:
        upcoming_orders.append({
            'id': order.id,
            'meal_name': order.meal_event.meal.name if order.meal_event and order.meal_event.meal else 'Unknown',
            'event_date': order.meal_event.event_date.isoformat() if order.meal_event else None,
            'status': order.status,
            'price': float(order.price_paid) if order.price_paid else None,
        })
    
    return Response({
        'chef': chef_data,
        'connected_since': connection.requested_at.isoformat() if connection.requested_at else None,
        'current_plan': plan_data,
        'upcoming_orders': upcoming_orders,
        'pending_suggestions': pending_suggestions,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chef_orders(request, chef_id):
    """
    Get all orders with a specific chef.
    
    Args:
        chef_id: The ID of the chef
        
    Query params:
        status: Filter by status (optional)
        limit: Number of orders to return (default 20)
        offset: Pagination offset (default 0)
    """
    # Verify connection exists
    connection = get_object_or_404(
        ChefCustomerConnection,
        customer=request.user,
        chef_id=chef_id,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    )
    
    status_filter = request.query_params.get('status')
    limit = int(request.query_params.get('limit', 20))
    offset = int(request.query_params.get('offset', 0))
    
    from meals.models import ChefMealOrder
    orders_qs = ChefMealOrder.objects.filter(
        customer=request.user,
        meal_event__chef_id=chef_id
    ).select_related('meal_event__meal')
    
    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)
    
    total = orders_qs.count()
    orders_qs = orders_qs.order_by('-created_at')[offset:offset + limit]
    
    orders = []
    for order in orders_qs:
        orders.append({
            'id': order.id,
            'meal_name': order.meal_event.meal.name if order.meal_event and order.meal_event.meal else 'Unknown',
            'event_date': order.meal_event.event_date.isoformat() if order.meal_event else None,
            'event_time': order.meal_event.event_time.strftime('%H:%M') if order.meal_event and order.meal_event.event_time else None,
            'status': order.status,
            'quantity': order.quantity,
            'price': float(order.price_paid) if order.price_paid else None,
            'created_at': order.created_at.isoformat(),
        })
    
    return Response({
        'orders': orders,
        'total': total,
        'limit': limit,
        'offset': offset,
    })


