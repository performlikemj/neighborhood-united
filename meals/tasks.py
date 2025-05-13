# Constants
MIN_SIMILARITY = 0.6  # Adjusted similarity threshold
MAX_ATTEMPTS = 5      # Max attempts to find or generate a meal per meal type per day
EXPECTED_EMBEDDING_SIZE = 1536  # Example size, adjust based on your embedding model

from celery import shared_task
from .models import SystemUpdate
from .models import Chef
from .chef_meals_views import sync_recent_payments
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import F
from decimal import Decimal
import stripe
from .models import ChefMealEvent, ChefMealOrder, PaymentLog, STATUS_COMPLETED
import pytz
from customer_dashboard.models import CustomUser

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

@shared_task
def queue_system_update_email(system_update_id, test_mode=False, admin_id=None):
    """
    Queue system update emails through Celery
    """
    print(f"Queueing system update email for {system_update_id}")
    from meals.email_service import send_system_update_email
    try:
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
    except SystemUpdate.DoesNotExist:
        return False

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
            user_timezone = pytz.timezone(user.timezone if user.timezone else 'UTC')
            
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
                    logger.debug(f"User {user.id} ({user.username}) already has a summary for today")
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





















