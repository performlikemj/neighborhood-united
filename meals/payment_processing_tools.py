"""
Payment processing tools for the OpenAI Responses API integration.

This module implements the payment processing tools defined in the optimized tool structure,
connecting them to the existing payment processing functionality in the application.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings

import stripe
from custom_auth.models import CustomUser
from meals.models import ChefMealOrder, Order

# Set the Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

# Tool definitions for the OpenAI Responses API
PAYMENT_PROCESSING_TOOLS = [
    {
        "type": "function",
        "name": "create_payment_link",
        "description": "Create a Stripe payment link for an order",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user making the payment"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to pay for"
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["chef_meal", "regular_meal"],
                        "description": "The type of order"
                    }
                },
                "required": ["user_id", "order_id", "order_type"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "check_payment_status",
        "description": "Check the payment status of an order",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user who placed the order"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to check"
                    }
                },
                "required": ["user_id", "order_id"],
                "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "process_refund",
        "description": "Process a refund for an order",
        "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The ID of the user who placed the order"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to refund"
                    },
                    "amount": {
                        "type": "number",
                        "description": "Amount to refund (if partial refund)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the refund"
                    }
                },
                "required": ["user_id", "order_id", "reason"],
                "additionalProperties": False
        }
    }
]

# Helper function to get return URLs
def get_stripe_return_urls(success_path="", cancel_path=""):
    """Get return URLs for Stripe checkout"""
    base_url = settings.FRONTEND_URL
    success_url = f"{base_url}/{success_path}".rstrip('/') + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = f"{base_url}/{cancel_path}".rstrip('/') + "?cancelled=true"
    
    return {
        "success_url": success_url,
        "cancel_url": cancel_url
    }

# Tool implementation functions
def create_payment_link(user_id: str, order_id: str, order_type: str) -> Dict[str, Any]:
    """
    Create a Stripe payment link for an order.
    
    Args:
        user_id: The ID of the user making the payment
        order_id: The ID of the order to pay for
        order_type: The type of order (chef_meal, regular_meal)
        
    Returns:
        Dict containing the payment link and session ID
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the order
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Check if the order has already been paid for
        if order.is_paid:
            return {
                "status": "error",
                "message": "This order has already been paid for"
            }
            
        if order_type == "chef_meal":
            # Get chef meal events from OrderMeal objects
            order_meals = order.ordermeal_set.filter(
                chef_meal_event__isnull=False
            ).select_related('chef_meal_event', 'meal', 'meal_plan_meal')
            
            if not order_meals.exists():
                return {
                    "status": "error",
                    "message": "No chef meal events found for this order."
                }
            
            # Prepare line items for Stripe Checkout
            line_items = []
            
            for order_meal in order_meals:
                meal = order_meal.meal
                meal_event = order_meal.chef_meal_event
                meal_plan_meal = order_meal.meal_plan_meal
                
                # Skip meals that have already been paid for
                if hasattr(meal_plan_meal, 'already_paid') and meal_plan_meal.already_paid:
                    continue
                
                # Get the associated ChefMealOrder for the correct quantity
                try:
                    chef_meal_order = ChefMealOrder.objects.get(
                        order=order,
                        meal_plan_meal=meal_plan_meal
                    )
                    actual_quantity = chef_meal_order.quantity
                except ChefMealOrder.DoesNotExist:
                    actual_quantity = order_meal.quantity
                
                # Always use the current price from the meal event
                current_price = meal_event.current_price
                
                line_items.append({
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': meal.name,
                            'description': meal_event.description[:500] if meal_event.description else "",
                        },
                        'unit_amount': int(current_price * 100),  # Convert to cents
                    },
                    'quantity': actual_quantity,  # Use the quantity from ChefMealOrder
                })
            
            if not line_items:
                return {
                    "status": "error",
                    "message": "No items requiring payment found in this order."
                }
                
            # Get return URLs
            return_urls = get_stripe_return_urls(
                success_path="",
                cancel_path=""
            )
            
            # Create the Stripe checkout session
            session = stripe.checkout.Session.create(
                customer_email=user.email,
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                **return_urls,
                metadata={
                    'order_id': str(order.id),
                    'order_type': order_type,
                    'customer_id': str(user.id)
                }
            )
            
            # Update the order with the session ID
            order.stripe_session_id = session.id
            order.save()
            
            return {
                "status": "success",
                "message": "Checkout session created successfully",
                "payment_url": session.url,
                "session_id": session.id
            }
        elif order_type == "regular_meal":
            # Calculate total price
            total_price_decimal = order.total_price()
            if total_price_decimal is None or total_price_decimal <= 0:
                return {
                    "status": "error",
                    "message": "Cannot process payment for an order with zero or invalid total price."
                }
            
            total_price_cents = int(total_price_decimal * 100)
            
            # Get return URLs
            return_urls = get_stripe_return_urls(
                success_path="",
                cancel_path=""
            )
            
            # Create line items for the Stripe checkout session
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f"Order #{order.id}",
                        'description': f"Payment for meal plan order",
                    },
                    'unit_amount': total_price_cents,
                },
                'quantity': 1,
            }]
            
            # Create the Stripe checkout session
            session = stripe.checkout.Session.create(
                customer_email=user.email,
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                **return_urls,
                metadata={
                    'order_id': str(order.id),
                    'order_type': order_type,
                    'customer_id': str(user.id)
                }
            )
            
            # Update the order with the session ID
            order.stripe_session_id = session.id
            order.save()
            
            return {
                "status": "success",
                "message": "Checkout session created successfully",
                "payment_url": session.url,
                "session_id": session.id
            }
        else:
            return {
                "status": "error",
                "message": f"Unsupported order type: {order_type}"
            }
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment link: {str(e)}")
        return {
            "status": "error",
            "message": f"Stripe error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error creating payment link for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create payment link: {str(e)}"
        }

def check_payment_status(user_id: str, order_id: str) -> Dict[str, Any]:
    """
    Check the payment status of an order.
    
    Args:
        user_id: The ID of the user who placed the order
        order_id: The ID of the order to check
        
    Returns:
        Dict containing the payment status
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Try to find the order
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Check if the order has a Stripe session ID
        if not order.stripe_session_id:
            return {
                "status": "success",
                "payment_status": "not_started",
                "order_type": "chef_meal" if order.ordermeal_set.filter(chef_meal_event__isnull=False).exists() else "regular_meal"
            }
            
        # Retrieve the Stripe checkout session
        session = stripe.checkout.Session.retrieve(order.stripe_session_id)
        
        # Determine the payment status based on the session status
        if session.payment_status == "paid":
            payment_status = "paid"
        elif session.payment_status == "unpaid":
            payment_status = "pending"
        else:
            payment_status = "failed"
            
        # Update the order's payment status if needed
        if payment_status == "paid" and not order.is_paid:
            order.is_paid = True
            order.save()
            
        return {
            "status": "success",
            "payment_status": payment_status,
            "order_type": "chef_meal" if order.ordermeal_set.filter(chef_meal_event__isnull=False).exists() else "regular_meal",
            "session_status": session.status,
            "payment_intent": session.payment_intent if hasattr(session, 'payment_intent') else None
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error checking payment status: {str(e)}")
        return {
            "status": "error",
            "message": f"Stripe error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error checking payment status for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to check payment status: {str(e)}"
        }

def process_refund(user_id: str, order_id: str, reason: str, amount: float = None) -> Dict[str, Any]:
    """
    Process a refund for an order.
    
    Args:
        user_id: The ID of the user who placed the order
        order_id: The ID of the order to refund
        amount: Amount to refund (if partial refund)
        reason: Reason for the refund
        
    Returns:
        Dict containing the refund status
    """
    try:
        # Get the user
        user = get_object_or_404(CustomUser, id=user_id)
        
        # Get the order
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Check if the order has been paid for
        if not order.is_paid:
            return {
                "status": "error",
                "message": "Cannot refund an order that has not been paid for"
            }
            
        # Check if the order has a session ID
        if not order.stripe_session_id:
            return {
                "status": "error",
                "message": "No payment information found for this order"
            }
        
        # Retrieve session to get payment intent
        session = stripe.checkout.Session.retrieve(order.stripe_session_id)
        if not hasattr(session, 'payment_intent'):
            return {
                "status": "error",
                "message": "No payment intent found for this order"
            }
        
        payment_intent_id = session.payment_intent
        
        # Process the refund
        refund_amount = int(amount * 100) if amount else None  # Convert to cents if provided
        
        refund = stripe.Refund.create(
            payment_intent=payment_intent_id,
            amount=refund_amount,
            reason="requested_by_customer",
            metadata={
                'order_id': order_id,
                'order_type': "chef_meal" if order.ordermeal_set.filter(chef_meal_event__isnull=False).exists() else "regular_meal",
                'user_id': user_id,
                'reason': reason
            }
        )
        
        # Update the order
        order.status = 'Refunded'
        order.save()
        
        # For chef meal orders, update their status too
        for chef_meal_order in order.chef_meal_orders.all():
            chef_meal_order.status = 'refunded'
            chef_meal_order.stripe_refund_id = refund.id
            chef_meal_order.save()
        
        return {
            "status": "success",
            "message": "Refund processed successfully",
            "refund_id": refund.id,
            "refund_status": refund.status,
            "refund_amount": amount if amount else order.total_price()
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error processing refund: {str(e)}")
        return {
            "status": "error",
            "message": f"Stripe error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error processing refund for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to process refund: {str(e)}"
        }

# Function to get all payment processing tools
def get_payment_processing_tools():
    """
    Get all payment processing tools for the OpenAI Responses API.
    
    Returns:
        List of payment processing tools in the format required by the OpenAI Responses API
    """
    return PAYMENT_PROCESSING_TOOLS
