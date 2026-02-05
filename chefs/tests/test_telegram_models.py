"""
Tests for Telegram Integration Models - Phase 1.

Tests cover:
- ChefTelegramLink model (linking chef to Telegram account)
- TelegramLinkToken model (one-time linking tokens)
- ChefTelegramSettings model (notification preferences)

Run with: pytest chefs/tests/test_telegram_models.py -v
"""

from datetime import time as dt_time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone

from custom_auth.models import CustomUser
from chefs.models import Chef


# =============================================================================
# CHEF TELEGRAM LINK MODEL TESTS
# =============================================================================


class ChefTelegramLinkTests(TestCase):
    """Tests for ChefTelegramLink model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="telegram_test_chef",
            email="telegram_test@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_chef_can_have_one_telegram_link(self):
        """Each chef can only have one Telegram link (OneToOneField)."""
        from chefs.models import ChefTelegramLink

        # Create first link
        ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
            telegram_username="testuser",
        )

        # Attempt to create second link should fail
        with self.assertRaises(IntegrityError):
            ChefTelegramLink.objects.create(
                chef=self.chef,
                telegram_user_id=987654321,
                telegram_username="anotheruser",
            )

    def test_telegram_user_id_is_unique(self):
        """Same Telegram user can't link to multiple chefs."""
        from chefs.models import ChefTelegramLink

        # Create another chef
        user2 = CustomUser.objects.create_user(
            username="telegram_test_chef2",
            email="telegram_test2@example.com",
            password="testpass123",
        )
        chef2 = Chef.objects.create(user=user2, bio="Test chef 2")

        # Create link for first chef
        ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
            telegram_username="testuser",
        )

        # Attempt to create link with same telegram_user_id for second chef should fail
        with self.assertRaises(IntegrityError):
            ChefTelegramLink.objects.create(
                chef=chef2,
                telegram_user_id=123456789,
                telegram_username="testuser",
            )

    def test_unlink_sets_inactive(self):
        """Unlinking sets is_active=False, preserves record."""
        from chefs.models import ChefTelegramLink

        link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
            telegram_username="testuser",
            is_active=True,
        )

        # Deactivate the link
        link.is_active = False
        link.save()

        # Verify link still exists but is inactive
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        self.assertEqual(link.telegram_user_id, 123456789)

    def test_telegram_link_str_method(self):
        """Test string representation of ChefTelegramLink."""
        from chefs.models import ChefTelegramLink

        link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
            telegram_username="testuser",
        )

        # Should contain chef username and telegram info
        self.assertIn("telegram_test_chef", str(link))

    def test_telegram_link_defaults(self):
        """Test default values for ChefTelegramLink."""
        from chefs.models import ChefTelegramLink

        link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
        )

        self.assertTrue(link.is_active)  # Default True
        self.assertIsNone(link.telegram_username)  # Blank allowed
        self.assertIsNone(link.telegram_first_name)  # Blank allowed
        self.assertIsNotNone(link.linked_at)  # Auto-set

    def test_related_name_access(self):
        """Test accessing telegram_link via chef.telegram_link."""
        from chefs.models import ChefTelegramLink

        link = ChefTelegramLink.objects.create(
            chef=self.chef,
            telegram_user_id=123456789,
            telegram_username="testuser",
        )

        # Access via related_name
        self.assertEqual(self.chef.telegram_link, link)
        self.assertEqual(self.chef.telegram_link.telegram_user_id, 123456789)


# =============================================================================
# TELEGRAM LINK TOKEN MODEL TESTS
# =============================================================================


class TelegramLinkTokenTests(TestCase):
    """Tests for TelegramLinkToken model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="token_test_chef",
            email="token_test@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_token_expires_after_period(self):
        """Tokens have an expiration time."""
        from chefs.models import TelegramLinkToken

        expires_at = timezone.now() + timedelta(minutes=10)
        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="test_token_12345",
            expires_at=expires_at,
        )

        self.assertIsNotNone(token.expires_at)
        self.assertGreater(token.expires_at, timezone.now())

    def test_token_single_use(self):
        """Token can only be used once (used flag)."""
        from chefs.models import TelegramLinkToken

        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="test_token_12345",
            expires_at=timezone.now() + timedelta(minutes=10),
            used=False,
        )

        # Mark as used
        token.used = True
        token.save()

        token.refresh_from_db()
        self.assertTrue(token.used)

    def test_expired_token_is_invalid(self):
        """is_valid returns False for expired tokens."""
        from chefs.models import TelegramLinkToken

        # Create already-expired token
        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="expired_token_12345",
            expires_at=timezone.now() - timedelta(minutes=1),
            used=False,
        )

        self.assertFalse(token.is_valid)

    def test_used_token_is_invalid(self):
        """is_valid returns False for used tokens."""
        from chefs.models import TelegramLinkToken

        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="used_token_12345",
            expires_at=timezone.now() + timedelta(minutes=10),
            used=True,
        )

        self.assertFalse(token.is_valid)

    def test_valid_token_is_valid(self):
        """is_valid returns True for valid (unused, not expired) tokens."""
        from chefs.models import TelegramLinkToken

        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="valid_token_12345",
            expires_at=timezone.now() + timedelta(minutes=10),
            used=False,
        )

        self.assertTrue(token.is_valid)

    def test_token_uniqueness(self):
        """Token values must be unique."""
        from chefs.models import TelegramLinkToken

        TelegramLinkToken.objects.create(
            chef=self.chef,
            token="unique_token_12345",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Creating token with same value should fail
        with self.assertRaises(IntegrityError):
            TelegramLinkToken.objects.create(
                chef=self.chef,
                token="unique_token_12345",
                expires_at=timezone.now() + timedelta(minutes=10),
            )

    def test_chef_can_have_multiple_tokens(self):
        """Chef can have multiple tokens (ForeignKey, not OneToOne)."""
        from chefs.models import TelegramLinkToken

        token1 = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="token_one",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        token2 = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="token_two",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        self.assertEqual(TelegramLinkToken.objects.filter(chef=self.chef).count(), 2)

    def test_token_str_method(self):
        """Test string representation of TelegramLinkToken."""
        from chefs.models import TelegramLinkToken

        token = TelegramLinkToken.objects.create(
            chef=self.chef,
            token="test_token_for_str",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Should be informative
        str_repr = str(token)
        self.assertIsInstance(str_repr, str)


# =============================================================================
# CHEF TELEGRAM SETTINGS MODEL TESTS
# =============================================================================


class ChefTelegramSettingsTests(TestCase):
    """Tests for ChefTelegramSettings model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="settings_test_chef",
            email="settings_test@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_default_settings_created(self):
        """Default settings are sensible."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(chef=self.chef)

        # Check default values
        self.assertTrue(settings.notify_new_orders)
        self.assertTrue(settings.notify_order_updates)
        self.assertTrue(settings.notify_schedule_reminders)
        self.assertFalse(settings.notify_customer_messages)  # Default False
        self.assertTrue(settings.quiet_hours_enabled)
        self.assertEqual(settings.quiet_hours_start, dt_time(22, 0))  # 10pm
        self.assertEqual(settings.quiet_hours_end, dt_time(8, 0))  # 8am

    def test_quiet_hours_same_day(self):
        """Quiet hours work when start < end (same day, e.g., 9am-5pm)."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(9, 0),  # 9am
            quiet_hours_end=dt_time(17, 0),  # 5pm
        )

        # Test time within quiet hours (noon)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=12, minute=0)
            mock_localtime.return_value = mock_now
            self.assertTrue(settings.is_quiet_hours())

        # Test time outside quiet hours (8am)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=8, minute=0)
            mock_localtime.return_value = mock_now
            self.assertFalse(settings.is_quiet_hours())

        # Test time outside quiet hours (6pm)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=18, minute=0)
            mock_localtime.return_value = mock_now
            self.assertFalse(settings.is_quiet_hours())

    def test_quiet_hours_cross_midnight(self):
        """Quiet hours work when crossing midnight (e.g., 10pm-8am)."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(22, 0),  # 10pm
            quiet_hours_end=dt_time(8, 0),  # 8am
        )

        # Test time within quiet hours (11pm - after start)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=23, minute=0)
            mock_localtime.return_value = mock_now
            self.assertTrue(settings.is_quiet_hours())

        # Test time within quiet hours (3am - before end)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=3, minute=0)
            mock_localtime.return_value = mock_now
            self.assertTrue(settings.is_quiet_hours())

        # Test time outside quiet hours (noon)
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=12, minute=0)
            mock_localtime.return_value = mock_now
            self.assertFalse(settings.is_quiet_hours())

    def test_quiet_hours_disabled(self):
        """is_quiet_hours returns False when quiet hours disabled."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=False,
            quiet_hours_start=dt_time(22, 0),
            quiet_hours_end=dt_time(8, 0),
        )

        # Even during quiet hours time, should return False
        with patch('django.utils.timezone.localtime') as mock_localtime:
            mock_now = timezone.now().replace(hour=23, minute=0)
            mock_localtime.return_value = mock_now
            self.assertFalse(settings.is_quiet_hours())

    def test_settings_one_per_chef(self):
        """Each chef can only have one settings record (OneToOneField)."""
        from chefs.models import ChefTelegramSettings

        ChefTelegramSettings.objects.create(chef=self.chef)

        with self.assertRaises(IntegrityError):
            ChefTelegramSettings.objects.create(chef=self.chef)

    def test_related_name_access(self):
        """Test accessing settings via chef.telegram_settings."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(
            chef=self.chef,
            notify_new_orders=False,
        )

        # Access via related_name
        self.assertEqual(self.chef.telegram_settings, settings)
        self.assertFalse(self.chef.telegram_settings.notify_new_orders)

    def test_settings_str_method(self):
        """Test string representation of ChefTelegramSettings."""
        from chefs.models import ChefTelegramSettings

        settings = ChefTelegramSettings.objects.create(chef=self.chef)

        str_repr = str(settings)
        self.assertIsInstance(str_repr, str)
        self.assertIn("settings_test_chef", str_repr)
