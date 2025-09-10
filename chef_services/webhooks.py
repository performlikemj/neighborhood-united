import logging
import stripe
from django.conf import settings
from django.db import transaction
from .models import ChefServiceOrder

logger = logging.getLogger(__name__)


def handle_checkout_session_completed(session):
    """Handle Stripe checkout.session.completed for service orders.
    Expects metadata.service_order_id and metadata.order_type == 'service'.
    """
    metadata = getattr(session, 'metadata', {}) or {}
    if not metadata or metadata.get('order_type') != 'service':
        return

    service_order_id = metadata.get('service_order_id')
    if not service_order_id:
        logger.error("Service webhook missing service_order_id in metadata")
        return

    try:
        with transaction.atomic():
            order = ChefServiceOrder.objects.select_for_update().get(id=service_order_id)
            # Idempotency: if already confirmed, do nothing
            if order.status == 'confirmed':
                return

            # Basic metadata consistency checks
            md_tier_id = (getattr(session, 'metadata', {}) or {}).get('tier_id')
            if md_tier_id and str(order.tier_id) != str(md_tier_id):
                logger.warning(f"Service order {order.id} tier mismatch in metadata: got {md_tier_id}, expected {order.tier_id}")

            # Verify session mode and price id against order's tier via Stripe API
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                sess = stripe.checkout.Session.retrieve(session.id, expand=['line_items', 'line_items.data.price'])
                if order.tier.is_recurring and sess.mode != 'subscription':
                    logger.error(f"Order {order.id} expected subscription mode, got {sess.mode}")
                    return
                if not order.tier.is_recurring and sess.mode != 'payment':
                    logger.error(f"Order {order.id} expected one-time payment mode, got {sess.mode}")
                    return
                # Ensure exactly one line item and price id matches
                items = getattr(sess, 'line_items', None)
                prices = []
                if items and getattr(items, 'data', None):
                    for li in items.data:
                        price_obj = getattr(li, 'price', None)
                        if price_obj and getattr(price_obj, 'id', None):
                            prices.append(price_obj.id)
                if len(prices) != 1 or prices[0] != order.tier.stripe_price_id:
                    logger.error(f"Price verification failed for order {order.id}. Prices: {prices} expected: {order.tier.stripe_price_id}")
                    return
            except Exception as verify_err:
                logger.error(f"Stripe verification failed for service order {order.id}: {verify_err}")
                return

            # Persist subscription id if any
            subscription_id = getattr(session, 'subscription', None) or getattr(session, 'subscription_id', None)
            if subscription_id:
                order.stripe_subscription_id = subscription_id

            # Mark as confirmed
            order.status = 'confirmed'
            if not order.stripe_session_id:
                order.stripe_session_id = session.id
            order.save(update_fields=['status', 'stripe_session_id', 'stripe_subscription_id'])
    except ChefServiceOrder.DoesNotExist:
        logger.error(f"Service order {service_order_id} not found for webhook session {session.id}")
