# meals/signals.py
from django.db.models.signals import post_save, m2m_changed, post_delete, pre_save
from django.dispatch import receiver
from .models import Meal, MealPlan, ChefMealOrder, ChefMealEvent
from django.db import transaction
from customer_dashboard.models import ChatThread, WeeklyAnnouncement, UserMessage
from custom_auth.models import CustomUser
from django.db import transaction
import requests
from django.core.files.base import ContentFile
try:
    from groq import Groq
except ImportError:
    Groq = None
from django.conf import settings
from rest_framework.test import APIRequestFactory
from meals.email_service import generate_shopping_list, generate_user_summary, mark_summary_stale
from meals.feature_flags import meal_plan_notifications_enabled
from meals.meal_instructions import generate_bulk_prep_instructions
from meals.meal_plan_service import create_meal_plan_for_new_user
from meals.pantry_management import assign_pantry_tags
from django.utils import timezone
import logging
from datetime import timedelta, date
import traceback
import os
from utils.redis_client import redis_client
logger = logging.getLogger(__name__)

def trigger_assign_pantry_tags(sender, instance, created, **kwargs):
    if created:
        assign_pantry_tags(instance.id)

@receiver(m2m_changed, sender=MealPlan.meal.through)
def mealplan_meal_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        # Record change and require manual re‑approval
        instance.has_changes = True
        instance.is_approved = False
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
    if not meal_plan_notifications_enabled():
        logger.info(
            "Meal-plan email notifications disabled; skipping shopping list for MealPlan %s",
            instance.id,
        )
        return

    user = instance.user
    if user.unsubscribed_from_emails:
        return

    if getattr(instance, "_suppress_auto_approval_email", False):
        try:
            delattr(instance, "_suppress_auto_approval_email")
        except AttributeError:
            pass
        logger.debug(
            "Skipping shopping list email for MealPlan %s due to Groq auto-approval suppression.",
            instance.id,
        )
        return

    # Check if approval status changed from unapproved to approved and has_changes from True to False
    if (
        instance.is_approved and not instance.has_changes and
        (instance._previous_is_approved != instance.is_approved or
         instance._previous_has_changes != instance.has_changes)
    ):
        generate_shopping_list(instance.id)
        if instance.meal_prep_preference == 'one_day_prep':
            # Generate bulk prep and send by default
            generate_bulk_prep_instructions(instance.id, send_via_assistant=True)

# Health tracking signal handlers removed (GoalTracking, UserHealthMetrics, CalorieIntake)

@receiver(post_save, sender=CustomUser)
def create_meal_plan_on_user_registration(sender, instance, created, **kwargs):
    """
    Create an initial meal plan once a user's email is confirmed.
    - On create: if email_confirmed is True, queue meal plan generation.
    - On update: if email_confirmed transitioned from False->True, queue meal plan generation (idempotent for current week).
    For all updates with confirmed email, mark daily summary stale.
    """
    from meals.models import MealPlan
    from datetime import timedelta
    from django.utils import timezone

    def _queue_meal_plan_if_needed():
        # Compute current week window (Monday..Sunday) in server tz
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        # Avoid duplicate plan generation for this user/week
        exists = MealPlan.objects.filter(user=instance, week_start_date=week_start, week_end_date=week_end).exists()
        if not exists:
            create_meal_plan_for_new_user(instance.id)

    if created:
        if instance.email_confirmed and getattr(instance, 'auto_meal_plans_enabled', True):
            transaction.on_commit(_queue_meal_plan_if_needed)
    else:
        # Detect False -> True transition
        prev_confirmed = getattr(instance, '_previous_email_confirmed', None)
        if instance.email_confirmed and prev_confirmed is False and getattr(instance, 'auto_meal_plans_enabled', True):
            transaction.on_commit(_queue_meal_plan_if_needed)

        if instance.email_confirmed:
            def trigger_summary_stale():
                mark_summary_stale(instance)
            transaction.on_commit(trigger_summary_stale)

@receiver(pre_save, sender=CustomUser)
def _track_prev_email_confirmed(sender, instance, **kwargs):
    """Track previous email_confirmed value to detect transitions on post_save."""
    if instance.pk:
        try:
            previous = CustomUser.objects.get(pk=instance.pk)
            instance._previous_email_confirmed = bool(previous.email_confirmed)
        except CustomUser.DoesNotExist:
            instance._previous_email_confirmed = None
    else:
        instance._previous_email_confirmed = None

@receiver(post_save, sender=ChefMealOrder)
def push_order_event(sender, instance, created, **kwargs):
    """
    Send order events via assistant email notifications.
    
    This handler is triggered whenever a ChefMealOrder is saved/updated.
    It will send relevant event data via the assistant's email functionality.
    """
    # Determine event type and message content
    if created:
        # Group newly created ChefMealOrder rows by parent Order to avoid sending one email per event
        try:
            schedule_grouped_order_email(instance.order.id, instance.customer.id)
        except Exception as e:
            logger.error(f"Failed to schedule grouped order email for order {instance.order.id}: {e}")
        return
    elif instance.status in ['cancelled', 'refunded']:
        kind = f'order.{instance.status}'
        subject = f"Your chef meal order has been {instance.status}"
        if instance.status == 'cancelled':
            message = (
                f"Your order for {instance.meal_event.meal.name} by Chef "
                f"{instance.meal_event.chef.user.get_full_name()} has been cancelled.\n\n"
                f"If you cancelled this order yourself, no further action is needed. "
                f"If this was cancelled by the chef or due to an issue, any payment "
                f"will be refunded according to our cancellation policy.\n\n"
                f"Would you like me to help you find alternative meal options for "
                f"{instance.meal_event.event_date.strftime('%A, %B %d')}?"
            )
        else:  # refunded
            message = (
                f"Your order for {instance.meal_event.meal.name} by Chef "
                f"{instance.meal_event.chef.user.get_full_name()} has been refunded.\n\n"
                f"The refund amount of ${float(instance.unit_price * instance.quantity):.2f} "
                f"will be processed back to your original payment method within 3-5 business days.\n\n"
                f"If you have any questions about this refund, please let me know!"
            )
    else:
        # For quantity changes and other updates
        kind = 'order.quantity_changed'
        subject = "Your chef meal order has been updated"
        message = (
            f"Your order for {instance.meal_event.meal.name} by Chef "
            f"{instance.meal_event.chef.user.get_full_name()} has been updated.\n\n"
            f"Updated Order Details:\n"
            f"• Quantity: {instance.quantity} serving{'s' if instance.quantity > 1 else ''}\n"
            f"• Total Price: ${float(instance.unit_price * instance.quantity):.2f}\n\n"
            f"You can view your complete order details in your dashboard."
        )
    
    # Send notification via assistant for non-created updates (quantity changes/cancel/refund)
    send_chef_order_notification(instance.customer.id, message, subject)


def schedule_grouped_order_email(order_id: int, user_id: int, debounce_seconds: int = 8) -> None:
    """
    Debounce multiple ChefMealOrder creations that belong to the same Order and
    send a single aggregated confirmation email.
    """
    # Record the user for this order (used by the task)
    redis_client.set(f"order_group_queue:{order_id}:user", user_id, timeout=3600)

    # Use a scheduled flag to avoid duplicate processing
    scheduled_key = f"order_group_queue:{order_id}:scheduled"
    if not redis_client.exists(scheduled_key):
        # Mark as scheduled with a short TTL
        redis_client.set(scheduled_key, "1", timeout=max(debounce_seconds * 4, 60))
        # NOTE: Previously used countdown for debouncing, now executes immediately
        send_grouped_order_confirmation(order_id)

def send_chef_order_notification(user_id, message, subject):
    """
    Task to send a chef order notification via the assistant.
    """
    try:
        from meals.meal_assistant_implementation import MealPlanningAssistant
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user_id,
            message_content=message,
            subject=subject,
            template_key='system_update'
        )
        
        if result.get("status") == "success":
            logger.info(f"Successfully sent chef order notification to user {user_id}")
        else:
            logger.warning(f"Chef order notification result for user {user_id}: {result}")
            
    except Exception as e:
        logger.error(f"Error sending chef order notification to user {user_id}: {str(e)}")


def send_grouped_order_confirmation(order_id: int):
    """
    Build and send a single confirmation email summarizing all ChefMealOrder items
    for the given Order.
    """
    try:
        from meals.models import ChefMealOrder, Order
        from meals.meal_assistant_implementation import MealPlanningAssistant

        order = Order.objects.select_related('customer').get(id=order_id)
        user = order.customer

        # Collect active (placed/confirmed) items for this order
        items = (
            ChefMealOrder.objects
            .filter(order_id=order_id, status__in=['placed', 'confirmed'])
            .select_related('meal_event', 'meal_event__meal', 'meal_event__chef', 'meal_event__chef__user')
            .order_by('created_at')
        )

        if not items:
            logger.info(f"No active items to include for grouped order email: order {order_id}")
            return

        # Build summary lines and compute totals
        lines = []
        total_amount = 0.0
        for it in items:
            meal_name = it.meal_event.meal.name
            chef_name = it.meal_event.chef.user.get_full_name() or it.meal_event.chef.user.username
            evt_date = it.meal_event.event_date.strftime('%A, %B %d, %Y')
            evt_time = it.meal_event.event_time.strftime('%I:%M %p')
            qty = it.quantity or 1
            line_total = float((it.unit_price or 0) * qty)
            total_amount += line_total
            cutoff = it.meal_event.order_cutoff_time.strftime('%A, %B %d at %I:%M %p') if it.meal_event.order_cutoff_time else 'N/A'
            lines.append(
                f"• {meal_name} by Chef {chef_name} — {qty} serving{'s' if qty > 1 else ''} — {evt_time} on {evt_date} — ${line_total:.2f} (cutoff: {cutoff})"
            )

        message = (
            f"Great news! Your order has been confirmed.\n\n"
            f"Order Details:\n"
            + "\n".join(lines)
            + "\n\n"
            f"Order Total: ${total_amount:.2f}\n\n"
            f"You can view and manage your orders anytime in your dashboard."
        )

        subject = "Your chef meal order has been confirmed"

        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content=message,
            subject=subject,
            template_key='system_update'
        )

        if result.get("status") == "success":
            logger.info(f"Sent grouped order confirmation to user {user.id} for order {order_id}")
        else:
            logger.warning(f"Grouped order confirmation result for user {user.id}, order {order_id}: {result}")

    except Exception as e:
        logger.error(f"Error sending grouped order confirmation for order {order_id}: {str(e)}")

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
    Notify affected users about changes to ChefMealEvent via assistant.
    
    This signal handler will:
    1. Detect changes to event status, date, time, price
    2. Find users affected by these changes
    3. Notify them via the assistant's email functionality
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
            
        # Generate personalized message and subject
        message = generate_chef_event_change_message(instance, changes, user)
        subject = generate_chef_event_change_subject(changes)
        
        # Send notification via assistant
        send_chef_event_notification(user.id, message, subject, instance.id, changes)

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
            f"I wanted to let you know that Chef {chef_name} has unfortunately had to cancel "
            f"their '{meal_name}' event that was scheduled for {event.event_date.strftime('%A, %B %d')}. "
            f"Your order has been automatically cancelled, and any payment will be refunded according to the chef's cancellation policy.\n\n"
            f"Would you like me to suggest some alternatives for that day?"
        )
    
    if 'schedule' in changes:
        return (
            f"I wanted to let you know that Chef {chef_name} has rescheduled their '{meal_name}' event from "
            f"{changes['schedule']['from']} to {changes['schedule']['to']}.\n\n"
            f"Your order is still active for this new time. If this change doesn't work for you, "
            f"you can cancel your order through your orders dashboard. Would you like me to help with that?"
        )
    
    if 'price' in changes and changes['price']['to'] < changes['price']['from']:
        return (
            f"Good news! The price for Chef {chef_name}'s '{meal_name}' event has decreased from "
            f"${changes['price']['from']:.2f} to ${changes['price']['to']:.2f} per serving. "
            f"This price change will be automatically applied to your order.\n\n"
            f"Let me know if you'd like to modify your order quantity to take advantage of this better price!"
        )
    
    # Generic message for other changes
    return (
        f"I wanted to let you know about an update to your order for Chef {chef_name}'s '{meal_name}' "
        f"event on {event.event_date.strftime('%A, %B %d')}. "
        f"Please check your orders dashboard for details, or ask me if you need any assistance."
    )

def generate_chef_event_change_subject(changes):
    """
    Generate an appropriate subject line based on the type of changes.
    """
    if 'status' in changes and changes['status']['to'] == 'cancelled':
        return "Your chef meal event has been cancelled"
    elif 'schedule' in changes:
        return "Your chef meal event has been rescheduled"
    elif 'price' in changes:
        return "Price update for your chef meal order"
    else:
        return "Update about your chef meal order"

def send_chef_event_notification(user_id, message, subject, event_id, changes):
    """
    Task to send a notification about a chef meal event change via the assistant.
    """
    try:
        from meals.meal_assistant_implementation import MealPlanningAssistant
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user_id,
            message_content=message,
            subject=subject
        )
        
        if result.get("status") == "success":
            logger.info(f"Successfully sent chef event notification to user {user_id} for event {event_id}")
        else:
            logger.warning(f"Chef event notification result for user {user_id}: {result}")
            
    except Exception as e:
        logger.error(f"Error sending chef event notification to user {user_id}: {str(e)}")
        n8n_traceback_url = os.getenv('N8N_TRACEBACK_URL', '')
        if n8n_traceback_url:
            try:
                requests.post(n8n_traceback_url, json={
                    "error": str(e),
                    "source": f"chef_event_notification_{user_id}",
                    "traceback": traceback.format_exc()
                })
            except Exception as webhook_error:
                logger.error(f"Failed to send error to N8N webhook: {str(webhook_error)}")

# Weekly conversation reset feature
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
            # Import assistant here to avoid circular imports
            from meals.meal_assistant_implementation import MealPlanningAssistant
            
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
