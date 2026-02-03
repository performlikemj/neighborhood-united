#!/usr/bin/env python
"""
Standalone tests for TelegramNotificationService.

These tests can run without a database connection by using mocks.
Run with: python chefs/tests/test_telegram_notifications_standalone.py

For full integration tests, use pytest with a PostgreSQL database.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup Django environment
os.environ['DJANGO_SETTINGS_MODULE'] = 'hood_united.settings'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['TEST_DB_NAME'] = 'test'
os.environ['TEST_DB_USER'] = 'test'
os.environ['TEST_DB_PASSWORD'] = 'test'
os.environ['TEST_DB_HOST'] = 'localhost'
os.environ['TEST_DB_PORT'] = '5432'
os.environ['SECRET_KEY'] = 'test-key'
os.environ['OPENAI_KEY'] = 'sk-test'
os.environ['GROQ_API_KEY'] = 'gsk-test'
os.environ['STRIPE_PUBLIC_KEY'] = 'pk_test'
os.environ['STRIPE_SECRET_KEY'] = 'sk_test'
os.environ['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'
os.environ['DEBUG'] = 'True'

import django
django.setup()

from unittest.mock import MagicMock, patch
from chefs.services.telegram_notification_service import TelegramNotificationService
from chefs.models import ChefTelegramLink, ChefTelegramSettings


def create_mock_chef(
    is_linked=True,
    is_active=True,
    has_settings=True,
    notify_new_orders=True,
    notify_order_updates=True,
    notify_schedule_reminders=True,
    is_quiet_hours=False,
):
    """Create a mock chef with configurable telegram settings."""
    mock_chef = MagicMock()
    mock_chef.id = 1

    if not is_linked:
        type(mock_chef).telegram_link = property(
            lambda self: (_ for _ in ()).throw(ChefTelegramLink.DoesNotExist())
        )
    else:
        mock_link = MagicMock()
        mock_link.is_active = is_active
        mock_link.telegram_user_id = 123456789
        mock_chef.telegram_link = mock_link

    if not has_settings:
        type(mock_chef).telegram_settings = property(
            lambda self: (_ for _ in ()).throw(ChefTelegramSettings.DoesNotExist())
        )
    else:
        mock_settings = MagicMock()
        mock_settings.notify_new_orders = notify_new_orders
        mock_settings.notify_order_updates = notify_order_updates
        mock_settings.notify_schedule_reminders = notify_schedule_reminders
        mock_settings.is_quiet_hours.return_value = is_quiet_hours
        mock_chef.telegram_settings = mock_settings

    return mock_chef


def create_mock_order(customer_first_name="John", order_id=42):
    """Create a mock order with sensitive customer data."""
    mock_order = MagicMock()
    mock_order.id = order_id
    mock_order.customer.first_name = customer_first_name
    # Sensitive data that should NEVER appear in notifications
    mock_order.customer.dietary_preference = "Keto"
    mock_order.customer.allergies = ["Peanuts", "Tree nuts", "Shellfish"]
    return mock_order


class TestRunner:
    def __init__(self):
        self.service = TelegramNotificationService()
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name, condition, error_msg=""):
        """Run a single test assertion."""
        try:
            if condition:
                print(f"  ✅ {name}")
                self.passed += 1
            else:
                print(f"  ❌ {name}")
                self.failed += 1
                if error_msg:
                    self.errors.append(f"{name}: {error_msg}")
        except Exception as e:
            print(f"  💥 {name} - Exception: {e}")
            self.failed += 1
            self.errors.append(f"{name}: Exception - {e}")

    def run_all(self):
        """Run all tests."""
        print("\n" + "=" * 60)
        print("TELEGRAM NOTIFICATION SERVICE TESTS")
        print("=" * 60)

        self.test_notification_sent_when_enabled()
        self.test_notification_blocked_when_disabled()
        self.test_notification_blocked_during_quiet_hours()
        self.test_notification_blocked_when_unlinked()
        self.test_notification_blocked_when_inactive()
        self.test_new_order_notification_format()
        self.test_notification_does_not_include_dietary_info()
        self.test_notification_includes_dashboard_link()
        self.test_order_update_notification()
        self.test_schedule_reminder_notification()
        self.test_send_delegates_to_celery()

        print("\n" + "-" * 60)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")

        if self.errors:
            print("\nFailed tests:")
            for error in self.errors:
                print(f"  - {error}")

        return self.failed == 0

    def test_notification_sent_when_enabled(self):
        print("\n[test_notification_sent_when_enabled]")
        chef = create_mock_chef(notify_new_orders=True)
        order = create_mock_order()

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            result = self.service.notify_new_order(chef, order)

        self.test("Returns True when enabled", result == True)
        self.test("_send was called", mock_send.called)

    def test_notification_blocked_when_disabled(self):
        print("\n[test_notification_blocked_when_disabled]")
        chef = create_mock_chef(notify_new_orders=False)
        order = create_mock_order()

        with patch.object(self.service, '_send') as mock_send:
            result = self.service.notify_new_order(chef, order)

        self.test("Returns False when disabled", result == False)
        self.test("_send was NOT called", not mock_send.called)

    def test_notification_blocked_during_quiet_hours(self):
        print("\n[test_notification_blocked_during_quiet_hours]")
        chef = create_mock_chef(notify_new_orders=True, is_quiet_hours=True)
        order = create_mock_order()

        with patch.object(self.service, '_send') as mock_send:
            result = self.service.notify_new_order(chef, order)

        self.test("Returns False during quiet hours", result == False)
        self.test("_send was NOT called", not mock_send.called)

    def test_notification_blocked_when_unlinked(self):
        print("\n[test_notification_blocked_when_unlinked]")
        chef = create_mock_chef(is_linked=False)
        order = create_mock_order()

        with patch.object(self.service, '_send') as mock_send:
            result = self.service.notify_new_order(chef, order)

        self.test("Returns False when unlinked", result == False)
        self.test("_send was NOT called", not mock_send.called)

    def test_notification_blocked_when_inactive(self):
        print("\n[test_notification_blocked_when_inactive]")
        chef = create_mock_chef(is_active=False)
        order = create_mock_order()

        with patch.object(self.service, '_send') as mock_send:
            result = self.service.notify_new_order(chef, order)

        self.test("Returns False when link inactive", result == False)
        self.test("_send was NOT called", not mock_send.called)

    def test_new_order_notification_format(self):
        print("\n[test_new_order_notification_format]")
        chef = create_mock_chef()
        order = create_mock_order(customer_first_name="Alice", order_id=99)

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            self.service.notify_new_order(chef, order)
            message = mock_send.call_args[0][1]

        self.test("Contains new order emoji", "🆕" in message)
        self.test("Contains customer first name", "Alice" in message)
        self.test("Contains 'order'", "order" in message.lower())

    def test_notification_does_not_include_dietary_info(self):
        print("\n[test_notification_does_not_include_dietary_info] (SECURITY)")
        chef = create_mock_chef()
        order = create_mock_order()

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            self.service.notify_new_order(chef, order)
            message = mock_send.call_args[0][1]

        # SECURITY: These must NEVER appear
        sensitive_terms = [
            "Keto", "keto",
            "Peanuts", "peanuts",
            "Tree nuts", "tree nuts",
            "Shellfish", "shellfish",
            "dietary", "Dietary",
            "allerg", "Allerg",
        ]

        all_safe = True
        for term in sensitive_terms:
            if term in message:
                self.test(f"Does NOT contain '{term}'", False, "SECURITY VIOLATION")
                all_safe = False

        if all_safe:
            self.test("No sensitive health data in message", True)

    def test_notification_includes_dashboard_link(self):
        print("\n[test_notification_includes_dashboard_link]")
        chef = create_mock_chef()
        order = create_mock_order(order_id=123)

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            self.service.notify_new_order(chef, order)
            message = mock_send.call_args[0][1]

        self.test("Contains order ID in link", "123" in message)
        has_link = "http" in message or "/orders/" in message
        self.test("Contains URL or path", has_link)

    def test_order_update_notification(self):
        print("\n[test_order_update_notification]")
        chef = create_mock_chef(notify_order_updates=True)
        order = create_mock_order()

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            result = self.service.notify_order_update(chef, order, "Status changed")
            message = mock_send.call_args[0][1]

        self.test("Returns True when enabled", result == True)
        self.test("Contains update emoji", "📦" in message)
        self.test("Contains update text", "Status changed" in message)

    def test_schedule_reminder_notification(self):
        print("\n[test_schedule_reminder_notification]")
        chef = create_mock_chef(notify_schedule_reminders=True)

        with patch.object(self.service, '_send', return_value=True) as mock_send:
            result = self.service.notify_schedule_reminder(chef, "3 orders tomorrow")
            message = mock_send.call_args[0][1]

        self.test("Returns True when enabled", result == True)
        self.test("Contains reminder emoji", "⏰" in message)
        self.test("Contains reminder text", "3 orders tomorrow" in message)

    def test_send_delegates_to_celery(self):
        print("\n[test_send_delegates_to_celery]")
        chef = create_mock_chef()

        with patch('chefs.services.telegram_notification_service.send_telegram_message') as mock_task:
            mock_task.delay = MagicMock()
            self.service._send(chef, "Test message")

            mock_task.delay.assert_called_once()
            call_args = mock_task.delay.call_args
            self.test("Called with telegram_user_id", call_args[0][0] == 123456789)
            self.test("Called with message", call_args[0][1] == "Test message")


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
