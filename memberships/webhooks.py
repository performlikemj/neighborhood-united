"""
Stripe webhook handlers for community membership subscriptions.

These handlers process subscription lifecycle events from Stripe
and update the local membership records accordingly.
"""

import logging
from django.db import transaction
from django.utils import timezone

from .models import ChefMembership, MembershipPaymentLog, MEMBERSHIP_PRODUCT_ID

logger = logging.getLogger(__name__)


def is_membership_subscription(subscription):
    """
    Check if a Stripe subscription is for community membership.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        bool: True if this is a membership subscription
    """
    items = getattr(subscription, 'items', None)
    if not items:
        return False
    
    data = getattr(items, 'data', [])
    for item in data:
        price = getattr(item, 'price', None)
        if price:
            product = getattr(price, 'product', None)
            if product == MEMBERSHIP_PRODUCT_ID:
                return True
    
    return False


def get_chef_from_subscription(subscription):
    """
    Find the Chef associated with a Stripe subscription.
    
    First checks metadata for chef_id, then falls back to
    looking up by stripe_customer_id.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        Chef instance or None
    """
    from chefs.models import Chef
    
    metadata = getattr(subscription, 'metadata', {}) or {}
    
    # Try to get chef_id from metadata first
    chef_id = metadata.get('chef_id')
    if chef_id:
        try:
            return Chef.objects.get(id=chef_id)
        except Chef.DoesNotExist:
            logger.warning(f"Chef {chef_id} from subscription metadata not found")
    
    # Fall back to looking up by customer ID
    customer_id = getattr(subscription, 'customer', None)
    if customer_id:
        try:
            membership = ChefMembership.objects.select_related('chef').get(
                stripe_customer_id=customer_id
            )
            return membership.chef
        except ChefMembership.DoesNotExist:
            pass
    
    return None


def handle_subscription_created(subscription):
    """
    Handle customer.subscription.created event.
    
    Creates or updates the ChefMembership record when a new
    subscription is created in Stripe.
    
    Args:
        subscription: Stripe subscription object
    """
    if not is_membership_subscription(subscription):
        logger.debug("Ignoring non-membership subscription created event")
        return
    
    chef = get_chef_from_subscription(subscription)
    if not chef:
        logger.error(
            f"Could not find chef for subscription {subscription.id}. "
            "Ensure chef_id is in subscription metadata."
        )
        return
    
    customer_id = getattr(subscription, 'customer', None)
    
    # Determine billing cycle from subscription interval
    items = getattr(subscription, 'items', {})
    data = getattr(items, 'data', [])
    billing_cycle = ChefMembership.BillingCycle.MONTHLY
    if data:
        price = getattr(data[0], 'price', None)
        if price:
            recurring = getattr(price, 'recurring', {})
            if recurring and recurring.get('interval') == 'year':
                billing_cycle = ChefMembership.BillingCycle.ANNUAL
    
    # Map Stripe status to our status
    stripe_status = getattr(subscription, 'status', 'active')
    status_map = {
        'trialing': ChefMembership.Status.TRIAL,
        'active': ChefMembership.Status.ACTIVE,
        'past_due': ChefMembership.Status.PAST_DUE,
        'canceled': ChefMembership.Status.CANCELLED,
        'paused': ChefMembership.Status.PAUSED,
        'unpaid': ChefMembership.Status.PAST_DUE,
    }
    status = status_map.get(stripe_status, ChefMembership.Status.ACTIVE)
    
    with transaction.atomic():
        membership, created = ChefMembership.objects.update_or_create(
            chef=chef,
            defaults={
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription.id,
                'billing_cycle': billing_cycle,
                'status': status,
            }
        )
        
        # Update billing period
        period_start = getattr(subscription, 'current_period_start', None)
        period_end = getattr(subscription, 'current_period_end', None)
        if period_start and period_end:
            membership.update_billing_period(period_start, period_end)
        
        # Handle trial period
        trial_start = getattr(subscription, 'trial_start', None)
        trial_end = getattr(subscription, 'trial_end', None)
        if trial_start:
            membership.trial_started_at = timezone.datetime.fromtimestamp(
                trial_start, tz=timezone.utc
            )
        if trial_end:
            membership.trial_ends_at = timezone.datetime.fromtimestamp(
                trial_end, tz=timezone.utc
            )
        membership.save()
        
        action = "Created" if created else "Updated"
        logger.info(
            f"{action} membership for chef {chef.id} "
            f"(subscription: {subscription.id}, status: {status})"
        )


def handle_subscription_updated(subscription):
    """
    Handle customer.subscription.updated event.
    
    Updates the ChefMembership status and billing period when
    the subscription changes in Stripe.
    
    Args:
        subscription: Stripe subscription object
    """
    if not is_membership_subscription(subscription):
        logger.debug("Ignoring non-membership subscription updated event")
        return
    
    try:
        membership = ChefMembership.objects.get(
            stripe_subscription_id=subscription.id
        )
    except ChefMembership.DoesNotExist:
        # Might be a new subscription - try to handle as created
        logger.info(
            f"Subscription {subscription.id} not found, "
            "attempting to handle as new subscription"
        )
        handle_subscription_created(subscription)
        return
    
    # Map Stripe status to our status
    stripe_status = getattr(subscription, 'status', 'active')
    status_map = {
        'trialing': ChefMembership.Status.TRIAL,
        'active': ChefMembership.Status.ACTIVE,
        'past_due': ChefMembership.Status.PAST_DUE,
        'canceled': ChefMembership.Status.CANCELLED,
        'paused': ChefMembership.Status.PAUSED,
        'unpaid': ChefMembership.Status.PAST_DUE,
    }
    new_status = status_map.get(stripe_status, membership.status)
    
    with transaction.atomic():
        membership.status = new_status
        
        # Update billing period
        period_start = getattr(subscription, 'current_period_start', None)
        period_end = getattr(subscription, 'current_period_end', None)
        if period_start and period_end:
            membership.update_billing_period(period_start, period_end)
        
        # Check for cancellation
        if stripe_status == 'canceled':
            cancel_at = getattr(subscription, 'canceled_at', None)
            if cancel_at:
                membership.cancelled_at = timezone.datetime.fromtimestamp(
                    cancel_at, tz=timezone.utc
                )
        
        membership.save()
        
        logger.info(
            f"Updated membership {membership.id} for chef {membership.chef_id} "
            f"(status: {new_status})"
        )


def handle_subscription_deleted(subscription):
    """
    Handle customer.subscription.deleted event.
    
    Marks the membership as cancelled when the subscription
    is deleted in Stripe.
    
    Args:
        subscription: Stripe subscription object
    """
    if not is_membership_subscription(subscription):
        logger.debug("Ignoring non-membership subscription deleted event")
        return
    
    try:
        membership = ChefMembership.objects.get(
            stripe_subscription_id=subscription.id
        )
    except ChefMembership.DoesNotExist:
        logger.warning(
            f"Received deletion for unknown subscription {subscription.id}"
        )
        return
    
    membership.cancel()
    logger.info(
        f"Cancelled membership {membership.id} for chef {membership.chef_id}"
    )


def handle_invoice_paid(invoice):
    """
    Handle invoice.paid event.
    
    Logs the payment and ensures the membership is active.
    
    Args:
        invoice: Stripe invoice object
    """
    subscription_id = getattr(invoice, 'subscription', None)
    if not subscription_id:
        logger.debug("Ignoring invoice.paid without subscription")
        return
    
    try:
        membership = ChefMembership.objects.get(
            stripe_subscription_id=subscription_id
        )
    except ChefMembership.DoesNotExist:
        logger.debug(
            f"Invoice paid for unknown subscription {subscription_id}, "
            "may not be a membership subscription"
        )
        return
    
    # Log the payment
    amount_paid = getattr(invoice, 'amount_paid', 0)
    invoice_id = getattr(invoice, 'id', None)
    payment_intent = getattr(invoice, 'payment_intent', None)
    charge = getattr(invoice, 'charge', None)
    
    # Get billing period from invoice lines
    period_start = None
    period_end = None
    lines = getattr(invoice, 'lines', None)
    if lines:
        data = getattr(lines, 'data', [])
        if data:
            period = getattr(data[0], 'period', {})
            period_start = period.get('start')
            period_end = period.get('end')
    
    # Convert timestamps to datetime
    if period_start:
        period_start = timezone.datetime.fromtimestamp(
            period_start, tz=timezone.utc
        )
    if period_end:
        period_end = timezone.datetime.fromtimestamp(
            period_end, tz=timezone.utc
        )
    
    with transaction.atomic():
        # Check for duplicate payment log
        if not MembershipPaymentLog.objects.filter(
            stripe_invoice_id=invoice_id
        ).exists():
            MembershipPaymentLog.log_payment(
                membership=membership,
                amount_cents=amount_paid,
                invoice_id=invoice_id,
                payment_intent_id=payment_intent,
                charge_id=charge,
                period_start=period_start,
                period_end=period_end,
            )
            logger.info(
                f"Logged payment of ${amount_paid/100:.2f} for "
                f"membership {membership.id}"
            )
        
        # Ensure membership is active
        if membership.status in [
            ChefMembership.Status.TRIAL,
            ChefMembership.Status.PAST_DUE
        ]:
            membership.activate()
            logger.info(f"Activated membership {membership.id} after payment")


def handle_invoice_payment_failed(invoice):
    """
    Handle invoice.payment_failed event.
    
    Marks the membership as past due when payment fails.
    
    Args:
        invoice: Stripe invoice object
    """
    subscription_id = getattr(invoice, 'subscription', None)
    if not subscription_id:
        return
    
    try:
        membership = ChefMembership.objects.get(
            stripe_subscription_id=subscription_id
        )
    except ChefMembership.DoesNotExist:
        return
    
    membership.mark_past_due()
    logger.warning(
        f"Payment failed for membership {membership.id} "
        f"(chef: {membership.chef_id})"
    )
    
    # TODO: Send notification to chef about failed payment

