"""
Tests for Telegram Webhook - Phase 4.

Tests cover:
- Webhook security (X-Telegram-Bot-Api-Secret-Token validation)
- Message routing to linked chefs
- /start command handling for account linking
- Error handling for malformed requests

Run with: pytest chefs/tests/test_telegram_webhook.py -v

Note: Security tests use SimpleTestCase to avoid database setup issues.
Integration tests require a PostgreSQL database.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta


# =============================================================================
# WEBHOOK SECURITY TESTS (SimpleTestCase - no database required)
# =============================================================================


@override_settings(
    TELEGRAM_WEBHOOK_SECRET='test-secret-token-12345',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TelegramWebhookSecurityTests(SimpleTestCase):
    """Tests for webhook security validation.
    
    These tests verify the security of the webhook endpoint without
    requiring database access. Message processing is mocked.
    """
    # Allow database access temporarily for URL routing
    databases = []

    def setUp(self):
        self.client = Client()
        # Note: URL must match exactly - include trailing slash to avoid 301 redirect
        self.webhook_url = '/chefs/api/telegram/webhook/'
        self.valid_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 111222333,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {"id": 111222333, "type": "private"},
                "date": 1234567890,
                "text": "Hello"
            }
        }

    @patch('chefs.tasks.telegram_tasks.process_telegram_update')
    def test_valid_secret_token_accepted(self, mock_task):
        """Request with valid secret token returns 200."""
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345',
            follow=False,  # Don't follow redirects
        )
        self.assertEqual(response.status_code, 200)
        mock_task.assert_called_once()

    def test_invalid_secret_token_rejected(self):
        """Request with invalid secret token returns 403."""
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong-token'
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_secret_token_rejected(self):
        """Request without secret token returns 403."""
        response = self.client.post(
            self.webhook_url,
            data=json.dumps(self.valid_update),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_returns_400(self):
        """Malformed JSON returns 400."""
        response = self.client.post(
            self.webhook_url,
            data='not valid json {{{',
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )
        self.assertEqual(response.status_code, 400)


# =============================================================================
# MESSAGE ROUTING TESTS (Requires PostgreSQL database)
# =============================================================================

# Import models only when running database tests
try:
    from custom_auth.models import CustomUser
    from chefs.models import Chef
    from chefs.models.telegram_integration import (
        ChefTelegramLink,
        TelegramLinkToken,
        ChefTelegramSettings,
    )
    _DB_MODELS_AVAILABLE = True
except ImportError:
    _DB_MODELS_AVAILABLE = False


@override_settings(
    TELEGRAM_WEBHOOK_SECRET='test-secret-token-12345',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TelegramMessageRoutingTests(TestCase):
    """Tests for routing messages to the correct chef.
    
    NOTE: These tests require a PostgreSQL database with proper migrations.
    They will be skipped if running on SQLite.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _DB_MODELS_AVAILABLE:
            raise unittest.SkipTest("Database models not available")

    def setUp(self):
        self.client = Client()
        self.webhook_url = '/chefs/api/telegram/webhook/'

        # Create test chef with linked Telegram account
        self.user = CustomUser.objects.create_user(
            username="webhook_test_chef",
            email="webhook_test@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")
        self.telegram_user_id = 111222333

        # Create active Telegram link
        self.link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=self.telegram_user_id,
            telegram_username="testchef",
            telegram_first_name="Test",
            is_active=True,
        )

        # Create settings
        ChefTelegramSettings.objects.create(chef=self.chef)

    def _make_message_update(self, telegram_user_id: int, text: str) -> dict:
        """Create a Telegram message update payload."""
        return {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": telegram_user_id,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {"id": telegram_user_id, "type": "private"},
                "date": 1234567890,
                "text": text
            }
        }

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    @patch('chefs.tasks.telegram_tasks.process_chef_message')
    def test_message_routed_to_correct_chef(self, mock_process, mock_send):
        """Message from linked user routes to their chef."""
        mock_process.return_value = "Response from Sous Chef"

        update = self._make_message_update(self.telegram_user_id, "What orders do I have today?")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify process_chef_message was called with the correct chef
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        self.assertEqual(call_args[0][0], self.chef)  # First arg is chef
        self.assertEqual(call_args[0][1], "What orders do I have today?")  # Second is message

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_unknown_user_gets_error_message(self, mock_send):
        """Unlinked user gets friendly error message."""
        unknown_user_id = 999888777  # Not linked to any chef

        update = self._make_message_update(unknown_user_id, "Hello")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify error message was sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], unknown_user_id)  # Chat ID
        self.assertIn("don't recognize", call_args[0][1].lower())  # Error message

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_inactive_link_treated_as_unknown(self, mock_send):
        """Deactivated link = unknown user."""
        # Deactivate the link
        self.link.is_active = False
        self.link.save()

        update = self._make_message_update(self.telegram_user_id, "Hello")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify error message was sent (treated as unknown)
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertIn("don't recognize", call_args[0][1].lower())


# =============================================================================
# START COMMAND TESTS (Requires PostgreSQL database)
# =============================================================================


@override_settings(
    TELEGRAM_WEBHOOK_SECRET='test-secret-token-12345',
    CELERY_TASK_ALWAYS_EAGER=True,
)
class TelegramStartCommandTests(TestCase):
    """Tests for /start command handling.
    
    NOTE: These tests require a PostgreSQL database with proper migrations.
    They will be skipped if running on SQLite.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _DB_MODELS_AVAILABLE:
            raise unittest.SkipTest("Database models not available")

    def setUp(self):
        self.client = Client()
        self.webhook_url = '/chefs/api/telegram/webhook/'

        # Create test chef (not yet linked)
        self.user = CustomUser.objects.create_user(
            username="start_cmd_chef",
            email="start_cmd@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")
        self.telegram_user_id = 555666777

    def _make_start_command_update(self, telegram_user_id: int, token: str = None) -> dict:
        """Create a Telegram /start command update payload."""
        text = f"/start {token}" if token else "/start"
        return {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": telegram_user_id,
                    "first_name": "NewUser",
                    "username": "newuser"
                },
                "chat": {"id": telegram_user_id, "type": "private"},
                "date": 1234567890,
                "text": text
            }
        }

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_start_with_valid_token_links(self, mock_send):
        """'/start <token>' with valid token links account."""
        # Create a valid link token
        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="valid-test-token-abc123",
            expires_at=timezone.now() + timedelta(minutes=10),
            used=False,
        )

        update = self._make_start_command_update(self.telegram_user_id, "valid-test-token-abc123")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify link was created
        link = ChefTelegramLink.objects.filter(
            telegram_user_id=self.telegram_user_id,
            chef=self.chef,
            is_active=True
        ).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.telegram_username, "newuser")
        self.assertEqual(link.telegram_first_name, "NewUser")

        # Verify token is now used
        token.refresh_from_db()
        self.assertTrue(token.used)

        # Verify success message sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], self.telegram_user_id)
        # Message should be welcoming/confirming link
        self.assertTrue(
            "linked" in call_args[0][1].lower() or
            "connected" in call_args[0][1].lower() or
            "welcome" in call_args[0][1].lower()
        )

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_start_with_invalid_token_fails(self, mock_send):
        """'/start <token>' with bad token sends error."""
        update = self._make_start_command_update(self.telegram_user_id, "invalid-token-xyz")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify no link was created
        link = ChefTelegramLink.objects.filter(telegram_user_id=self.telegram_user_id).first()
        self.assertIsNone(link)

        # Verify error message sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        # Message should indicate failure
        self.assertTrue(
            "invalid" in call_args[0][1].lower() or
            "expired" in call_args[0][1].lower() or
            "error" in call_args[0][1].lower() or
            "failed" in call_args[0][1].lower()
        )

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_start_with_expired_token_fails(self, mock_send):
        """'/start <token>' with expired token sends error."""
        # Create an expired token
        TelegramLinkToken.objects.create(
            chef=self.chef,
            token="expired-test-token",
            expires_at=timezone.now() - timedelta(minutes=1),  # Expired
            used=False,
        )

        update = self._make_start_command_update(self.telegram_user_id, "expired-test-token")

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify no link was created
        link = ChefTelegramLink.objects.filter(telegram_user_id=self.telegram_user_id).first()
        self.assertIsNone(link)

    @patch('chefs.tasks.telegram_tasks.send_telegram_message')
    def test_start_without_token_sends_welcome(self, mock_send):
        """'/start' alone sends generic welcome message."""
        update = self._make_start_command_update(self.telegram_user_id)  # No token

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(update),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='test-secret-token-12345'
        )

        self.assertEqual(response.status_code, 200)

        # Verify welcome message sent
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        self.assertEqual(call_args[0][0], self.telegram_user_id)
