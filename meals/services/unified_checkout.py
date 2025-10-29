"""
Unified checkout service for processing carts containing both meals and chef services.

This module handles the complex logic of:
1. Validating all cart items are from a single chef (Stripe Connect requirement)
2. Collecting line items from meals and chef services
3. Creating a single Stripe checkout session
4. Linking payment to all related orders
"""

import logging
import stripe
import decimal
from django.conf import settings
from django.db import transaction
from typing import Dict, List, Any, Tuple

from meals.models import Cart, Order, OrderMeal, ChefMealEvent
from chef_services.models import ChefServiceOrder
from meals.utils.stripe_utils import (
    get_active_stripe_account,
    calculate_platform_fee_cents,
    get_stripe_return_urls,
    StripeAccountError
)

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


class UnifiedCheckoutError(Exception):
    """Base exception for unified checkout errors"""
    pass


class MultipleChefError(UnifiedCheckoutError):
    """Raised when cart contains items from multiple chefs"""
    pass


class EmptyCartError(UnifiedCheckoutError):
    """Raised when cart is empty"""
    pass


class ValidationError(UnifiedCheckoutError):
    """Raised when cart items fail validation"""
    pass


def validate_chef_service_orders(service_orders: List[ChefServiceOrder]) -> Dict[str, List[str]]:
    """
    Validate that chef service orders have all required fields for checkout.
    
    Returns:
        Dict of validation errors by order_id
    """
    errors = {}
    
    for order in service_orders:
        order_errors = []
        
        if order.offering.service_type == "home_chef":
            if not order.service_date:
                order_errors.append("Service date is required")
            if not order.service_start_time:
                order_errors.append("Service start time is required")
        elif order.offering.service_type == "weekly_prep":
            if order.tier and order.tier.is_recurring:
                if not order.schedule_preferences and (not order.service_date or not order.service_start_time):
                    order_errors.append("Schedule preferences or date/time required")
            else:
                if not order.service_date:
                    order_errors.append("Service date is required")
                if not order.service_start_time:
                    order_errors.append("Service start time is required")
        
        if not order.address:
            order_errors.append("Delivery address is required")
        
        if order_errors:
            errors[str(order.id)] = order_errors
    
    return errors


def collect_line_items_from_cart(cart: Cart) -> Tuple[List[Dict], int, Any]:
    """
    Collect Stripe line items from cart (meals + chef services).
    
    Returns:
        Tuple of (line_items, total_amount_cents, chef)
        
    Raises:
        MultipleChefError: If cart contains items from multiple chefs
        EmptyCartError: If cart is empty
        ValidationError: If chef service orders are missing required fields
    """
    if not cart.is_single_chef_cart():
        raise MultipleChefError(
            "Cart contains items from multiple chefs. Due to payment processing limitations, "
            "please checkout items from each chef separately."
        )
    
    chef = cart.get_cart_chef()
    if not chef:
        raise EmptyCartError("Cart is empty")
    
    line_items = []
    total_amount_cents = 0
    
    # Collect meal line items
    meals = cart.meal.all()
    for meal in meals:
        if hasattr(meal, 'price') and meal.price:
            unit_amount = int(decimal.Decimal(meal.price) * 100)
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': meal.name,
                        'description': (meal.description or '')[:500] if hasattr(meal, 'description') else '',
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': 1,
            })
            total_amount_cents += unit_amount
    
    # Collect chef service line items
    service_orders = cart.chef_service_orders.filter(status='draft').select_related('offering', 'tier')
    
    # Validate chef service orders have required fields
    validation_errors = validate_chef_service_orders(service_orders)
    if validation_errors:
        raise ValidationError(f"Chef service orders missing required fields: {validation_errors}")
    
    for service_order in service_orders:
        tier = service_order.tier
        offering = service_order.offering
        
        # Check if tier has a stripe_price_id (for recurring services)
        if tier.stripe_price_id and tier.is_recurring:
            # Use Stripe Price ID for subscription items
            line_items.append({
                'price': tier.stripe_price_id,
                'quantity': 1,
            })
            # For total calculation, use desired amount
            total_amount_cents += tier.desired_unit_amount_cents
        else:
            # One-time service - use price_data
            unit_amount = tier.desired_unit_amount_cents
            line_items.append({
                'price_data': {
                    'currency': tier.currency,
                    'product_data': {
                        'name': offering.title,
                        'description': (offering.description or '')[:500],
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': 1,
            })
            total_amount_cents += unit_amount
    
    if not line_items:
        raise EmptyCartError("No valid items in cart")
    
    return line_items, total_amount_cents, chef


def create_unified_checkout_session(user, cart: Cart) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for cart containing meals and/or chef services.
    
    Args:
        user: The authenticated user
        cart: The user's cart
        
    Returns:
        Dict with success status and session details or error message
        
    Raises:
        UnifiedCheckoutError: For various checkout failures
    """
    try:
        # Collect line items and validate
        line_items, total_amount_cents, chef = collect_line_items_from_cart(cart)
        
        # Get chef's Stripe account
        try:
            destination_account_id, _ = get_active_stripe_account(chef)
        except StripeAccountError as exc:
            raise UnifiedCheckoutError(str(exc))
        
        # Calculate platform fee
        platform_fee_cents = calculate_platform_fee_cents(total_amount_cents)
        
        # Determine if this is a subscription (has any recurring service)
        has_subscription = any(
            order.tier.is_recurring 
            for order in cart.chef_service_orders.filter(status='draft').select_related('tier')
        )
        
        # Get return URLs
        return_urls = get_stripe_return_urls(success_path="", cancel_path="")
        
        # Prepare metadata
        service_order_ids = [
            str(order.id) 
            for order in cart.chef_service_orders.filter(status='draft')
        ]
        
        metadata = {
            'cart_id': str(cart.id),
            'customer_id': str(user.id),
            'chef_id': str(chef.id),
            'order_type': 'unified_cart',
            'has_meals': 'true' if cart.meal.exists() else 'false',
            'has_services': 'true' if service_order_ids else 'false',
        }
        
        if service_order_ids:
            metadata['service_order_ids'] = ','.join(service_order_ids)
        
        # Create Stripe session
        session_params = {
            'customer_email': user.email,
            'payment_method_types': ['card'],
            'line_items': line_items,
            'mode': 'subscription' if has_subscription else 'payment',
            **return_urls,
            'metadata': metadata,
        }
        
        # Add payment intent data for one-time payments
        if not has_subscription:
            session_params['payment_intent_data'] = {
                'transfer_data': {'destination': destination_account_id},
                'on_behalf_of': destination_account_id,
                'metadata': {
                    'cart_id': str(cart.id),
                    'chef_id': str(chef.id),
                    'order_type': 'unified_cart',
                },
                **({'application_fee_amount': platform_fee_cents} if platform_fee_cents else {}),
            }
        else:
            # For subscriptions
            session_params['subscription_data'] = {
                'metadata': {
                    'cart_id': str(cart.id),
                    'chef_id': str(chef.id),
                    'order_type': 'unified_cart',
                },
                'application_fee_percent': settings.PLATFORM_FEE_PERCENTAGE if hasattr(settings, 'PLATFORM_FEE_PERCENTAGE') else 10,
                'transfer_data': {'destination': destination_account_id},
            }
        
        session = stripe.checkout.Session.create(**session_params)
        
        # Update chef service orders to awaiting_payment
        with transaction.atomic():
            cart.chef_service_orders.filter(status='draft').update(
                status='awaiting_payment',
                stripe_session_id=session.id
            )
        
        return {
            'success': True,
            'session_id': session.id,
            'session_url': session.url,
            'chef_id': chef.id,
            'total_amount_cents': total_amount_cents,
        }
        
    except (MultipleChefError, EmptyCartError, ValidationError, UnifiedCheckoutError) as e:
        logger.error(f"Unified checkout error for user {user.id}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'error_type': e.__class__.__name__,
        }
    except Exception as e:
        logger.exception(f"Unexpected error in unified checkout for user {user.id}")
        return {
            'success': False,
            'error': 'An unexpected error occurred during checkout',
            'error_type': 'UnexpectedError',
        }


def clear_cart_after_payment(cart: Cart):
    """
    Clear cart items after successful payment.
    Called by webhook handler after payment confirmation.
    """
    with transaction.atomic():
        cart.meal.clear()
        # Don't clear chef service orders here - they're managed by their own status
        cart.chef_service_orders.clear()

