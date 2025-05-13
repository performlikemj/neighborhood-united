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
from openai import OpenAI
import stripe
from custom_auth.models import CustomUser
from meals.models import ChefMealOrder, Order
from meals.pydantic_models import PaymentInfoSchema
from decimal import Decimal
# Set the Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

# Helper function to convert Decimal values to float
def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj

# Tool definitions for the OpenAI Responses API
PAYMENT_PROCESSING_TOOLS = [
    {
        "type": "function",
        "name": "generate_payment_link",
        "description": "Create a Stripe Checkout session URL for an unpaid order so the customer can pay for their order",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "order_id": {"type": "integer"}
            },
            "required": ["user_id", "order_id"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "cancel_order",
        "description": "Cancel a chef meal order",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "The ID of the user who placed the order"
                },
                "order_id": {
                    "type": "integer",
                    "description": "The ID of the order to cancel"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation"
                }
            },
            "required": ["user_id", "order_id"],
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
                        "type": "integer",
                        "description": "The ID of the user who placed the order"
                    },
                    "order_id": {
                        "type": "integer",
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
                        "type": "integer",
                        "description": "The ID of the user who placed the order"
                    },
                    "order_id": {
                        "type": "integer",
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


def generate_payment_link(user_id: int, order_id: int) -> Dict[str, Any]:
    """
    Generate a Stripe Checkout session URL for an unpaid *chef‑meal* order.

    The logic mirrors the `api_process_chef_meal_payment` endpoint:
      • Only chef‑meal events are considered
      • Quantities come from ChefMealOrder
      • Current price is always taken from the meal event
    Returns:
        { "status": "success",
          "checkout_url": session.url,
          "session_id":  session.id }
        or { "status": "error", "message": … }
    """
    import time
    import stripe
    from django.conf import settings
    from django.shortcuts import get_object_or_404
    from meals.utils.stripe_utils import get_stripe_return_urls
    from meals.models import Order, ChefMealOrder
    from custom_auth.models import CustomUser
    print("[generate_payment_link] START user_id=", user_id, "order_id=", order_id)
    logger = logging.getLogger(__name__)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # 1) Fetch user & order ------------------------------------------------
        user  = get_object_or_404(CustomUser, id=user_id)
        order = get_object_or_404(Order, id=order_id, customer=user)
        print(f"[generate_payment_link] Retrieved user {user.id} ({user.email}), "
              f"order {order.id} (is_paid={order.is_paid})")

        if order.is_paid:
            return {"status": "error",
                    "message": "This order has already been paid."}

        # 2) Collect chef‑meal ChefMealOrder rows ----------------------------------
        chef_meal_orders = ChefMealOrder.objects.filter(
            order=order
        ).select_related('meal_event', 'meal_event__meal')
        
        print(f"[generate_payment_link] Found {chef_meal_orders.count()} ChefMealOrder rows")
        if not chef_meal_orders.exists():
            return {"status": "error",
                    "message": "No chef meal events found for this order."}

        # 3) Build Stripe line_items ------------------------------------------
        line_items: List[Dict[str, Any]] = []

        for cmo in chef_meal_orders:
            print(f"[generate_payment_link] Processing ChefMealOrder {cmo.id}: "
                  f"meal={cmo.meal_event.meal.id}-{cmo.meal_event.meal.name}, "
                  f"event={cmo.meal_event.id}, "
                  f"meal_plan_meal={cmo.meal_plan_meal.id if cmo.meal_plan_meal else 'None'}")
            
            meal = cmo.meal_event.meal
            meal_event = cmo.meal_event
            meal_plan_meal = cmo.meal_plan_meal

            # Skip already‑paid MealPlanMeal instances
            if meal_plan_meal and getattr(meal_plan_meal, "already_paid", False):
                print(f"[generate_payment_link] Skipping meal_plan_meal {meal_plan_meal.id} "
                      "because already_paid=True")
                continue

            # Use quantity from ChefMealOrder
            quantity = cmo.quantity
            print(f"[generate_payment_link] Using quantity={quantity}")

            price = meal_event.current_price
            if not price or price <= 0:
                print(f"[generate_payment_link] Skipping item due to invalid price={price}")
                continue  # ignore invalid prices

            # Convert Decimal price to float if necessary
            if isinstance(price, Decimal):
                price = float(price)

            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": meal.name,
                        "description": (meal_event.description or "")[:500],
                    },
                    "unit_amount": int(price * 100),  # cents
                },
                "quantity": quantity,
            })
            print(f"[generate_payment_link] Added line_item – name={meal.name}, "
                  f"unit_amount={int(price*100)}, qty={quantity}")

        print(f"[generate_payment_link] Built {len(line_items)} total line_items")
        if not line_items:
            return {"status": "error",
                    "message": "No items requiring payment found in this order."}

        # 4) Create Stripe Checkout session -----------------------------------
        return_urls = get_stripe_return_urls(success_path="", cancel_path="")
        idempotency_key = f"order_{order.id}_{int(time.time())}"
        print("[generate_payment_link] Creating Stripe checkout session…")
        print(f"[generate_payment_link] return_urls={return_urls}, "
              f"idempotency_key={idempotency_key}")

        session = stripe.checkout.Session.create(
            customer_email=user.email,
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            **return_urls,
            metadata={
                "order_id":   str(order.id),
                "order_type": "chef_meal",
                "customer_id": str(user.id),
            },
            idempotency_key=idempotency_key,
        )
        print(f"[generate_payment_link] Stripe session created: id={session.id}, "
              f"url={session.url}")

        # 5) Persist session ID and respond -----------------------------------
        order.stripe_session_id = session.id
        order.save(update_fields=["stripe_session_id"])
        print(f"[generate_payment_link] Saved stripe_session_id to order {order.id}")

        api_key = settings.OPENAI_KEY
        client = OpenAI(api_key=api_key)
        output = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "developer", "content": (
                    """
                    Transform Stripe session checkout data into a structured response containing payment information, checkout URL, and an HTML button to facilitate payment.

                    Extract the necessary information from the user's Stripe session checkout data and organize it in accordance with the `PaymentInfoSchema`. Use the provided schema attributes to ensure accurate representation of the data:

                    - `checkout_url`: The URL for the checkout page.
                    - `session_id`: The unique identifier for the Stripe session.
                    - `html_button`: HTML code for a button that, when clicked, directs users to the full checkout URL.

                    # Steps

                    1. **Extract Information**: Identify the checkout URL, session ID, and relevant details from the Stripe session.
                    2. **Structure Information**: Populate the attributes of the `PaymentInfoSchema` with the extracted data.
                    3. **Generate HTML Button**: Create a simple HTML button using the checkout URL. The button should be styled for usability and accessibility.
                    4. **Return Schema-structured Output**: Provide the information in the format defined by the schema.

                    # Output Format

                    - JSON format adhering to the `PaymentInfoSchema`:
                        ```json
                        {
                            "checkout_url": "[Checkout URL]",
                            "session_id": "[Stripe Session ID]",
                            "html_button": "<button onclick=\"location.href='[Checkout URL]'\">Pay Now</button>"
                        }
                        ```

                    # Examples

                    **Example Input:**
                    - Stripe session data containing relevant payment checkout information.

                    **Example Output:**
                    ```json
                    {
                        "checkout_url": "https://checkout.stripe.com/pay/cs_test_a1b2c3d4e5f6g7h8i9j0",
                        "session_id": "cs_test_a1b2c3d4e5f6g7h8i9j0",
                        "html_button": "<button onclick=\"location.href='https://checkout.stripe.com/pay/cs_test_a1b2c3d4e5f6g7h8i9j0'\">Pay Now</button>"
                    }
                    ```

                    **(Note: The actual input will vary, providing only key-value pairs such as IDs and URL strings associated with a real Stripe checkout session.)**
                    """
                )},
                {"role": "user", "content": f"checkout url: {session.url}, session id: {session.id}"}
            ],
            text={
                "format": {
                    'type': 'json_schema',
                    'name': 'payment_info',
                    'schema': PaymentInfoSchema.model_json_schema()
                }
            }
        )
        payment_info = json.loads(output.output_text)
        return decimal_to_float({
            "status": "success",
            "checkout_url": payment_info["checkout_url"],
            "session_id": payment_info["session_id"],
            "html_button": payment_info["html_button"]
        })

    except stripe.error.StripeError as se:
        print(f"[generate_payment_link] StripeError occurred: {se}")
        logger.error(f"Stripe error (order {order_id}): {se}", exc_info=True)
        return {"status": "error", "message": f"Stripe error: {se}"}
    except Exception as e:
        print(f"[generate_payment_link] General exception occurred: {e}")
        logger.error(f"generate_payment_link failed for order {order_id}: {e}",
                     exc_info=True)
        return {"status": "error", "message": str(e)}
    
def cancel_order(user_id: int, order_id: int, reason: str = None) -> Dict[str, Any]:
    """
    Cancel a chef meal order.
    
    Args:
        user_id: The ID of the user who placed the order
        order_id: The ID of the order to cancel
        reason: Reason for cancellation
        
    Returns:
        Dict containing the cancellation status
    """
    try:
        # Get the user and order
        user = get_object_or_404(CustomUser, id=user_id)
        order = get_object_or_404(Order, id=order_id, customer=user)
        
        # Check if the order has chef meal orders
        chef_meal_orders = ChefMealOrder.objects.filter(order=order)
        if not chef_meal_orders.exists():
            return {
                "status": "error",
                "message": "No chef meal orders found for this order."
            }
        
        # Check if any of the chef meal orders can't be cancelled
        now = timezone.now()
        uncancellable_orders = []
        for cmo in chef_meal_orders:
            event = cmo.meal_event
            # Check if already cancelled
            if cmo.status == 'cancelled':
                continue
                
            # Check if the event is in the past
            if event.event_date < now.date():
                uncancellable_orders.append(f"Event {event.id} ({event.meal.name}) has already passed")
            # Check if past cutoff time
            elif now > event.order_cutoff_time:
                uncancellable_orders.append(f"Event {event.id} ({event.meal.name}) is past the order cutoff time")
                
        if uncancellable_orders:
            return {
                "status": "error",
                "message": "Cannot cancel some or all of the chef meal orders",
                "details": uncancellable_orders
            }
            
        # Cancel all chef meal orders
        cancelled_orders = []
        for cmo in chef_meal_orders:
            if cmo.status not in ['cancelled', 'refunded', 'completed']:
                # Use the ChefMealOrder's cancel method to properly update counts
                cmo.cancel()
                cancelled_orders.append(cmo.id)
        
        # Update the main order status
        order.status = "Cancelled"
        order.save()
        
        # Process refund if the order is paid
        refund_result = None
        if order.is_paid:
            refund_reason = reason or "Order cancelled by customer"
            refund_result = process_refund(user_id, order_id, refund_reason)
            
            if refund_result.get('status') == 'success':
                # Convert any Decimal values to float
                refund_result = decimal_to_float(refund_result)
                
                return {
                    "status": "success",
                    "message": "Order cancelled and refund processed successfully",
                    "cancelled_orders": cancelled_orders,
                    "refund_status": "completed",
                    "refund_details": refund_result
                }
            else:
                return {
                    "status": "partial_success",
                    "message": "Order cancelled but refund could not be processed automatically",
                    "cancelled_orders": cancelled_orders,
                    "refund_status": "failed",
                    "refund_error": refund_result.get('message', 'Unknown error processing refund')
                }
        
        # If order is not paid, just return success
        return {
            "status": "success",
            "message": "Order cancelled successfully",
            "cancelled_orders": cancelled_orders,
            "refund_status": "not_applicable"
        }
        
    except Order.DoesNotExist:
        return { "status": "error", "message": f"Order with ID {order_id} not found for user {user_id}."}
    except Exception as e:
        logger.error(f"Error cancelling order for user {user_id}, order {order_id}: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to cancel order: {str(e)}"
        }

def check_payment_status(user_id: int, order_id: int) -> Dict[str, Any]:
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
            return decimal_to_float({
                "status": "success",
                "payment_status": "not_started",
                "order_type": "chef_meal" if order.ordermeal_set.filter(chef_meal_event__isnull=False).exists() else "regular_meal"
            })
            
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
            
        return decimal_to_float({
            "status": "success",
            "payment_status": payment_status,
            "order_type": "chef_meal" if order.ordermeal_set.filter(chef_meal_event__isnull=False).exists() else "regular_meal",
            "session_status": session.status,
            "payment_intent": session.payment_intent if hasattr(session, 'payment_intent') else None
        })
        
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

def process_refund(user_id: int, order_id: int, reason: str, amount: float = None) -> Dict[str, Any]:
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
        
        # Handle any Decimal values that might be returned by total_price()
        total_price = order.total_price()
        if isinstance(total_price, Decimal):
            total_price = float(total_price)
            
        return {
            "status": "success",
            "message": "Refund processed successfully",
            "refund_id": refund.id,
            "refund_status": refund.status,
            "refund_amount": amount if amount else total_price
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
