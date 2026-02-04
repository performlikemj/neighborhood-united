# chefs/tasks/proactive_engine.py
"""
Proactive Engine - Generates insights and notifications for chefs.

Runs periodically via Celery Beat to check for:
- Upcoming special occasions (birthdays, anniversaries)
- Clients who haven't ordered in a while
- Todo reminders from memory
- Seasonal ingredient suggestions
- Client milestones
"""

import logging
from datetime import timedelta
from typing import List

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='chefs.proactive_engine.run_proactive_check')
def run_proactive_check():
    """
    Main proactive engine task. Runs hourly via Celery Beat.
    
    Checks each chef with proactive enabled and generates
    appropriate notifications based on their settings.
    """
    from chefs.models import ChefProactiveSettings
    
    # Get all chefs with proactive enabled
    enabled_settings = ChefProactiveSettings.objects.filter(
        enabled=True
    ).select_related('chef')
    
    processed = 0
    notifications_created = 0
    
    for settings in enabled_settings:
        try:
            # Check quiet hours
            if settings.is_within_quiet_hours():
                continue
            
            # Check frequency
            if not should_run_for_frequency(settings):
                continue
            
            # Generate insights based on enabled notifications
            count = generate_insights_for_chef(settings)
            notifications_created += count
            processed += 1
            
        except Exception as e:
            logger.error(f"Error processing proactive for chef {settings.chef_id}: {e}")
    
    logger.info(f"Proactive check complete: {processed} chefs, {notifications_created} notifications")
    return {'processed': processed, 'notifications': notifications_created}


def should_run_for_frequency(settings) -> bool:
    """Check if we should run based on frequency setting."""
    from chefs.models import ChefNotification
    
    freq = settings.notification_frequency
    
    if freq == ChefProactiveSettings.FREQUENCY_REALTIME:
        return True
    
    # Get last notification sent
    last_notification = ChefNotification.objects.filter(
        chef=settings.chef,
        status__in=[ChefNotification.STATUS_SENT, ChefNotification.STATUS_READ]
    ).order_by('-sent_at').first()
    
    if not last_notification or not last_notification.sent_at:
        return True
    
    now = timezone.now()
    
    if freq == ChefProactiveSettings.FREQUENCY_DAILY:
        # Check if it's a new day (9 AM local time)
        try:
            import pytz
            tz = pytz.timezone(settings.quiet_hours_timezone)
            local_now = now.astimezone(tz)
            local_last = last_notification.sent_at.astimezone(tz)
            
            # Run if different day and after 9 AM
            if local_now.date() > local_last.date() and local_now.hour >= 9:
                return True
        except Exception:
            # Fallback: 24 hours since last notification
            if now - last_notification.sent_at > timedelta(hours=24):
                return True
        return False
    
    if freq == ChefProactiveSettings.FREQUENCY_WEEKLY:
        # Check if it's Monday 9 AM local time
        try:
            import pytz
            tz = pytz.timezone(settings.quiet_hours_timezone)
            local_now = now.astimezone(tz)
            
            if local_now.weekday() == 0 and local_now.hour >= 9:
                # Check if we've already sent this week
                week_start = local_now.date() - timedelta(days=local_now.weekday())
                if not last_notification.sent_at or last_notification.sent_at.astimezone(tz).date() < week_start:
                    return True
        except Exception:
            # Fallback: 7 days since last notification
            if now - last_notification.sent_at > timedelta(days=7):
                return True
        return False
    
    return False


# Import settings class for frequency constants
from chefs.models import ChefProactiveSettings


def generate_insights_for_chef(settings) -> int:
    """Generate all relevant insights for a chef based on their settings."""
    notifications = []
    
    if settings.notify_birthdays or settings.notify_anniversaries:
        notifications.extend(check_special_occasions(settings))
    
    if settings.notify_followups:
        notifications.extend(check_followups(settings))
    
    if settings.notify_todos:
        notifications.extend(check_todos(settings))
    
    if settings.notify_milestones:
        notifications.extend(check_milestones(settings))
    
    if settings.notify_seasonal:
        notifications.extend(check_seasonal(settings))
    
    return len(notifications)


def check_special_occasions(settings) -> List:
    """Check for upcoming birthdays and anniversaries."""
    from chefs.models import ClientContext, ChefNotification
    
    notifications = []
    chef = settings.chef
    
    # Get all client contexts with special occasions
    contexts = ClientContext.objects.filter(chef=chef).exclude(special_occasions=[])
    
    today = timezone.now().date()
    
    for context in contexts:
        for occasion in context.special_occasions:
            occasion_name = occasion.get('name', 'Special Date')
            occasion_date_str = occasion.get('date', '')
            
            if not occasion_date_str:
                continue
            
            try:
                # Parse date (expecting YYYY-MM-DD or MM-DD)
                if len(occasion_date_str) == 10:  # YYYY-MM-DD
                    month, day = int(occasion_date_str[5:7]), int(occasion_date_str[8:10])
                elif len(occasion_date_str) == 5:  # MM-DD
                    month, day = int(occasion_date_str[:2]), int(occasion_date_str[3:5])
                else:
                    continue
                
                # Check if occasion is coming up this year
                try:
                    occasion_this_year = today.replace(month=month, day=day)
                except ValueError:
                    continue
                
                # If already passed this year, check next year
                if occasion_this_year < today:
                    try:
                        occasion_this_year = occasion_this_year.replace(year=today.year + 1)
                    except ValueError:
                        continue
                
                # Determine lead days based on occasion type
                is_birthday = 'birthday' in occasion_name.lower()
                lead_days = settings.birthday_lead_days if is_birthday else settings.anniversary_lead_days
                check_until = today + timedelta(days=lead_days)
                
                # Check if within lead days
                if today <= occasion_this_year <= check_until:
                    days_until = (occasion_this_year - today).days
                    client_name = context.get_client_name()
                    
                    notification_type = ChefNotification.TYPE_BIRTHDAY if is_birthday else ChefNotification.TYPE_ANNIVERSARY
                    
                    # Use deduplication
                    dedup_key = f"{notification_type}_{context.id}_{occasion_this_year.isoformat()}"
                    
                    if is_birthday and settings.notify_birthdays:
                        notif = ChefNotification.create_notification(
                            chef=chef,
                            notification_type=notification_type,
                            title=f"🎂 {client_name}'s {occasion_name} in {days_until} days",
                            message=f"{client_name}'s {occasion_name} is coming up on {occasion_this_year.strftime('%B %d')}. Consider reaching out!",
                            related_client=context.client,
                            related_lead=context.lead,
                            dedup_key=dedup_key,
                        )
                        if notif.status == ChefNotification.STATUS_PENDING:
                            _auto_send_if_enabled(notif, settings)
                            notifications.append(notif)
                    
                    elif not is_birthday and settings.notify_anniversaries:
                        notif = ChefNotification.create_notification(
                            chef=chef,
                            notification_type=notification_type,
                            title=f"💍 {client_name}'s {occasion_name} in {days_until} days",
                            message=f"{client_name}'s {occasion_name} is on {occasion_this_year.strftime('%B %d')}. A great opportunity to do something special!",
                            related_client=context.client,
                            related_lead=context.lead,
                            dedup_key=dedup_key,
                        )
                        if notif.status == ChefNotification.STATUS_PENDING:
                            _auto_send_if_enabled(notif, settings)
                            notifications.append(notif)
            
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse occasion date: {occasion_date_str} - {e}")
                continue
    
    return notifications


def check_followups(settings) -> List:
    """Check for clients who haven't ordered recently."""
    from chefs.models import ClientContext, ChefNotification
    
    notifications = []
    chef = settings.chef
    threshold_days = settings.followup_threshold_days
    
    cutoff_date = timezone.now() - timedelta(days=threshold_days)
    
    # Get clients with orders but none recent
    contexts = ClientContext.objects.filter(chef=chef, total_orders__gt=0)
    
    for context in contexts:
        # Check last order date
        if context.last_order_date and context.last_order_date < cutoff_date.date():
            client_name = context.get_client_name()
            days_since = (timezone.now().date() - context.last_order_date).days
            
            dedup_key = f"followup_{context.id}_{timezone.now().date().isoformat()}"
            
            notif = ChefNotification.create_notification(
                chef=chef,
                notification_type=ChefNotification.TYPE_FOLLOWUP,
                title=f"👋 Haven't heard from {client_name} in {days_since} days",
                message=f"It's been {days_since} days since {client_name}'s last order. Maybe reach out to see how they're doing?",
                related_client=context.client,
                related_lead=context.lead,
                dedup_key=dedup_key,
            )
            if notif.status == ChefNotification.STATUS_PENDING:
                _auto_send_if_enabled(notif, settings)
                notifications.append(notif)
    
    return notifications


def check_todos(settings) -> List:
    """Check for pending todo memories."""
    from customer_dashboard.models import ChefMemory
    from chefs.models import ChefNotification
    
    notifications = []
    chef = settings.chef
    
    # Get active todos
    todos = ChefMemory.objects.filter(
        chef=chef,
        memory_type='todo',
        is_active=True
    ).order_by('-importance', '-created_at')[:5]
    
    for todo in todos:
        dedup_key = f"todo_{todo.id}"
        
        client_info = ""
        if todo.customer:
            client_info = f" (for {todo.customer.first_name})"
        elif todo.lead:
            client_info = f" (for {todo.lead.first_name})"
        
        notif = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_TODO,
            title=f"📝 Reminder: {todo.content[:50]}{'...' if len(todo.content) > 50 else ''}{client_info}",
            message=todo.content,
            related_client=todo.customer,
            related_lead=todo.lead,
            dedup_key=dedup_key,
        )
        if notif.status == ChefNotification.STATUS_PENDING:
            _auto_send_if_enabled(notif, settings)
            notifications.append(notif)
    
    return notifications


def check_milestones(settings) -> List:
    """Check for client milestones (5th, 10th, 25th, 50th, 100th order)."""
    from chefs.models import ClientContext, ChefNotification
    
    notifications = []
    chef = settings.chef
    
    milestones = [5, 10, 25, 50, 100]
    
    contexts = ClientContext.objects.filter(chef=chef, total_orders__in=milestones)
    
    for context in contexts:
        client_name = context.get_client_name()
        dedup_key = f"milestone_{context.id}_{context.total_orders}"
        
        notif = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_MILESTONE,
            title=f"🎉 {client_name} just hit {context.total_orders} orders!",
            message=f"Congratulations! {client_name} has placed {context.total_orders} orders with you. Consider sending a thank you!",
            related_client=context.client,
            related_lead=context.lead,
            dedup_key=dedup_key,
        )
        if notif.status == ChefNotification.STATUS_PENDING:
            _auto_send_if_enabled(notif, settings)
            notifications.append(notif)
    
    return notifications


def check_seasonal(settings) -> List:
    """Check for seasonal ingredient suggestions."""
    from chefs.models import ChefNotification
    
    notifications = []
    chef = settings.chef
    
    current_month = timezone.now().month
    month_name = timezone.now().strftime('%B')
    
    # Try to import seasonal ingredients, gracefully handle if not available
    try:
        from meals.sous_chef_tools import SEASONAL_INGREDIENTS
        seasonal = SEASONAL_INGREDIENTS.get(current_month, {})
    except (ImportError, AttributeError):
        seasonal = {}
    
    if not seasonal:
        return notifications
    
    # Dedup key for this month
    dedup_key = f"seasonal_{chef.id}_{timezone.now().year}_{current_month}"
    
    # Build a nice message with seasonal highlights
    highlights = []
    for category, items in list(seasonal.items())[:3]:
        if items:
            highlights.append(f"{category.title()}: {', '.join(items[:3])}")
    
    if highlights:
        notif = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_SEASONAL,
            title=f"🌱 What's in season for {month_name}",
            message="Fresh seasonal ingredients to inspire your menus:\n\n• " + "\n• ".join(highlights),
            dedup_key=dedup_key,
        )
        if notif.status == ChefNotification.STATUS_PENDING:
            _auto_send_if_enabled(notif, settings)
            notifications.append(notif)
    
    return notifications


def _auto_send_if_enabled(notification, settings):
    """Auto-send notification based on channel preferences."""
    if settings.channel_in_app:
        notification.mark_sent('in_app')


@shared_task(name='chefs.proactive_engine.send_welcome_notification')
def send_welcome_notification(chef_id: int):
    """Send welcome notification to a new chef."""
    from chefs.models import Chef, ChefNotification, ChefOnboardingState
    
    try:
        chef = Chef.objects.get(id=chef_id)
        state = ChefOnboardingState.get_or_create_for_chef(chef)
        
        if state.welcomed:
            return {'status': 'already_welcomed'}
        
        notif = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_WELCOME,
            title="👋 Welcome to your Chef Dashboard!",
            message="I'm your Sous Chef — think of me as your kitchen partner who never forgets a detail. Ready to get started?",
            action_context={'action': 'start_onboarding', 'show_welcome': True}
        )
        notif.mark_sent('in_app')
        
        state.mark_welcomed()
        
        return {'status': 'sent', 'notification_id': notif.id}
        
    except Chef.DoesNotExist:
        logger.error(f"Chef {chef_id} not found for welcome notification")
        return {'status': 'error', 'error': 'chef_not_found'}
