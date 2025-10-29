"""
Unified cart views for handling meals and chef services together.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from meals.models import Cart
from chef_services.models import ChefServiceOrder
from meals.services.unified_checkout import (
    create_unified_checkout_session,
    UnifiedCheckoutError,
    MultipleChefError,
    EmptyCartError,
    ValidationError
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    """
    Get the user's cart with meals and chef service orders.
    
    Returns cart summary including:
    - Meals
    - Chef service orders (draft status)
    - Chef validation (single chef check)
    - Total item count
    """
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    # Get meals
    meals = cart.meal.all().values('id', 'name', 'price', 'chef__user__username', 'chef_id')
    
    # Get draft chef service orders
    service_orders = cart.chef_service_orders.filter(status='draft').select_related(
        'offering', 'tier', 'chef__user'
    ).values(
        'id', 'offering__title', 'offering__service_type', 'tier__desired_unit_amount_cents',
        'tier__currency', 'household_size', 'chef__user__username', 'chef_id',
        'service_date', 'service_start_time', 'address_id'
    )
    
    # Check if cart is from single chef
    is_single_chef = cart.is_single_chef_cart()
    cart_chef_id = cart.get_cart_chef().id if cart.get_cart_chef() else None
    all_chefs = [{'id': chef.id, 'username': chef.user.username} for chef in cart.get_all_chefs()]
    
    return Response({
        'cart_id': cart.id,
        'meals': list(meals),
        'chef_services': list(service_orders),
        'is_single_chef_cart': is_single_chef,
        'cart_chef_id': cart_chef_id,
        'all_chefs': all_chefs,
        'total_items': len(meals) + len(service_orders),
        'can_checkout': is_single_chef and (len(meals) + len(service_orders)) > 0,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_chef_service_to_cart(request):
    """
    Add a chef service order to the cart.
    
    Body:
    {
        "service_order_id": 123
    }
    
    The service order must be in 'draft' status and belong to the user.
    """
    service_order_id = request.data.get('service_order_id')
    
    if not service_order_id:
        return Response({
            'success': False,
            'error': 'service_order_id is required'
        }, status=400)
    
    # Get the service order
    try:
        service_order = ChefServiceOrder.objects.get(
            id=service_order_id,
            customer=request.user,
            status='draft'
        )
    except ChefServiceOrder.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Chef service order not found or not in draft status'
        }, status=404)
    
    # Get or create cart
    cart, created = Cart.objects.get_or_create(customer=request.user)
    
    # Check if adding this would create a multi-chef cart
    if cart.get_all_chefs() and cart.get_cart_chef() and cart.get_cart_chef().id != service_order.chef_id:
        return Response({
            'success': False,
            'error': 'Cannot add service from different chef. Cart already contains items from another chef.',
            'current_chef_id': cart.get_cart_chef().id,
            'service_chef_id': service_order.chef_id,
        }, status=400)
    
    # Add to cart
    cart.chef_service_orders.add(service_order)
    
    return Response({
        'success': True,
        'message': 'Chef service added to cart',
        'cart_id': cart.id,
        'service_order_id': service_order.id,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_chef_service_from_cart(request):
    """
    Remove a chef service order from the cart.
    
    Body:
    {
        "service_order_id": 123
    }
    """
    service_order_id = request.data.get('service_order_id')
    
    if not service_order_id:
        return Response({
            'success': False,
            'error': 'service_order_id is required'
        }, status=400)
    
    cart = get_object_or_404(Cart, customer=request.user)
    
    try:
        service_order = ChefServiceOrder.objects.get(id=service_order_id, customer=request.user)
        cart.chef_service_orders.remove(service_order)
        
        return Response({
            'success': True,
            'message': 'Chef service removed from cart'
        })
    except ChefServiceOrder.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Chef service order not found'
        }, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unified_checkout(request):
    """
    Process checkout for cart containing meals and/or chef services.
    
    Validates:
    - All items are from same chef
    - Chef service orders have required fields
    - User has a valid payment method setup
    
    Returns:
    - Stripe checkout session URL
    """
    cart = get_object_or_404(Cart, customer=request.user)
    
    # Create checkout session
    result = create_unified_checkout_session(request.user, cart)
    
    if not result.get('success'):
        error_type = result.get('error_type', 'UnknownError')
        error_message = result.get('error', 'Unknown error')
        
        # Map error types to HTTP status codes
        status_map = {
            'MultipleChefError': 400,
            'EmptyCartError': 400,
            'ValidationError': 400,
            'UnifiedCheckoutError': 400,
            'UnexpectedError': 500,
        }
        
        status_code = status_map.get(error_type, 400)
        
        return Response({
            'success': False,
            'error': error_message,
            'error_type': error_type,
        }, status=status_code)
    
    return Response({
        'success': True,
        'session_id': result['session_id'],
        'session_url': result['session_url'],
        'chef_id': result['chef_id'],
        'total_amount_cents': result['total_amount_cents'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """
    Clear all items from the cart.
    """
    cart = get_object_or_404(Cart, customer=request.user)
    
    # Clear meals
    meal_count = cart.meal.count()
    cart.meal.clear()
    
    # Clear chef service orders
    service_count = cart.chef_service_orders.count()
    cart.chef_service_orders.clear()
    
    return Response({
        'success': True,
        'message': 'Cart cleared',
        'meals_removed': meal_count,
        'services_removed': service_count,
    })

