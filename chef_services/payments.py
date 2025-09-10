import stripe
from django.conf import settings
from django.db import transaction
from meals.utils.stripe_utils import get_stripe_return_urls, standardize_stripe_response
from .models import ChefServiceOrder


def create_service_checkout_session(service_order_id, customer_email=None):
    """
    Create a Stripe Checkout Session for a ChefServiceOrder using the tier.stripe_price_id.
    Returns (success: bool, payload: dict)
    """
    try:
        order = ChefServiceOrder.objects.select_related('tier', 'offering', 'chef', 'customer').get(id=service_order_id)
    except ChefServiceOrder.DoesNotExist:
        return False, {"message": "Service order not found", "status": "error"}

    if not order.tier or not order.tier.stripe_price_id:
        return False, {"message": "This order's price tier is not configured for checkout yet.", "status": "error"}

    stripe.api_key = settings.STRIPE_SECRET_KEY

    return_urls = get_stripe_return_urls(success_path="", cancel_path="")

    mode = 'subscription' if order.tier.is_recurring else 'payment'
    line_items = [{
        'price': order.tier.stripe_price_id,
        'quantity': 1,
    }]

    metadata = {
        'order_type': 'service',
        'service_order_id': str(order.id),
        'service_type': order.offering.service_type,
        'chef_id': str(order.chef_id),
        'customer_id': str(order.customer_id),
        'tier_id': str(order.tier_id),
        'household_size': str(order.household_size),
    }

    # Provide an idempotency key to guard against retries
    idempotency_key = f"service_checkout_{order.id}"

    session = stripe.checkout.Session.create(
        customer_email=customer_email,
        payment_method_types=['card'],
        mode=mode,
        line_items=line_items,
        **return_urls,
        metadata=metadata,
        idempotency_key=idempotency_key,
    )

    try:
        with transaction.atomic():
            order = ChefServiceOrder.objects.select_for_update().get(id=order.id)
            order.stripe_session_id = session.id
            order.status = 'awaiting_payment'
            order.save(update_fields=['stripe_session_id', 'status'])
    except Exception:
        # Non-fatal; webhook will still process
        pass

    return True, {"session_id": session.id, "session_url": session.url}
