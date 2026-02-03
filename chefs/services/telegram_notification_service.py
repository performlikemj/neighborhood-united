"""
Telegram Notification Service - Phase 5.

Handles sending notifications to chefs via Telegram.

SECURITY PRINCIPLE: Notifications must NEVER include customer health data
(dietary preferences, allergies, restrictions, etc.). Only include minimal
information needed for the notification - chef should check dashboard for details.

This module provides:
- TelegramNotificationService: Main service for sending notifications
- Helper functions for checking notification permissions

Usage:
    from chefs.services.telegram_notification_service import TelegramNotificationService
    
    service = TelegramNotificationService()
    service.notify_new_order(chef, order)  # Returns True if sent, False if blocked
"""

import logging
from django.conf import settings

from chefs.models import ChefTelegramLink, ChefTelegramSettings
from chefs.tasks.telegram_tasks import send_telegram_message

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """
    Service for sending notifications to chefs via Telegram.
    
    All notifications respect:
    - Chef's notification settings (per-type toggles)
    - Quiet hours
    - Link status (active/inactive)
    
    SECURITY: This service intentionally EXCLUDES health data from all
    notifications. Customer dietary info, allergies, and restrictions
    must NEVER be transmitted over Telegram.
    """

    def notify_new_order(self, chef, order) -> bool:
        """
        Send new order notification to chef if enabled.
        
        Args:
            chef: Chef model instance
            order: Order model instance
            
        Returns:
            True if notification was sent, False if blocked
            
        Security:
            - Only includes customer first name (not last name)
            - Only includes order ID and dashboard link
            - NEVER includes dietary/allergy info
        """
        if not self._can_notify(chef, 'notify_new_orders'):
            return False

        # Build notification message - SECURITY: No health data!
        customer_name = order.customer.first_name or "A customer"
        message = (
            f"🆕 New order from {customer_name}!\n"
            f"Tap to view: {self._dashboard_link(order)}"
        )

        return self._send(chef, message)

    def notify_order_update(self, chef, order, update_type: str) -> bool:
        """
        Send order update notification to chef if enabled.
        
        Args:
            chef: Chef model instance
            order: Order model instance
            update_type: Description of the update
            
        Returns:
            True if notification was sent, False if blocked
        """
        if not self._can_notify(chef, 'notify_order_updates'):
            return False

        message = (
            f"📦 Order update: {update_type}\n"
            f"Tap to view: {self._dashboard_link(order)}"
        )

        return self._send(chef, message)

    def notify_schedule_reminder(self, chef, reminder_text: str) -> bool:
        """
        Send schedule reminder to chef if enabled.
        
        Args:
            chef: Chef model instance
            reminder_text: The reminder content
            
        Returns:
            True if notification was sent, False if blocked
        """
        if not self._can_notify(chef, 'notify_schedule_reminders'):
            return False

        message = f"⏰ Reminder: {reminder_text}"

        return self._send(chef, message)

    def notify_customer_message(self, chef, customer, preview: str) -> bool:
        """
        Send customer message notification to chef if enabled.
        
        Args:
            chef: Chef model instance
            customer: Customer user instance
            preview: Short preview of the message (no health info!)
            
        Returns:
            True if notification was sent, False if blocked
            
        Security:
            - Preview should be truncated and sanitized
            - NEVER include dietary/health data in preview
        """
        if not self._can_notify(chef, 'notify_customer_messages'):
            return False

        customer_name = customer.first_name or "A customer"
        message = (
            f"💬 Message from {customer_name}\n"
            f"Tap to view in dashboard"
        )

        return self._send(chef, message)

    def _can_notify(self, chef, setting_name: str) -> bool:
        """
        Check if notification should be sent.
        
        Checks:
        1. Chef has active Telegram link
        2. Chef has settings record with notification enabled
        3. Not currently in quiet hours
        
        Args:
            chef: Chef model instance
            setting_name: Name of the setting to check (e.g., 'notify_new_orders')
            
        Returns:
            True if notification is allowed, False otherwise
        """
        # Check for active Telegram link
        try:
            link = chef.telegram_link
            if not link.is_active:
                logger.debug(f"Telegram link inactive for chef {chef.id}")
                return False
        except ChefTelegramLink.DoesNotExist:
            logger.debug(f"No Telegram link for chef {chef.id}")
            return False

        # Check settings
        try:
            telegram_settings = chef.telegram_settings
            
            # Check if this notification type is enabled
            if not getattr(telegram_settings, setting_name, False):
                logger.debug(f"Notification type {setting_name} disabled for chef {chef.id}")
                return False
            
            # Check quiet hours
            if telegram_settings.is_quiet_hours():
                logger.debug(f"Quiet hours active for chef {chef.id}")
                return False
                
        except ChefTelegramSettings.DoesNotExist:
            logger.debug(f"No Telegram settings for chef {chef.id}")
            return False

        return True

    def _send(self, chef, message: str) -> bool:
        """
        Send message to chef's Telegram via Celery task.
        
        Args:
            chef: Chef model instance (must have active telegram_link)
            message: Message content to send
            
        Returns:
            True if message was queued for sending
        """
        try:
            chat_id = chef.telegram_link.telegram_user_id
            success = send_telegram_message(chat_id, message)
            if success:
                logger.info(f"Sent Telegram notification for chef {chef.id}")
            else:
                logger.warning(f"Failed to send Telegram notification for chef {chef.id}")
            return success
        except Exception as e:
            logger.error(f"Failed to send Telegram notification for chef {chef.id}: {e}")
            return False

    def _dashboard_link(self, order) -> str:
        """
        Generate deep link to order in chef dashboard.
        
        Args:
            order: Order model instance
            
        Returns:
            URL string to order detail page
        """
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://sautai.com')
        return f"{frontend_url}/orders/{order.id}"
