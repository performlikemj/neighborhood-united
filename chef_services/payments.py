import logging
import stripe
from django.conf import settings
from django.db import transaction

from meals.utils.stripe_utils import (
    calculate_platform_fee_cents,
    get_active_stripe_account,
    get_platform_fee_percentage,
    get_stripe_return_urls,
    StripeAccountError,
)
from .models import ChefServiceOrder


logger = logging.getLogger(__name__)


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

    try:
        destination_account_id, _ = get_active_stripe_account(order.chef)
    except StripeAccountError as exc:
        return False, {"message": str(exc), "status": "error"}

    return_urls = get_stripe_return_urls(success_path="", cancel_path="")
    
    # Ensure success_url includes session_id for payment verification
    # This allows the frontend to verify payment status after Stripe redirects back
    if 'success_url' in return_urls and '{CHECKOUT_SESSION_ID}' not in return_urls['success_url']:
        separator = '&' if '?' in return_urls['success_url'] else '?'
        return_urls['success_url'] = f"{return_urls['success_url']}{separator}session_id={{CHECKOUT_SESSION_ID}}"

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

    amount_cents = int(order.tier.desired_unit_amount_cents or 0)
    platform_fee_cents = calculate_platform_fee_cents(amount_cents)
    platform_fee_percent = get_platform_fee_percentage()

    session_kwargs = dict(
        customer_email=customer_email,
        payment_method_types=['card'],
        mode=mode,
        line_items=line_items,
        metadata=metadata,
        **return_urls,
    )

    if mode == 'subscription':
        subscription_data = {
            'transfer_data': {'destination': destination_account_id},
            'metadata': {
                'service_order_id': str(order.id),
                'chef_id': str(order.chef_id),
            },
        }
        if platform_fee_percent > 0:
            subscription_data['application_fee_percent'] = float(platform_fee_percent)
        session_kwargs['subscription_data'] = subscription_data
    else:
        payment_intent_data = {
            'transfer_data': {'destination': destination_account_id},
            'on_behalf_of': destination_account_id,
            'metadata': {
                'service_order_id': str(order.id),
                'chef_id': str(order.chef_id),
                'order_type': 'service',
            },
        }
        if platform_fee_cents:
            payment_intent_data['application_fee_amount'] = platform_fee_cents
        session_kwargs['payment_intent_data'] = payment_intent_data

    # Provide an idempotency key to guard against retries
    idempotency_key = f"service_checkout_{order.id}"

    log_payload = {
        "order_id": order.id,
        "mode": mode,
        "stripe_price_id": order.tier.stripe_price_id,
        "platform_fee_cents": platform_fee_cents,
        "customer_email": customer_email,
    }
    logger.info("Creating service checkout session", extra=log_payload)

    session = stripe.checkout.Session.create(
        idempotency_key=idempotency_key,
        **session_kwargs,
    )
    session_id = session.id
    session_url = getattr(session, 'url', None)
    if not session_url:
        warn_payload = {"order_id": order.id, "session_id": session_id}
        logger.warning("Stripe session missing url; attempting retrieval", extra=warn_payload)
        try:
            refreshed = stripe.checkout.Session.retrieve(session_id)
            session_url = getattr(refreshed, 'url', None)
        except Exception:
            session_url = None

    done_payload = {
        "order_id": order.id,
        "session_id": session_id,
        "session_url_present": bool(session_url),
    }
    logger.info("Service checkout session created", extra=done_payload)

    try:
        with transaction.atomic():
            order = ChefServiceOrder.objects.select_for_update().get(id=order.id)
            order.stripe_session_id = session_id
            order.status = 'awaiting_payment'
            order.save(update_fields=['stripe_session_id', 'status'])
    except Exception as e:
        logger.error(
            f"Failed to save checkout session {session_id} for order {service_order_id}: {e}",
            exc_info=True
        )
        return False, {"message": "Failed to initialize checkout. Please try again.", "status": "error"}

    return True, {"session_id": session_id, "session_url": session_url}
