# meals/signals.py
from django.db.models.signals import post_save, m2m_changed, post_delete, pre_save
from django.dispatch import receiver
from .models import Meal, MealPlan, ChefMealOrder, ChefMealEvent
from django.db import transaction
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake, ChatThread, WeeklyAnnouncement, UserMessage
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
from meals.meal_assistant_implementation import MealPlanningAssistant
from django.utils import timezone
import logging
from datetime import timedelta, date
from celery import shared_task

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
    if user.unsubscribed_from_emails:
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

# New signal handlers for ChefMealEvent changes
@receiver(pre_save, sender=ChefMealEvent)
def chef_meal_event_pre_save(sender, instance, **kwargs):
    """
    Track changes to ChefMealEvent for email notification purposes.
    """
    if instance.pk:
        try:
            prev_state = ChefMealEvent.objects.get(pk=instance.pk)
            # Store previous state for comparison in post_save
            instance._prev_status = prev_state.status
            instance._prev_event_date = prev_state.event_date
            instance._prev_event_time = prev_state.event_time
            instance._prev_current_price = prev_state.current_price
        except ChefMealEvent.DoesNotExist:
            pass
    else:
        # New instance
        instance._prev_status = None
        instance._prev_event_date = None
        instance._prev_event_time = None
        instance._prev_current_price = None

@receiver(post_save, sender=ChefMealEvent)
def notify_users_of_chef_meal_event_changes(sender, instance, created, **kwargs):
    """
    Notify affected users about changes to ChefMealEvent.
    
    This signal handler will:
    1. Detect changes to event status, date, time, price
    2. Find users affected by these changes
    3. Notify them directly through the AI assistant
    """
    # Skip if this is a brand new event with no orders
    if created:
        return
    
    # Get changes by comparing with stored previous values
    changes = {}
    
    # Check status change
    if hasattr(instance, '_prev_status') and instance._prev_status != instance.status:
        changes['status'] = {
            'from': instance._prev_status,
            'to': instance.status
        }
    
    # Check date/time changes
    if (hasattr(instance, '_prev_event_date') and instance._prev_event_date != instance.event_date) or \
       (hasattr(instance, '_prev_event_time') and instance._prev_event_time != instance.event_time):
        changes['schedule'] = {
            'from': f"{getattr(instance, '_prev_event_date', 'unknown')} at {getattr(instance, '_prev_event_time', 'unknown')}",
            'to': f"{instance.event_date} at {instance.event_time}"
        }
    
    # Check price changes
    if hasattr(instance, '_prev_current_price') and instance._prev_current_price != instance.current_price:
        changes['price'] = {
            'from': float(instance._prev_current_price) if instance._prev_current_price else 0,
            'to': float(instance.current_price) if instance.current_price else 0
        }
    
    # If no changes detected that we care about, skip notification
    if not changes:
        return
        
    # Get all customers who have orders for this event
    affected_orders = instance.orders.select_related('customer').all()
    
    # Process each affected user
    for order in affected_orders:
        user = order.customer
        
        # Skip if user has no email confirmed
        if not user.email_confirmed:
            continue
            
        # Generate personalized message
        message = generate_chef_event_change_message(instance, changes, user)
        
        # Send notification
        send_chef_event_notification.delay(user.id, message, instance.id, changes)

def generate_chef_event_change_message(event, changes, user):
    """
    Generate a personalized message about changes to a ChefMealEvent.
    
    Args:
        event: The ChefMealEvent instance
        changes: Dictionary of changes detected
        user: The user to notify
    
    Returns:
        A formatted message string
    """
    chef_name = event.chef.user.get_full_name() or event.chef.user.username
    meal_name = event.meal.name
    
    # Build a message based on the type of changes
    if 'status' in changes and changes['status']['to'] == 'cancelled':
        return (
            f"Hi {user.first_name},\n\n"
            f"I wanted to let you know that Chef {chef_name} has unfortunately had to cancel "
            f"their '{meal_name}' event that was scheduled for {event.event_date.strftime('%A, %B %d')}. "
            f"Your order has been automatically cancelled, and any payment will be refunded according to the chef's cancellation policy.\n\n"
            f"Would you like me to suggest some alternatives for that day?"
        )
    
    if 'schedule' in changes:
        return (
            f"Hi {user.first_name},\n\n"
            f"I wanted to let you know that Chef {chef_name} has rescheduled their '{meal_name}' event from "
            f"{changes['schedule']['from']} to {changes['schedule']['to']}.\n\n"
            f"Your order is still active for this new time. If this change doesn't work for you, "
            f"you can cancel your order through your orders dashboard. Would you like me to help with that?"
        )
    
    if 'price' in changes and changes['price']['to'] < changes['price']['from']:
        return (
            f"Hi {user.first_name},\n\n"
            f"Good news! The price for Chef {chef_name}'s '{meal_name}' event has decreased from "
            f"${changes['price']['from']:.2f} to ${changes['price']['to']:.2f} per serving. "
            f"This price change will be automatically applied to your order.\n\n"
            f"Let me know if you'd like to modify your order quantity to take advantage of this better price!"
        )
    
    # Generic message for other changes
    return (
        f"Hi {user.first_name},\n\n"
        f"I wanted to let you know about an update to your order for Chef {chef_name}'s '{meal_name}' "
        f"event on {event.event_date.strftime('%A, %B %d')}. "
        f"Please check your orders dashboard for details, or ask me if you need any assistance."
    )

@shared_task
def send_chef_event_notification(user_id, message, event_id, changes):
    """
    Task to send a notification about a chef meal event change to a user.
    
    This is a Celery task to ensure email delivery doesn't block the main thread.
    """
    try:
        # Get the user
        user = CustomUser.objects.get(id=user_id)
        
        # Initialize the assistant
        assistant = MealPlanningAssistant(user_id=user_id)
        
        # Get the active chat thread or create one if it doesn't exist
        chat_thread = ChatThread.objects.filter(user=user, is_active=True).first()
        if not chat_thread:
            # Create a new thread if none exists
            today = timezone.localdate()
            week_end = today + timedelta(days=(6-today.weekday()))
            chat_thread = ChatThread.objects.create(
                user=user, 
                is_active=True,
                title=f"Conversation for week of {today.strftime('%b %d')} - {week_end.strftime('%b %d')}"
            )
        
        # Add the assistant message to the thread
        UserMessage.objects.create(
            user=user,
            thread=chat_thread,
            message="",  # Empty message since this is assistant-initiated
            response=message
        )
        
        # Update the thread history
        history = chat_thread.openai_input_history or []
        if not history:
            history.append({"role": "system", "content": assistant.system_message})
        
        # Add the assistant's message to history
        history.append({"role": "assistant", "content": message})
        chat_thread.openai_input_history = history
        chat_thread.save(update_fields=['openai_input_history'])
        
        # Send an email notification via n8n webhook if configured
        webhook_url = getattr(settings, 'N8N_ASSISTANT_NOTIFICATION_WEBHOOK', None)
        if webhook_url:
            subject = "Update about your chef meal order"
            
            # Customize subject based on change type
            if 'status' in changes and changes['status']['to'] == 'cancelled':
                subject = "Your chef meal order has been cancelled"
            elif 'schedule' in changes:
                subject = "Your chef meal event has been rescheduled"
            elif 'price' in changes:
                subject = "Price update for your chef meal order"
            
            payload = {
                "user_id": user_id,
                "user_email": user.email,
                "message": message,
                "subject": subject,
                "event_id": event_id,
                "notification_type": "chef_event_update"
            }
            
            try:
                response = requests.post(webhook_url, json=payload, timeout=5)
                if response.status_code != 200:
                    logger.error(f"Failed to send notification email via webhook: {response.status_code} {response.text}")
            except Exception as e:
                logger.error(f"Exception sending notification email: {str(e)}")
    
    except CustomUser.DoesNotExist:
        logger.error(f"User with ID {user_id} not found when sending chef event notification")
    except Exception as e:
        logger.error(f"Error sending chef event notification: {str(e)}")

# Weekly conversation reset feature
@shared_task
def create_weekly_chat_threads():
    """
    Task to create new chat threads for all users at the start of each week.
    
    This should be scheduled to run every Monday at 00:05.
    """
    # Get all users with email confirmed
    active_users = CustomUser.objects.filter(email_confirmed=True)
    today = timezone.localdate()
    
    # Only run on Mondays
    if today.weekday() != 0:  # 0 = Monday
        return
    
    for user in active_users:
        # Mark all existing threads as inactive
        ChatThread.objects.filter(user=user, is_active=True).update(is_active=False)
        
        # Calculate week range
        week_end = today + timedelta(days=6)
        
        # Create a new thread for this week
        thread = ChatThread.objects.create(
            user=user,
            title=f"Conversation for week of {today.strftime('%b %d')} - {week_end.strftime('%b %d')}",
            is_active=True
        )
        
        # Get weekly announcements for this user
        week_start = WeeklyAnnouncement.get_week_start(today)
        
        # Get country-specific and global announcements
        country_code = None
        if hasattr(user, 'address') and user.address and user.address.country:
            country_code = user.address.country.code
        
        announcement_text = ""
        
        # Get global announcement
        global_announcement = WeeklyAnnouncement.objects.filter(
            week_start=week_start,
            country__isnull=True
        ).first()
        
        if global_announcement:
            announcement_text += global_announcement.content + "\n\n"
        
        # Get region-specific announcement if applicable
        if country_code:
            regional_announcement = WeeklyAnnouncement.objects.filter(
                week_start=week_start,
                country=country_code
            ).first()
            
            if regional_announcement:
                announcement_text += regional_announcement.content
        
        # If we have any announcements, add them to the thread
        if announcement_text.strip():
            # Initialize assistant to get system message
            assistant = MealPlanningAssistant(user_id=user.id)
            
            # Initialize thread history with system message and announcements
            thread.openai_input_history = [
                {"role": "system", "content": assistant.system_message},
                {"role": "system", "content": f"Weekly Announcements:\n{announcement_text.strip()}"}
            ]
            thread.save(update_fields=['openai_input_history'])
            
            # Add the announcement as an assistant message
            formatted_announcement = (
                f"Hi {user.first_name},\n\n"
                f"Welcome to a new week! Here are some important announcements:\n\n"
                f"{announcement_text.strip()}\n\n"
                f"Let me know if you need any assistance with your meal planning this week!"
            )
            
            UserMessage.objects.create(
                user=user,
                thread=thread,
                message="",  # Empty user message since this is assistant-initiated
                response=formatted_announcement
            )
