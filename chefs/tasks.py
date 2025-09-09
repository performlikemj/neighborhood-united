from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
import os

from .models import Chef, ChefWaitlistSubscription, ChefWaitlistConfig
from meals.email_service import send_system_update_email


@shared_task
def send_chef_waitlist_notifications(chef_id: int, activation_epoch: int) -> None:
    """Notify subscribers that a chef is active again.

    Uses the assistant email template system for consistent formatting.
    """
    # Feature toggle guard
    if not ChefWaitlistConfig.get_enabled():
        return

    try:
        chef = Chef.objects.select_related('user').get(id=chef_id)
    except Chef.DoesNotExist:
        return

    base_url = os.getenv('STREAMLIT_URL') or ''
    chef_username = getattr(chef.user, 'username', 'chef')
    # Prefer by-username public route
    chef_profile_url = f"{base_url}/chefs/{chef_username}" if base_url else f"/chefs/{chef_username}"

    # Batch fetch subscriptions requiring notification
    qs = (
        ChefWaitlistSubscription.objects
        .select_related('user')
        .filter(
            chef=chef,
            active=True,
        )
        .filter(Q(last_notified_epoch__lt=activation_epoch) | Q(last_notified_epoch__isnull=True))
        .filter(user__email_confirmed=True)
    )

    now = timezone.now()
    subject = f"Chef {chef_username} is now accepting orders"
    message = f"Chef {chef_username} just opened orders. View their profile: {chef_profile_url}"

    user_ids = list(qs.values_list('user_id', flat=True))
    if not user_ids:
        return

    # Queue a single assistant-driven email job for all targets
    try:
        send_system_update_email.delay(
            subject,
            message,
            user_ids=user_ids,
            template_key='chef_waitlist_activation',
            template_context={'chef_username': chef_username, 'chef_profile_url': chef_profile_url},
        )
    except Exception:
        # If queueing fails, do not update subscriptions, so a later retry can notify
        return

    # Mark as notified for this epoch (after scheduling)
    (
        ChefWaitlistSubscription.objects
        .filter(
            chef=chef,
            active=True,
            user_id__in=user_ids,
        )
        .filter(Q(last_notified_epoch__lt=activation_epoch) | Q(last_notified_epoch__isnull=True))
        .update(last_notified_epoch=activation_epoch, last_notified_at=now)
    )

    return


@shared_task
def notify_waitlist_subscribers_for_chef(chef_id: int) -> None:
    """Simplified: notify all active subscribers that a chef now has open orderable events.

    - Ignores cooldowns/epochs; sends once and deactivates the subscriptions.
    - Uses the same assistant-driven email template for consistency.
    """
    try:
        chef = Chef.objects.select_related('user').get(id=chef_id)
    except Chef.DoesNotExist:
        return

    base_url = os.getenv('STREAMLIT_URL') or ''
    chef_username = getattr(chef.user, 'username', 'chef')
    chef_profile_url = f"{base_url}/chefs/{chef_username}" if base_url else f"/chefs/{chef_username}"

    # Active subscriptions (only confirmed emails)
    qs = (
        ChefWaitlistSubscription.objects
        .select_related('user')
        .filter(chef=chef, active=True, user__email_confirmed=True)
    )

    user_ids = list(qs.values_list('user_id', flat=True))
    if not user_ids:
        return

    subject = f"Chef {chef_username} is now accepting orders"
    message = f"Chef {chef_username} just opened orders. View their profile: {chef_profile_url}"

    try:
        send_system_update_email.delay(
            subject,
            message,
            user_ids=user_ids,
            template_key='chef_waitlist_activation',
            template_context={'chef_username': chef_username, 'chef_profile_url': chef_profile_url},
        )
    except Exception:
        # If queueing fails, do not change subscriptions; a later retry may succeed
        return

    now = timezone.now()
    # Deactivate subscriptions after scheduling to avoid duplicate notifications
    ChefWaitlistSubscription.objects.filter(chef=chef, active=True, user_id__in=user_ids).update(
        active=False,
        last_notified_epoch=None,
        last_notified_at=now,
    )

    return
