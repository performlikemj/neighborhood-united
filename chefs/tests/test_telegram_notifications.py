"""
Tests for Telegram Notification Service - Phase 5.

Tests cover:
- TelegramNotificationService notification gating (enabled/disabled, quiet hours, link status)
- Notification content formatting
- Security: notifications must NEVER include customer health data

SECURITY RULE: Notifications must NEVER include customer dietary info, allergies,
or any health data. This is explicitly tested.

Run with: pytest chefs/tests/test_telegram_notifications.py -v
"""

from datetime import time as dt_time, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone

from custom_auth.models import CustomUser
from chefs.models import (
    Chef,
    ChefTelegramLink,
    ChefTelegramSettings,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================


class TelegramNotificationTestMixin:
    """Common setup for telegram notification tests."""

    def setUp(self):
        # Create chef user and chef
        self.chef_user = CustomUser.objects.create_user(
            username="notification_test_chef",
            email="notification_chef@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")

        # Create customer user with dietary/allergy info (SENSITIVE DATA)
        self.customer = CustomUser.objects.create_user(
            username="notification_test_customer",
            email="customer@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )
        # Add sensitive health data to customer
        self.customer.dietary_preference = "Keto"
        self.customer.allergies = ["Peanuts", "Tree nuts"]
        self.customer.save()

        # Create mock order
        self.mock_order = MagicMock()
        self.mock_order.id = 123
        self.mock_order.customer = self.customer
        self.mock_order.status = "Placed"

    def _create_telegram_link(self, chef=None, is_active=True):
        """Helper to create a telegram link for a chef."""
        chef = chef or self.chef
        return ChefTelegramLink.objects.create(
            chef=chef,
            telegram_user_id=123456789,
            telegram_username="testchef",
            is_active=is_active,
        )

    def _create_telegram_settings(self, chef=None, **overrides):
        """Helper to create telegram settings for a chef."""
        chef = chef or self.chef
        defaults = {
            "notify_new_orders": True,
            "notify_order_updates": True,
            "notify_schedule_reminders": True,
            "quiet_hours_enabled": False,
        }
        defaults.update(overrides)
        return ChefTelegramSettings.objects.create(chef=chef, **defaults)


# =============================================================================
# NOTIFICATION GATING TESTS
# =============================================================================


class TelegramNotificationGatingTests(TelegramNotificationTestMixin, TestCase):
    """Tests for notification permission checks."""

    def test_notification_sent_when_enabled(self):
        """Notification is sent when chef has Telegram linked and notifications enabled."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Link Telegram and enable notifications
        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            result = service.notify_new_order(self.chef, self.mock_order)

        self.assertTrue(result)
        mock_send.assert_called_once()

    def test_notification_blocked_when_disabled(self):
        """Notification is blocked when chef has disabled that notification type."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Link Telegram but disable new order notifications
        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=False)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_new_order(self.chef, self.mock_order)

        self.assertFalse(result)
        mock_send.assert_not_called()

    def test_notification_blocked_during_quiet_hours(self):
        """Notification is blocked during chef's quiet hours."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Link Telegram, enable notifications, set quiet hours
        self._create_telegram_link()
        self._create_telegram_settings(
            notify_new_orders=True,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(22, 0),  # 10pm
            quiet_hours_end=dt_time(8, 0),  # 8am
        )

        service = TelegramNotificationService()

        # Mock current time to be during quiet hours (3am)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=3, minute=0)
            mock_localtime.return_value = mock_now

            with patch.object(service, '_send') as mock_send:
                result = service.notify_new_order(self.chef, self.mock_order)

        self.assertFalse(result)
        mock_send.assert_not_called()

    def test_notification_blocked_when_unlinked(self):
        """Notification is blocked when chef has no Telegram link."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: NO Telegram link, but settings exist
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_new_order(self.chef, self.mock_order)

        self.assertFalse(result)
        mock_send.assert_not_called()

    def test_notification_blocked_when_inactive(self):
        """Notification is blocked when Telegram link is inactive (unlinked)."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Telegram link exists but is_active=False (user unlinked)
        self._create_telegram_link(is_active=False)
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_new_order(self.chef, self.mock_order)

        self.assertFalse(result)
        mock_send.assert_not_called()


# =============================================================================
# NOTIFICATION CONTENT TESTS
# =============================================================================


class TelegramNotificationContentTests(TelegramNotificationTestMixin, TestCase):
    """Tests for notification message content and formatting."""

    def test_new_order_notification_format(self):
        """New order notification has correct format with customer name and link."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup
        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            service.notify_new_order(self.chef, self.mock_order)

        # Verify the message format
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        message = call_args[0][1]  # Second positional argument is the message

        # Should contain emoji, customer first name, and be informative
        self.assertIn("🆕", message)
        self.assertIn("John", message)  # Customer first name
        self.assertIn("order", message.lower())

    def test_notification_does_not_include_dietary_info(self):
        """
        SECURITY TEST: Notifications must NEVER include customer dietary/health data.
        
        This is critical - dietary info, allergies, and health data must stay on platform.
        """
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Customer has sensitive health data
        self.customer.dietary_preference = "Keto"
        self.customer.allergies = ["Peanuts", "Tree nuts", "Shellfish"]
        self.customer.save()

        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            service.notify_new_order(self.chef, self.mock_order)

        # Get the message that would be sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        message = call_args[0][1]

        # SECURITY: These should NEVER appear in notifications
        sensitive_terms = [
            "Keto", "keto",
            "Peanuts", "peanuts",
            "Tree nuts", "tree nuts",
            "Shellfish", "shellfish",
            "dietary", "Dietary",
            "allerg", "Allerg",
            "restriction", "Restriction",
        ]

        for term in sensitive_terms:
            self.assertNotIn(
                term,
                message,
                f"SECURITY VIOLATION: Notification contains sensitive term '{term}'"
            )

    def test_notification_includes_dashboard_link(self):
        """Notifications include a link to view the order in the dashboard."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup
        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            service.notify_new_order(self.chef, self.mock_order)

        # Get the message
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        message = call_args[0][1]

        # Should contain a link to the order
        self.assertIn(str(self.mock_order.id), message)
        # Should contain URL-like content
        self.assertTrue(
            "http" in message or "/orders/" in message,
            "Notification should include dashboard link"
        )


# =============================================================================
# ORDER UPDATE NOTIFICATION TESTS
# =============================================================================


class TelegramOrderUpdateNotificationTests(TelegramNotificationTestMixin, TestCase):
    """Tests for order update notifications."""

    def test_order_update_notification_sent_when_enabled(self):
        """Order update notification sent when enabled."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(notify_order_updates=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            result = service.notify_order_update(
                self.chef, self.mock_order, "Status changed to In Progress"
            )

        self.assertTrue(result)
        mock_send.assert_called_once()

    def test_order_update_notification_blocked_when_disabled(self):
        """Order update notification blocked when disabled."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(notify_order_updates=False)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_order_update(
                self.chef, self.mock_order, "Status changed"
            )

        self.assertFalse(result)
        mock_send.assert_not_called()


# =============================================================================
# SCHEDULE REMINDER NOTIFICATION TESTS
# =============================================================================


class TelegramScheduleReminderTests(TelegramNotificationTestMixin, TestCase):
    """Tests for schedule reminder notifications."""

    def test_schedule_reminder_sent_when_enabled(self):
        """Schedule reminder sent when enabled."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(notify_schedule_reminders=True)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            mock_send.return_value = True
            result = service.notify_schedule_reminder(
                self.chef, "You have 3 orders due tomorrow"
            )

        self.assertTrue(result)
        mock_send.assert_called_once()

    def test_schedule_reminder_blocked_when_disabled(self):
        """Schedule reminder blocked when disabled."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(notify_schedule_reminders=False)

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_schedule_reminder(
                self.chef, "Reminder text"
            )

        self.assertFalse(result)
        mock_send.assert_not_called()


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


class TelegramNotificationEdgeCasesTests(TelegramNotificationTestMixin, TestCase):
    """Tests for edge cases and error handling."""

    def test_notification_without_settings_record(self):
        """Notification blocked when settings record doesn't exist."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        # Setup: Link exists but no settings record
        self._create_telegram_link()
        # Note: NOT creating settings

        service = TelegramNotificationService()

        with patch.object(service, '_send') as mock_send:
            result = service.notify_new_order(self.chef, self.mock_order)

        self.assertFalse(result)
        mock_send.assert_not_called()

    def test_send_delegates_to_celery_task(self):
        """_send method queues message via Celery task."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(notify_new_orders=True)

        service = TelegramNotificationService()

        with patch('chefs.services.telegram_notification_service.send_telegram_message') as mock_task:
            mock_task.delay = MagicMock()
            result = service._send(self.chef, "Test message")

        self.assertTrue(result)
        mock_task.delay.assert_called_once_with(123456789, "Test message")

    def test_notification_outside_quiet_hours_is_sent(self):
        """Notification sent when outside quiet hours."""
        from chefs.services.telegram_notification_service import TelegramNotificationService

        self._create_telegram_link()
        self._create_telegram_settings(
            notify_new_orders=True,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(22, 0),  # 10pm
            quiet_hours_end=dt_time(8, 0),  # 8am
        )

        service = TelegramNotificationService()

        # Mock current time to be outside quiet hours (noon)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=12, minute=0)
            mock_localtime.return_value = mock_now

            with patch.object(service, '_send') as mock_send:
                mock_send.return_value = True
                result = service.notify_new_order(self.chef, self.mock_order)

        self.assertTrue(result)
        mock_send.assert_called_once()
