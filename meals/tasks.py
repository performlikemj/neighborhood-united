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





















