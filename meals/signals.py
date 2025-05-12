# meals/signals.py
from django.db.models.signals import post_save, m2m_changed, post_delete, pre_save
from django.dispatch import receiver
from .models import Meal, MealPlan, ChefMealOrder
from django.db import transaction
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake
from custom_auth.models import CustomUser
from django.db import transaction
import requests
from django.core.files.base import ContentFile
from openai import OpenAI
from django.conf import settings
from rest_framework.test import APIRequestFactory
from meals.email_service import generate_shopping_list, generate_user_summary, mark_summary_stale
from meals.meal_instructions import generate_bulk_prep_instructions
from meals.meal_plan_service import create_meal_plan_for_new_user
from meals.pantry_management import assign_pantry_tags
import logging

logger = logging.getLogger(__name__)

def trigger_assign_pantry_tags(sender, instance, created, **kwargs):
    if created:
        assign_pantry_tags.delay(instance.id)

@receiver(m2m_changed, sender=MealPlan.meal.through)
def mealplan_meal_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.has_changes = True
        instance.is_approved = False  # Reset approval when changes are detected
        instance.save()

@receiver(pre_save, sender=MealPlan)
def pre_save_mealplan(sender, instance, **kwargs):
    if instance.pk:
        previous = MealPlan.objects.get(pk=instance.pk)
        instance._previous_is_approved = previous.is_approved
        instance._previous_has_changes = previous.has_changes
    else:
        instance._previous_is_approved = None
        instance._previous_has_changes = None

@receiver(post_save, sender=MealPlan)
def send_meal_plan_email(sender, instance, **kwargs):
    user = instance.user
    if not user.email_meal_plan_saved:
        return

    # Check if approval status changed from unapproved to approved and has_changes from True to False
    if (
        instance.is_approved and not instance.has_changes and
        (instance._previous_is_approved != instance.is_approved or
         instance._previous_has_changes != instance.has_changes)
    ):
        generate_shopping_list.delay(instance.id)
        if instance.meal_prep_preference == 'one_day_prep':
            generate_bulk_prep_instructions.delay(instance.id)

@receiver(post_save, sender=GoalTracking)
@receiver(post_save, sender=UserHealthMetrics)
@receiver(post_save, sender=CalorieIntake)
def handle_model_update(sender, instance, **kwargs):
    # Check if the signal is post_save and whether the instance was just created
    created = kwargs.get('created', False)

    if hasattr(instance, 'user_id'):
        user_id = instance.user_id
    elif hasattr(instance, 'user'):
        user_id = instance.user.id
    else:
        return  # Exit if no user is associated with the instance
        
    # Get the user object
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return
        
    if not user.email_confirmed:
        return  # Skip if email is not confirmed
        
    print(f"Detected change for user with ID: {user_id}")
    
    # Use transaction.on_commit to ensure this runs after the transaction has committed
    def trigger_summary_stale():
        # Mark today's summary as stale and trigger regeneration
        mark_summary_stale(user)

    transaction.on_commit(trigger_summary_stale)

@receiver(post_save, sender=CustomUser)
def create_meal_plan_on_user_registration(sender, instance, created, **kwargs):
    if created and instance.email_confirmed:
        # Define a callback function to trigger after the transaction commits
        def trigger_meal_plan_creation():
            create_meal_plan_for_new_user.delay(instance.id)  # Queue the task to create a meal plan

        transaction.on_commit(trigger_meal_plan_creation)
        
    # For any update to a user (created or modified), mark their daily summary as stale
    elif not created and instance.email_confirmed:
        def trigger_summary_stale():
            mark_summary_stale(instance)
            
        transaction.on_commit(trigger_summary_stale)

@receiver(post_save, sender=ChefMealOrder)
def push_order_event(sender, instance, created, **kwargs):
    """
    Send order events to n8n webhook for email notifications.
    
    This handler is triggered whenever a ChefMealOrder is saved/updated.
    It will send relevant event data to the n8n webhook for email notifications.
    """
    import requests
    import json
    
    # Determine event type
    if created:
        kind = 'order.created'
    elif instance.status in ['cancelled', 'refunded']:
        kind = f'order.{instance.status}'
    else:
        # For quantity changes and other updates
        kind = 'order.quantity_changed'
    
    # Prepare the payload
    payload = {
        "event": kind,
        "order_id": instance.id,
        "customer_email": instance.customer.email,
        "customer_name": instance.customer.get_full_name(),
        "meal_name": instance.meal_event.meal.name,
        "quantity": instance.quantity,
        "event_date": instance.meal_event.event_date.strftime('%Y-%m-%d'),
        "event_time": instance.meal_event.event_time.strftime('%H:%M'),
        "chef_name": instance.meal_event.chef.user.get_full_name(),
        "unit_price": float(instance.unit_price) if instance.unit_price else None,
        "total_price": float(instance.unit_price * instance.quantity) if instance.unit_price else None,
        "cutoff_time": instance.meal_event.order_cutoff_time.strftime('%Y-%m-%d %H:%M')
    }
    
    # Get the webhook URL from settings
    from django.conf import settings
    webhook_url = getattr(settings, 'N8N_ORDER_EVENTS_WEBHOOK_URL', None)
    
    # Send the webhook if URL is configured
    if webhook_url:
        try:
            response = requests.post(webhook_url, json=payload, timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to send order event to n8n: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Exception sending order event to n8n: {str(e)}")
    else:
        logger.warning("N8N_ORDER_EVENTS_WEBHOOK_URL not configured, skipping webhook")
