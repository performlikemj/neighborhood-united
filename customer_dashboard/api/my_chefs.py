"""
API endpoints for customer's connected chefs (multi-chef support).

These endpoints support the Client Portal experience where customers
can view and interact with their connected chefs.
"""
from django.db.models import Max, Avg, Count
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chef_services.models import ChefCustomerConnection, ChefServiceOffering, ChefServicePriceTier
from meals.models import ChefMealPlan, Order, Dish, ChefMealEvent


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chef_catalog(request, chef_id):
    """
    Get the chef's full catalog: dishes, upcoming meal events, and services.
    
    Services are filtered based on the customer's location - only services
    available in their area are returned.
    
    Args:
        chef_id: The ID of the chef
        
    Returns:
        {
            'dishes': [...],
            'meal_events': [...],
            'services': [...]
        }
    """
    # Verify connection exists
    connection = get_object_or_404(
        ChefCustomerConnection.objects.select_related('chef'),
        customer=request.user,
        chef_id=chef_id,
        status=ChefCustomerConnection.STATUS_ACCEPTED
    )
    
    chef = connection.chef
    
    # Get user's postal code for service filtering
    user_postal_code = None
    if hasattr(request.user, 'address') and request.user.address:
        user_postal_code = getattr(request.user.address, 'postal_code', None) or \
                          getattr(request.user.address, 'postalcode', None)
    
    # 1. Get chef's dishes
    dishes_qs = Dish.objects.filter(chef=chef).select_related('chef')
    dishes = []
    for dish in dishes_qs:
        # Get first photo if available
        photo_url = None
        if hasattr(dish, 'photos') and dish.photos.exists():
            first_photo = dish.photos.first()
            if first_photo and first_photo.image:
                photo_url = first_photo.image.url
        
        dishes.append({
            'id': dish.id,
            'name': dish.name,
            'description': getattr(dish, 'description', ''),
            'photo': photo_url,
            'calories': float(dish.calories) if dish.calories else None,
            'protein': float(dish.protein) if dish.protein else None,
            'carbohydrates': float(dish.carbohydrates) if dish.carbohydrates else None,
            'fat': float(dish.fat) if dish.fat else None,
            'featured': dish.featured,
        })
    
    # 2. Get upcoming meal events (open for orders, future dates)
    today = timezone.now().date()
    now = timezone.now()
    
    events_qs = ChefMealEvent.objects.filter(
        chef=chef,
        event_date__gte=today,
        status__in=['scheduled', 'open'],
        order_cutoff_time__gt=now
    ).select_related('meal').order_by('event_date', 'event_time')[:20]
    
    meal_events = []
    for event in events_qs:
        # Get meal photo if available
        photo_url = None
        if event.meal and hasattr(event.meal, 'photos') and event.meal.photos.exists():
            first_photo = event.meal.photos.first()
            if first_photo and first_photo.image:
                photo_url = first_photo.image.url
        
        spots_remaining = event.max_orders - event.orders_count if event.max_orders else None
        
        meal_events.append({
            'id': event.id,
            'meal_id': event.meal_id,
            'meal_name': event.meal.name if event.meal else 'Unknown',
            'description': event.description or (event.meal.description if event.meal else ''),
            'photo': photo_url,
            'event_date': event.event_date.isoformat(),
            'event_time': event.event_time.strftime('%H:%M') if event.event_time else None,
            'order_cutoff': event.order_cutoff_time.isoformat(),
            'base_price': float(event.base_price),
            'current_price': float(event.current_price),
            'min_price': float(event.min_price),
            'spots_remaining': spots_remaining,
            'status': event.status,
        })
    
    # 3. Get chef's service offerings (filtered by customer's location)
    services_qs = ChefServiceOffering.objects.filter(
        chef=chef,
        active=True
    ).prefetch_related('tiers')
    
    # Check if user's postal code is in chef's serving areas
    chef_postal_codes = set()
    if hasattr(chef, 'serving_postalcodes'):
        chef_postal_codes = set(
            pc.code for pc in chef.serving_postalcodes.all()
        )
    
    # User is in service area if their postal code matches OR if chef has no restrictions
    user_in_service_area = (
        not chef_postal_codes or  # Chef serves everywhere
        (user_postal_code and user_postal_code in chef_postal_codes)
    )
    
    services = []
    for offering in services_qs:
        # Check if this offering is specifically targeted to this user
        is_targeted = offering.target_customers.filter(id=request.user.id).exists()
        
        # Include if: user is in service area OR offering is targeted to them
        if not user_in_service_area and not is_targeted:
            continue
        
        # Get active tiers
        tiers = []
        for tier in offering.tiers.filter(active=True):
            tiers.append({
                'id': tier.id,
                'name': tier.display_label or f"{tier.household_min}-{tier.household_max or '∞'} people",
                'description': '',
                'price_cents': tier.desired_unit_amount_cents,
                'household_min': tier.household_min,
                'household_max': tier.household_max,
                'is_recurring': tier.is_recurring,
                'recurrence_interval': tier.recurrence_interval,
                'ready_for_checkout': bool(tier.stripe_price_id and tier.price_sync_status == 'success'),
            })
        
        if not tiers:
            continue  # Skip offerings with no active tiers
        
        services.append({
            'id': offering.id,
            'service_type': offering.service_type,
            'service_type_display': offering.get_service_type_display(),
            'title': offering.title,
            'description': offering.description,
            'default_duration_minutes': offering.default_duration_minutes,
            'tiers': tiers,
            'is_personalized': is_targeted,
        })
    
    return Response({
        'dishes': dishes,
        'meal_events': meal_events,
        'services': services,
        'user_in_service_area': user_in_service_area,
    })


