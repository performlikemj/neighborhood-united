# Constants
MIN_SIMILARITY = 0.6  # Adjusted similarity threshold
MAX_ATTEMPTS = 5      # Max attempts to find or generate a meal per meal type per day
EXPECTED_EMBEDDING_SIZE = 1536  # Example size, adjust based on your embedding model

from celery import shared_task
from .models import SystemUpdate
from .models import MealPlan, MealPlanMeal, Meal
from .models import Chef
from .chef_meals_views import sync_recent_payments
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import F
from django.db import transaction
from decimal import Decimal
import stripe
from .models import ChefMealEvent, ChefMealOrder, PaymentLog, STATUS_COMPLETED
import pytz
from zoneinfo import ZoneInfo
from customer_dashboard.models import CustomUser
from openai import OpenAI
import time
from .celery_utils import handle_task_failure

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

@shared_task
@handle_task_failure
def queue_system_update_email(system_update_id, test_mode=False, admin_id=None):
    """
    Queue system update emails through Celery
    """
    print(f"Queueing system update email for {system_update_id}")
    from meals.email_service import send_system_update_email
    
    system_update = SystemUpdate.objects.get(id=system_update_id)
    
    if test_mode and admin_id:
        # Send test email only to admin
        send_system_update_email.delay(
            subject=system_update.subject,
            message=system_update.message,
            user_ids=[admin_id]
        )
    else:
        # Send to all users
        send_system_update_email.delay(
            subject=system_update.subject,
            message=system_update.message
        )
        print(f"System update email queued for all users!")
    return True

@shared_task
def sync_all_chef_payments():
    """Daily task to sync all chef payments with Stripe"""
    for chef in Chef.objects.all():
        try:
            print(f"Syncing payments for chef {chef.user.username}")
            sync_recent_payments(chef)
        except Exception as e:
            logger.error(f"Error syncing payments for chef {chef.id}: {str(e)}")

@shared_task
def process_chef_meal_price_adjustments():
    """
    Weekly task to process price adjustment refunds for chef meal orders.
    
    When more people order a chef meal, the price decreases for everyone.
    This task ensures everyone pays the same final (lowest) price by 
    refunding the difference to those who paid more.
    """
    # Look at events completed in the past 7 days
    # (adjust timeframe as needed for your business)
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    # Find completed events that need price reconciliation
    completed_events = ChefMealEvent.objects.filter(
        status=STATUS_COMPLETED,
        updated_at__gte=seven_days_ago,
        # Only look at events that have adjustable pricing
        base_price__gt=F('min_price')
    )
    
    logger.info(f"Processing price adjustments for {completed_events.count()} completed chef meal events")
    
    total_processed = 0
    total_refunded = Decimal('0.00')
    
    for event in completed_events:
        # Skip if final price equals base price (no discount was applied)
        if event.current_price >= event.base_price:
            continue
            
        # Get all orders for this event
        orders = ChefMealOrder.objects.filter(
            meal_event=event,
            status__in=['placed', 'confirmed', 'completed'],
            # Skip already refunded orders
            price_adjustment_processed=False
        )
        
        logger.info(f"Processing {orders.count()} orders for event '{event}' (ID: {event.id})")
        
        for order in orders:
            # Skip orders with no payment record
            if not order.stripe_payment_intent_id:
                logger.warning(f"Order {order.id} has no payment record, skipping")
                continue
                
            # Calculate price difference
            price_paid = order.price_paid
            final_price = event.current_price
            
            # Only process if customer paid more than final price
            if price_paid > final_price:
                difference = (price_paid - final_price) * order.quantity
                
                # Skip tiny amounts (often not worth the transaction fees)
                if difference < Decimal('0.50'):
                    logger.info(f"Skipping small refund of ${difference} for order {order.id}")
                    order.price_adjustment_processed = True
                    order.save()
                    continue
                
                # Convert to cents for Stripe
                refund_amount_cents = int(difference * 100)
                
                try:
                    # Process refund through Stripe
                    refund = stripe.Refund.create(
                        payment_intent=order.stripe_payment_intent_id,
                        amount=refund_amount_cents,
                        reason="duplicate",  # Using "duplicate" as proxy for price adjustment
                        metadata={
                            'reason': 'chef_meal_price_adjustment',
                            'event_id': str(event.id),
                            'order_id': str(order.id),
                            'original_price': str(price_paid),
                            'final_price': str(final_price)
                        }
                    )
                    
                    # Record the refund
                    order.stripe_refund_id = refund.id
                    order.price_adjustment_processed = True
                    order.save()
                    
                    # Log the payment
                    PaymentLog.objects.create(
                        chef_meal_order=order,
                        user=order.customer,
                        chef=event.chef,
                        action='refund',
                        amount=difference,
                        stripe_id=refund.id,
                        status='succeeded',
                        details={
                            'refund': refund.id,
                            'reason': 'chef_meal_price_adjustment',
                            'original_price': str(price_paid),
                            'final_price': str(final_price),
                            'difference': str(difference)
                        }
                    )
                    
                    logger.info(f"Processed refund of ${difference} for order {order.id} - Refund ID: {refund.id}")
                    total_processed += 1
                    total_refunded += difference
                    
                    # TODO: Send email notification to customer about the refund
                    # You can implement this using your n8n webhook or Django's email system
                    
                except stripe.error.StripeError as e:
                    logger.error(f"Stripe error processing refund for order {order.id}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error processing refund for order {order.id}: {str(e)}", exc_info=True)
            else:
                # Mark as processed even if no refund needed
                order.price_adjustment_processed = True
                order.save()
    
    logger.info(f"Price adjustment task completed. Processed {total_processed} refunds totaling ${total_refunded}")
    return {'processed': total_processed, 'total_refunded': str(total_refunded)}

@shared_task
@handle_task_failure
def generate_daily_user_summaries():
    """
    Task to generate daily summaries for all active users.
    This task runs hourly to catch users in different time zones
    and generates summaries only when it's 3:00 AM in the user's local timezone.
    """
    logger = logging.getLogger(__name__)
    
    # Get all users with confirmed emails
    active_users = CustomUser.objects.filter(
        email_confirmed=True
    )
    
    eligible_count = 0
    summary_count = 0
    
    logger.info(f"Checking {active_users.count()} users with confirmed emails for daily summary generation")
    
    # Process each user
    for user in active_users:
        try:
            # Get the user's timezone
            user_timezone = ZoneInfo(user.timezone if user.timezone else 'UTC')
            
            # Get current time in user's timezone
            user_local_time = timezone.now().astimezone(user_timezone)
            user_local_date = user_local_time.date()
            hour = user_local_time.hour
            
            # Only generate summary if it's between 2-4 AM in the user's timezone
            if 2 <= hour <= 4:
                # Check if we already generated a summary for this user today
                from customer_dashboard.models import UserDailySummary
                
                # Skip if the user already has a summary for today with completed status
                existing_summary = UserDailySummary.objects.filter(
                    user=user,
                    summary_date=user_local_date,
                    status=UserDailySummary.COMPLETED
                ).first()
                
                if existing_summary:
                    continue
                    
                # This user is eligible for a summary generation
                eligible_count += 1
                
                logger.info(f"Generating summary for user {user.id} ({user.username}) in timezone {user_timezone}")
                from meals.email_service import generate_user_summary
                
                # Queue the task to generate the summary
                generate_user_summary.delay(user.id)
                summary_count += 1
                
        except Exception as e:
            logger.error(f"Error checking/generating summary for user {user.id}: {e}")
    
    if eligible_count > 0:
        logger.info(f"Found {eligible_count} users eligible for summary generation, queued {summary_count} summaries")
    else:
        logger.info("No users currently in the 2-4 AM window in their local timezone")
        
    return f"Daily summary check complete: found {eligible_count} eligible users, queued {summary_count} summaries"

@shared_task
def schedule_capture(event_id):
    """
    Schedule the capture of payment intents at the event's cutoff time.
    
    Args:
        event_id: ID of the ChefMealEvent to schedule for
    """
    from meals.models import ChefMealEvent
    event = ChefMealEvent.objects.get(id=event_id)
    eta = event.order_cutoff_time
    
    # Schedule the capture task to run at the cutoff time
    capture_payment_intents.apply_async(args=[event_id], eta=eta)

@shared_task
def capture_payment_intents(event_id):
    """
    Capture all payment intents for a given chef meal event.
    This task is scheduled to run at the event's cutoff time.
    
    Args:
        event_id: ID of the ChefMealEvent to capture payments for
    """
    import stripe
    from django.conf import settings
    from meals.models import ChefMealOrder
    
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    # Get all placed orders for this event
    orders = ChefMealOrder.objects.filter(
        meal_event_id=event_id, 
        status='placed'
    )
    
    for order in orders:
        if order.stripe_payment_intent_id:
            try:
                # Capture the payment intent
                stripe.PaymentIntent.capture(
                    order.stripe_payment_intent_id,
                    idempotency_key=f"capture_{order.stripe_payment_intent_id}"
                )
                
                # Update order status
                order.status = 'confirmed'
                order.save(update_fields=['status'])
                
                # Log the successful capture
                logger.info(f"Payment captured for order {order.id}, " 
                           f"payment intent {order.stripe_payment_intent_id}")
            except Exception as e:
                logger.error(f"Failed to capture payment for order {order.id}: {str(e)}")
        else:
            logger.warning(f"No payment intent found for order {order.id}")

@shared_task
@handle_task_failure
def create_weekly_chat_threads():
    """
    Task to create new chat threads for all active users at the start of each week.
    
    This should be scheduled to run every Monday morning.
    """
    from customer_dashboard.models import ChatThread, WeeklyAnnouncement, UserMessage
    from custom_auth.models import CustomUser
    from meals.meal_assistant_implementation import MealPlanningAssistant
    from django.utils import timezone
    from datetime import timedelta, date
    
    logger = logging.getLogger(__name__)
    
    # Get all authenticated users with email confirmed
    active_users = CustomUser.objects.filter(email_confirmed=True)
    today = timezone.localdate()
    
    # Only run on Mondays
    if today.weekday() != 0:  # 0 = Monday
        logger.info(f"create_weekly_chat_threads: Today is not Monday, skipping")
        return
    
    logger.info(f"Creating new weekly chat threads for {active_users.count()} active users")
    threads_created = 0
    threads_with_announcements = 0
    
    for user in active_users:
        try:
            # Mark old threads as inactive
            ChatThread.objects.filter(user=user, is_active=True).update(is_active=False)
            
            # Create a new thread for this week
            week_end = today + timedelta(days=6)
            thread = ChatThread.objects.create(
                user=user,
                title=f"Conversation for week of {today.strftime('%b %d')} - {week_end.strftime('%b %d')}",
                is_active=True
            )
            threads_created += 1
            
            # Add initial context about weekly announcements if available
            today_iso = today.isocalendar()
            week_start = date.fromisocalendar(today_iso[0], today_iso[1], 1)  # Monday
            
            # Get global and country-specific announcements
            country_code = user.address.country.code if hasattr(user, 'address') and user.address and user.address.country else ""
            announcements = []
            
            global_announcement = WeeklyAnnouncement.objects.filter(
                week_start=week_start,
                country__isnull=True
            ).first()
            
            if global_announcement:
                announcements.append(global_announcement.content)
                
            if country_code:
                country_announcement = WeeklyAnnouncement.objects.filter(
                    week_start=week_start,
                    country=country_code
                ).first()
                
                if country_announcement:
                    announcements.append(country_announcement.content)
            
            # If we have announcements, add context to the thread history
            if announcements:
                threads_with_announcements += 1
                # Initialize the thread with system message and announcement context
                assistant = MealPlanningAssistant(user_id=user.id)
                
                announcements_text = '\n\n'.join(announcements)
                history = [
                    {"role": "system", "content": assistant.system_message},
                    {"role": "system", "content": f"Weekly Announcements:\n{announcements_text}"}
                ]
                
                thread.openai_input_history = history
                thread.save(update_fields=['openai_input_history'])
                
                # Add the announcement as an assistant message
                announcement_text = '\n\n'.join(announcements)
                formatted_announcement = (
                    f"Hi {user.first_name},\n\n"
                    f"Welcome to a new week! Here are some important announcements:\n\n"
                    f"{announcement_text}\n\n"
                    f"Let me know if you need any assistance with your meal planning this week!"
                )
                
                UserMessage.objects.create(
                    user=user,
                    thread=thread,
                    message="",  # Empty user message since this is assistant-initiated
                    response=formatted_announcement
                )
        except Exception as e:
            logger.error(f"Error creating weekly chat thread for user {user.id}: {str(e)}")
    
    logger.info(f"Weekly chat thread creation completed. Created {threads_created} new threads, {threads_with_announcements} with announcements.")
    return {
        "threads_created": threads_created,
        "threads_with_announcements": threads_with_announcements
    }

@shared_task
@handle_task_failure
def generate_user_chat_summaries():
    """
    Generate or update consolidated chat summaries for all active users.
    
    This task consolidates individual chat session summaries into a comprehensive user
    chat summary that provides context for the assistant in future conversations.
    Should be run once a day or after weekly chat thread reset.
    """
    from customer_dashboard.models import UserChatSummary, ChatSessionSummary, CustomUser
    from meals.meal_assistant_implementation import MealPlanningAssistant
    import time
    
    logger = logging.getLogger(__name__)
    
    # Get all users with confirmed emails
    active_users = CustomUser.objects.filter(email_confirmed=True)
    logger.info(f"Generating chat summaries for {active_users.count()} active users")
    
    updated_count = 0
    created_count = 0
    error_count = 0
    
    for user in active_users:
        try:
            # First check if we should update this user's summary
            existing_summary = UserChatSummary.objects.filter(user=user).first()
            
            # Get the latest session summaries for this user
            session_summaries = ChatSessionSummary.objects.filter(
                user=user,
                status=ChatSessionSummary.COMPLETED
            ).order_by('-summary_date')[:5]  # Get up to 5 most recent session summaries
            
            # If no session summaries, skip
            if not session_summaries.exists():
                continue
            
            # Check if summary exists and is up to date
            if existing_summary:
                latest_session_date = session_summaries.first().summary_date
                if existing_summary.last_summary_date and existing_summary.last_summary_date >= latest_session_date:
                    continue
            
            # Need to generate or update summary
            # Extract the content from each session summary
            session_texts = [f"{s.summary_date.strftime('%Y-%m-%d')}: {s.summary}" 
                            for s in session_summaries if s.summary]
            
            if not session_texts:
                continue
                
            # Create a prompt for OpenAI to consolidate these summaries
            client = OpenAI(api_key=settings.OPENAI_KEY)
            
            # Create a prompt that asks to create a consolidated user summary
            prompt = (
                "Create a comprehensive summary of user's chat history and behaviors based on these session summaries. "
                "Focus on providing a concise, clear understanding of the user's food preferences, dietary habits, "
                "meal planning patterns, goals, and conversations with the assistant.\n\n"
                "This should be no longer than 500 words.\n\n"
                "Session summaries:\n" + "\n\n".join(session_texts)
            )
            
            # Call OpenAI API to generate consolidated summary
            try:
                response = client.responses.create(
                    model="gpt-4.1-mini",
                    input=[
                        {"role": "system", "content": "You are an assistant that creates concise user summaries from chat data."},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                
                # Extract the generated summary
                consolidated_summary = getattr(response, "output_text", "").strip()
                
                if not consolidated_summary:
                    logger.warning(f"Empty summary generated for user {user.id}")
                    error_count += 1
                    continue
                
                # Create or update the user's chat summary
                if existing_summary:
                    existing_summary.summary = consolidated_summary
                    existing_summary.status = UserChatSummary.COMPLETED
                    existing_summary.last_summary_date = session_summaries.first().summary_date
                    existing_summary.save()
                    updated_count += 1
                    logger.info(f"Updated chat summary for user {user.id}")
                else:
                    UserChatSummary.objects.create(
                        user=user,
                        summary=consolidated_summary,
                        status=UserChatSummary.COMPLETED,
                        last_summary_date=session_summaries.first().summary_date
                    )
                    created_count += 1
                    logger.info(f"Created new chat summary for user {user.id}")
                
                # Sleep briefly to avoid rate limits
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error generating consolidated summary for user {user.id}: {str(e)}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"Error processing chat summaries for user {user.id}: {str(e)}")
            error_count += 1
    
    logger.info(f"Chat summary generation completed: {created_count} created, {updated_count} updated, {error_count} errors")
    return {
        "created": created_count,
        "updated": updated_count,
        "errors": error_count
    }

@shared_task
def generate_chat_session_summaries():
    """
    Generate summaries for individual chat sessions.
    
    This task should run daily to create summaries of active chat threads.
    These session summaries are then used to build the comprehensive user chat summary.
    """
    from customer_dashboard.models import ChatSessionSummary, ChatThread, UserMessage
    from django.db.models import Max, Q
    from openai import OpenAI
    import time
    from datetime import timedelta
    
    logger = logging.getLogger(__name__)
    
    # Get the date for yesterday (to ensure complete conversations)
    yesterday = timezone.localdate() - timedelta(days=1)
    
    # Get active chat threads from yesterday that don't have summaries yet
    chat_threads = ChatThread.objects.filter(
        Q(created_at__date=yesterday) | Q(is_active=True)
    ).exclude(
        # Exclude threads that already have summaries for yesterday
        summaries__summary_date=yesterday,
        summaries__status=ChatSessionSummary.COMPLETED
    )
    
    logger.info(f"Found {chat_threads.count()} chat threads to summarize")
    
    summaries_created = 0
    errors = 0
    
    client = OpenAI(api_key=settings.OPENAI_KEY)
    
    for thread in chat_threads:
        try:
            # Get messages for this thread from yesterday
            messages = UserMessage.objects.filter(
                thread=thread,
                created_at__date=yesterday
            ).order_by('created_at')
            
            # Skip if no messages were found
            if not messages.exists():
                continue
            
            # Check if we already have a pending summary
            existing_summary = ChatSessionSummary.objects.filter(
                thread=thread,
                summary_date=yesterday
            ).first()
            
            if existing_summary and existing_summary.status == ChatSessionSummary.COMPLETED:
                continue
            
            # Format the conversation into a string for the model
            conversation = []
            for msg in messages:
                if msg.message:  # User message
                    conversation.append(f"User: {msg.message}")
                if msg.response:  # Assistant response
                    conversation.append(f"Assistant: {msg.response}")
            
            # Skip if the conversation is too short
            if len(conversation) < 2:  # Need at least a message and response
                continue
            
            conversation_text = "\n\n".join(conversation)
            
            # Prepare prompt for OpenAI
            prompt = (
                "Create a concise but comprehensive summary of this conversation between a user and the meal planning assistant. "
                "Focus on key points discussed, any meal preferences mentioned, dietary needs, requests made, "
                "and decisions or actions taken. This summary will be used to maintain context across conversations. "
                "Keep the summary between 150-300 words.\n\n"
                f"Conversation:\n{conversation_text}\n\n"
                "Summary:"
            )
            
            # Call OpenAI API
            try:
                response = client.responses.create(
                    model="gpt-4.1-mini", # Use a smaller model for summaries
                    input=[
                        {"role": "system", "content": "You are an assistant that summarizes conversations accurately and concisely."},
                        {"role": "user", "content": prompt}
                    ],
                    stream=False
                )
                
                # Extract the summary
                summary_text = getattr(response, "output_text", "").strip()
                
                if not summary_text:
                    logger.warning(f"Empty summary generated for thread {thread.id}")
                    continue
                
                # Create or update the summary
                if existing_summary:
                    existing_summary.summary = summary_text
                    existing_summary.status = ChatSessionSummary.COMPLETED
                    existing_summary.last_message_processed = messages.last().created_at
                    existing_summary.save()
                else:
                    ChatSessionSummary.objects.create(
                        user=thread.user,
                        thread=thread,
                        summary_date=yesterday,
                        summary=summary_text,
                        status=ChatSessionSummary.COMPLETED,
                        last_message_processed=messages.last().created_at
                    )
                
                summaries_created += 1
                logger.info(f"Created summary for thread {thread.id}, user {thread.user.id}")
                
                # Sleep briefly to avoid rate limits
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error generating summary for thread {thread.id}: {str(e)}")
                errors += 1
                
        except Exception as e:
            logger.error(f"Error processing thread {thread.id}: {str(e)}")
            errors += 1
    
    logger.info(f"Chat session summary generation completed: {summaries_created} created, {errors} errors")
    return {
        "summaries_created": summaries_created,
        "errors": errors
    }













@shared_task
def cleanup_old_meal_plans_and_meals(dry_run: bool = False):
    """
    Delete meal plans whose week_end_date is older than 3 weeks and delete any
    meals tied exclusively to those old plans, provided those meals:
      - have not been used in any meal plans within the last 3 weeks,
      - have never been ordered (to preserve order history), and
      - are NOT chef-created meals (i.e., only delete user-created meals).

    Args:
        dry_run: If True, perform no deletions and return counts only.

    Returns:
        Dict with counts of items identified and deleted.
    """
    logger = logging.getLogger(__name__)

    today = timezone.localdate()
    cutoff_date = today - timedelta(weeks=3)

    # Meals that appear in meal plans in the last 3 weeks (protected)
    recent_meal_ids_qs = (
        MealPlanMeal.objects
        .filter(meal_plan__week_end_date__gte=cutoff_date)
        .values_list('meal_id', flat=True)
        .distinct()
    )
    recent_meal_ids = set(recent_meal_ids_qs)

    # Old meal plans to delete
    old_meal_plans_qs = MealPlan.objects.filter(week_end_date__lt=cutoff_date)

    # Meals tied to those old plans which are NOT used in recent plans
    candidate_old_meal_ids_qs = (
        MealPlanMeal.objects
        .filter(meal_plan__in=old_meal_plans_qs)
        .exclude(meal_id__in=recent_meal_ids)
        .values_list('meal_id', flat=True)
        .distinct()
    )
    # Restrict to user-created meals only (chef__isnull=True)
    deletable_user_meal_ids_qs = (
        Meal.objects
        .filter(id__in=candidate_old_meal_ids_qs, chef__isnull=True)
        .values_list('id', flat=True)
    )
    deletable_user_meal_ids = list(deletable_user_meal_ids_qs)

    identified_old_plans = old_meal_plans_qs.count()
    identified_old_only_meals = len(deletable_user_meal_ids)

    if dry_run:
        logger.info(
            f"[DRY RUN] Identified {identified_old_plans} old meal plans and "
            f"{identified_old_only_meals} meals eligible for deletion."
        )
        return {
            "old_meal_plans_found": identified_old_plans,
            "meals_eligible_for_deletion": identified_old_only_meals,
            "deleted_meal_plans": 0,
            "deleted_meals": 0,
        }

    deleted_plans = 0
    deleted_meals = 0

    with transaction.atomic():
        # Delete the old meal plans (cascades remove MealPlanMeal, instructions, etc.)
        deleted_plans = old_meal_plans_qs.count()
        if deleted_plans:
            logger.info(f"Deleting {deleted_plans} meal plans older than {cutoff_date}")
            old_meal_plans_qs.delete()

        # Now delete the meals that were only tied to those old plans and not used recently
        if deletable_user_meal_ids:
            meals_qs = Meal.objects.filter(id__in=deletable_user_meal_ids, chef__isnull=True)
            deleted_meals = meals_qs.count()
            if deleted_meals:
                logger.info(f"Deleting {deleted_meals} meals no longer referenced by recent meal plans")
                meals_qs.delete()

    logger.info(
        f"Cleanup complete. Deleted {deleted_plans} meal plans and {deleted_meals} meals."
    )
    return {
        "old_meal_plans_found": identified_old_plans,
        "meals_eligible_for_deletion": identified_old_only_meals,
        "deleted_meal_plans": deleted_plans,
        "deleted_meals": deleted_meals,
    }










