from django.db import transaction
from django.utils import timezone
from meals.models import ChefMealOrder, ChefMealEvent
from django.db.models import F
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_order(user, event: ChefMealEvent, qty: int, idem_key: str):
    """
    Create a new chef meal order with Stripe payment intent for manual capture.
    
    Args:
        user: The user placing the order
        event: The ChefMealEvent being ordered
        qty: Quantity of the meal being ordered
        idem_key: Idempotency key to prevent duplicate operations
        
    Returns:
        The created ChefMealOrder object
        
    Raises:
        ValueError: If an active order already exists or if other validation fails
    """
    with transaction.atomic():
        # Lock the event row to prevent race conditions
        event = ChefMealEvent.objects.select_for_update().get(id=event.id)
        
        # Check if user already has an active order for this event
        if ChefMealOrder.objects.filter(
            customer=user, 
            meal_event=event,
            status__in=['placed', 'confirmed']
        ).exists():
            raise ValueError("Active order already exists")
        
        # Create payment intent with manual capture
        intent = stripe.PaymentIntent.create(
            amount=int(event.current_price * qty * 100),  # cents
            currency='usd',
            capture_method='manual',
            metadata={
                'meal_event': event.id, 
                'customer': user.id,
                'quantity': qty
            },
            idempotency_key=idem_key
        )
        
        # Create the order
        from meals.models import Order
        # Check if the user already has an active order
        order, created = Order.objects.get_or_create(
            customer=user,
            status='Placed',
            is_paid=False,
            defaults={
                'delivery_method': 'Pickup',  # Default, can be updated later
            }
        )
        
        # Create the chef meal order
        chef_meal_order = ChefMealOrder.objects.create(
            order=order,
            meal_event=event,
            customer=user,
            quantity=qty,
            unit_price=event.current_price,
            stripe_payment_intent_id=intent.id
        )
        
        # Schedule capture at cutoff time
        from meals.tasks import schedule_capture
        schedule_capture.delay(event.id)
        
        return chef_meal_order

def adjust_quantity(order: ChefMealOrder, new_qty: int, idem_key: str):
    """
    Adjust the quantity of an existing order.
    
    Args:
        order: The ChefMealOrder to update
        new_qty: The new quantity
        idem_key: Idempotency key to prevent duplicate operations
        
    Raises:
        ValueError: If cutoff time has passed or validation fails
    """
    cutoff = order.meal_event.order_cutoff_time
    
    # Check if cutoff time has passed
    if timezone.now() >= cutoff:
        raise ValueError("Order cutoff time has passed")
    
    # Calculate payment difference
    diff_amount = int(order.unit_price * (new_qty - order.quantity) * 100)
    
    # Update payment intent amount
    stripe.PaymentIntent.modify(
        order.stripe_payment_intent_id,
        amount=int(order.unit_price * new_qty * 100),
        idempotency_key=idem_key
    )
    
    # Update order quantity
    order.quantity = new_qty
    order.save(update_fields=['quantity'])

def cancel_order(order: ChefMealOrder, reason: str, idem_key: str):
    """
    Cancel an order and void the payment authorization.
    
    Args:
        order: The ChefMealOrder to cancel
        reason: Reason for cancellation
        idem_key: Idempotency key to prevent duplicate operations
        
    Returns:
        bool: True if cancelled successfully
        
    Raises:
        Exception: If Stripe API call fails
    """
    # Void the payment authorization
    if order.stripe_payment_intent_id:
        stripe.PaymentIntent.cancel(
            order.stripe_payment_intent_id,
            cancellation_reason=reason,
            idempotency_key=idem_key
        )
    
    # Update order status
    order.status = 'cancelled'
    order.save(update_fields=['status'])
    
    return True 