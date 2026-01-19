from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Chef
from django.utils import timezone
from meals.models import ChefMealEvent, STATUS_SCHEDULED, STATUS_OPEN
from local_chefs.models import ChefPostalCode

from .tasks import notify_waitlist_subscribers_for_chef, notify_area_waitlist_users

# Note: DALL-E image generation for chef profile pics has been removed.
# Chefs should upload their own profile pictures.

@receiver(post_save, sender=ChefMealEvent)
def on_meal_event_saved(sender, instance: ChefMealEvent, created, **kwargs):
    """When a chef creates or updates an orderable event, notify waitlist subscribers once.

    This is a simplified trigger: if an event is orderable (scheduled/open, before cutoff,
    and not at max capacity), fire a background task that emails all active subscribers
    and deactivates their subscriptions to avoid duplicate sends.
    """
    try:
        now = timezone.now()
        if instance.status in [STATUS_SCHEDULED, STATUS_OPEN] and instance.order_cutoff_time and instance.order_cutoff_time > now:
            if instance.max_orders is None or instance.orders_count < instance.max_orders:
                notify_waitlist_subscribers_for_chef(instance.chef_id)
    except Exception:
        # Never raise in signal handler
        return


@receiver(post_save, sender=ChefPostalCode)
def on_chef_postal_code_added(sender, instance: ChefPostalCode, created, **kwargs):
    """When a verified chef adds a new postal code, notify users waiting in that area.
    
    This triggers the area waitlist notification system to let users know a chef
    is now available in their area.
    """
    if not created:
        return
    
    try:
        chef = instance.chef
        postal_code_obj = instance.postal_code
        
        # Only notify if the chef is verified
        if not chef.is_verified:
            return
        
        # Get the postal code and country
        postal_code = postal_code_obj.code
        country = str(postal_code_obj.country) if postal_code_obj.country else None
        
        if not postal_code or not country:
            return
        
        # Get chef username for the notification
        chef_username = getattr(chef.user, 'username', 'chef')
        
        # Send the notification
        notify_area_waitlist_users(postal_code, country, chef_username)
        
    except Exception:
        # Never raise in signal handler
        return
