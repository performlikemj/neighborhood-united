"""
Tests for Sous Chef Proactive Engine Models.

Tests cover:
- ChefProactiveSettings model methods
- ChefOnboardingState model methods
- ChefNotification model methods

Run with: pytest chefs/tests/test_proactive_models.py -v
"""

from datetime import datetime as dt_datetime, time as dt_time, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from custom_auth.models import CustomUser
from chefs.models import (
    Chef,
    ChefProactiveSettings,
    ChefOnboardingState,
    ChefNotification,
)


# =============================================================================
# CHEF PROACTIVE SETTINGS MODEL TESTS
# =============================================================================


class ChefProactiveSettingsModelTests(TestCase):
    """Tests for ChefProactiveSettings model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="proactive_model_chef",
            email="proactive_model@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_get_or_create_for_chef_creates_with_defaults(self):
        """get_or_create_for_chef should create settings with defaults."""
        self.assertFalse(ChefProactiveSettings.objects.filter(chef=self.chef).exists())

        settings = ChefProactiveSettings.get_or_create_for_chef(self.chef)

        self.assertIsNotNone(settings)
        self.assertEqual(settings.chef, self.chef)
        # Master switch should be OFF by default
        self.assertFalse(settings.enabled)
        # Feature toggles should be ON by default
        self.assertTrue(settings.notify_birthdays)
        self.assertTrue(settings.notify_followups)
        self.assertTrue(settings.notify_todos)
        # Default frequency
        self.assertEqual(settings.notification_frequency, 'daily')
        # Default channels
        self.assertTrue(settings.channel_in_app)
        self.assertFalse(settings.channel_email)
        self.assertFalse(settings.channel_push)

    def test_get_or_create_for_chef_returns_existing(self):
        """get_or_create_for_chef should return existing settings."""
        existing = ChefProactiveSettings.objects.create(
            chef=self.chef,
            enabled=True,
            notify_birthdays=False,
        )

        settings = ChefProactiveSettings.get_or_create_for_chef(self.chef)

        self.assertEqual(settings.id, existing.id)
        self.assertTrue(settings.enabled)
        self.assertFalse(settings.notify_birthdays)

    def test_is_within_quiet_hours_returns_false_when_disabled(self):
        """is_within_quiet_hours should return False when quiet hours disabled."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=False,
            quiet_hours_start=dt_time(22, 0),
            quiet_hours_end=dt_time(8, 0),
        )

        self.assertFalse(settings.is_within_quiet_hours())

    def test_is_within_quiet_hours_returns_false_when_times_not_set(self):
        """is_within_quiet_hours should return False when times not set."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=None,
            quiet_hours_end=None,
        )

        self.assertFalse(settings.is_within_quiet_hours())

    def test_is_within_quiet_hours_same_day_range(self):
        """is_within_quiet_hours should handle same-day ranges (e.g., 09:00-17:00)."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(9, 0),
            quiet_hours_end=dt_time(17, 0),
            quiet_hours_timezone='UTC',
        )

        # Mock time to 12:00 UTC (within range)
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
            self.assertTrue(settings.is_within_quiet_hours())

        # Mock time to 20:00 UTC (outside range)
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 15, 20, 0, tzinfo=dt_timezone.utc)
            self.assertFalse(settings.is_within_quiet_hours())

    def test_is_within_quiet_hours_overnight_range(self):
        """is_within_quiet_hours should handle overnight ranges (e.g., 22:00-08:00)."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(22, 0),
            quiet_hours_end=dt_time(8, 0),
            quiet_hours_timezone='UTC',
        )

        # Mock time to 23:00 UTC (within range - after start)
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 15, 23, 0, tzinfo=dt_timezone.utc)
            self.assertTrue(settings.is_within_quiet_hours())

        # Mock time to 06:00 UTC (within range - before end)
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 16, 6, 0, tzinfo=dt_timezone.utc)
            self.assertTrue(settings.is_within_quiet_hours())

        # Mock time to 12:00 UTC (outside range)
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
            self.assertFalse(settings.is_within_quiet_hours())

    def test_is_within_quiet_hours_handles_invalid_timezone(self):
        """is_within_quiet_hours should default to UTC for invalid timezone."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            quiet_hours_enabled=True,
            quiet_hours_start=dt_time(9, 0),
            quiet_hours_end=dt_time(17, 0),
            quiet_hours_timezone='Invalid/Timezone',
        )

        # Should not raise exception, should use UTC fallback
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dt_datetime(2024, 1, 15, 12, 0, tzinfo=dt_timezone.utc)
            # Should work without raising exception
            result = settings.is_within_quiet_hours()
            self.assertIsInstance(result, bool)

    def test_str_representation(self):
        """__str__ should return readable representation."""
        settings = ChefProactiveSettings.objects.create(
            chef=self.chef,
            enabled=True,
        )

        self.assertIn('enabled', str(settings))
        self.assertIn(str(self.chef.id), str(settings))


# =============================================================================
# CHEF ONBOARDING STATE MODEL TESTS
# =============================================================================


class ChefOnboardingStateModelTests(TestCase):
    """Tests for ChefOnboardingState model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="onboarding_model_chef",
            email="onboarding_model@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_get_or_create_for_chef_creates_with_defaults(self):
        """get_or_create_for_chef should create state with defaults."""
        self.assertFalse(ChefOnboardingState.objects.filter(chef=self.chef).exists())

        state = ChefOnboardingState.get_or_create_for_chef(self.chef)

        self.assertIsNotNone(state)
        self.assertEqual(state.chef, self.chef)
        self.assertFalse(state.welcomed)
        self.assertFalse(state.setup_started)
        self.assertFalse(state.setup_completed)
        self.assertFalse(state.setup_skipped)
        self.assertFalse(state.first_dish_added)
        self.assertEqual(state.tips_shown, [])
        self.assertEqual(state.tips_dismissed, [])

    def test_get_or_create_for_chef_returns_existing(self):
        """get_or_create_for_chef should return existing state."""
        existing = ChefOnboardingState.objects.create(
            chef=self.chef,
            welcomed=True,
            first_dish_added=True,
        )

        state = ChefOnboardingState.get_or_create_for_chef(self.chef)

        self.assertEqual(state.id, existing.id)
        self.assertTrue(state.welcomed)
        self.assertTrue(state.first_dish_added)

    def test_mark_welcomed_sets_flag_and_timestamp(self):
        """mark_welcomed should set flag and timestamp."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        self.assertFalse(state.welcomed)
        self.assertIsNone(state.welcomed_at)

        state.mark_welcomed()

        state.refresh_from_db()
        self.assertTrue(state.welcomed)
        self.assertIsNotNone(state.welcomed_at)

    def test_mark_welcomed_is_idempotent(self):
        """mark_welcomed should not change timestamp on subsequent calls."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        state.mark_welcomed()
        first_timestamp = state.welcomed_at

        state.mark_welcomed()
        state.refresh_from_db()

        # Timestamp should not change
        self.assertEqual(state.welcomed_at, first_timestamp)

    def test_mark_setup_started_sets_flag_and_timestamp(self):
        """mark_setup_started should set flag and timestamp."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        state.mark_setup_started()

        state.refresh_from_db()
        self.assertTrue(state.setup_started)
        self.assertIsNotNone(state.setup_started_at)

    def test_mark_setup_completed_sets_flag_and_clears_skipped(self):
        """mark_setup_completed should set flag and clear skipped."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            setup_skipped=True,
        )

        state.mark_setup_completed()

        state.refresh_from_db()
        self.assertTrue(state.setup_completed)
        self.assertFalse(state.setup_skipped)  # Should be cleared
        self.assertIsNotNone(state.setup_completed_at)

    def test_mark_setup_skipped_sets_flag_if_not_completed(self):
        """mark_setup_skipped should set flag only if not completed."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        state.mark_setup_skipped()

        state.refresh_from_db()
        self.assertTrue(state.setup_skipped)
        self.assertIsNotNone(state.setup_skipped_at)

    def test_mark_setup_skipped_does_nothing_if_completed(self):
        """mark_setup_skipped should not set flag if already completed."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            setup_completed=True,
        )

        state.mark_setup_skipped()

        state.refresh_from_db()
        self.assertFalse(state.setup_skipped)

    def test_record_milestone_first_dish(self):
        """record_milestone should record first_dish milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('first_dish')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.first_dish_added)
        self.assertIsNotNone(state.first_dish_added_at)

    def test_record_milestone_first_client(self):
        """record_milestone should record first_client milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('first_client')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.first_client_added)
        self.assertIsNotNone(state.first_client_added_at)

    def test_record_milestone_first_conversation(self):
        """record_milestone should record first_conversation milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('first_conversation')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.first_conversation)
        self.assertIsNotNone(state.first_conversation_at)

    def test_record_milestone_first_memory(self):
        """record_milestone should record first_memory milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('first_memory')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.first_memory_saved)
        self.assertIsNotNone(state.first_memory_saved_at)

    def test_record_milestone_first_order(self):
        """record_milestone should record first_order milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('first_order')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.first_order_completed)
        self.assertIsNotNone(state.first_order_completed_at)

    def test_record_milestone_proactive_enabled(self):
        """record_milestone should record proactive_enabled milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('proactive_enabled')

        self.assertTrue(result)
        state.refresh_from_db()
        self.assertTrue(state.proactive_enabled)
        self.assertIsNotNone(state.proactive_enabled_at)

    def test_record_milestone_is_idempotent(self):
        """record_milestone should return False on second call."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        # First call
        result1 = state.record_milestone('first_dish')
        self.assertTrue(result1)

        first_timestamp = state.first_dish_added_at

        # Second call
        result2 = state.record_milestone('first_dish')
        self.assertFalse(result2)

        # Timestamp should not change
        state.refresh_from_db()
        self.assertEqual(state.first_dish_added_at, first_timestamp)

    def test_record_milestone_invalid_returns_false(self):
        """record_milestone should return False for invalid milestone."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        result = state.record_milestone('invalid_milestone')

        self.assertFalse(result)

    def test_show_tip_adds_to_list(self):
        """show_tip should add tip_id to tips_shown list."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        state.show_tip('add_first_dish')

        state.refresh_from_db()
        self.assertIn('add_first_dish', state.tips_shown)

    def test_show_tip_does_not_duplicate(self):
        """show_tip should not add duplicate tip_id."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            tips_shown=['add_first_dish'],
        )

        state.show_tip('add_first_dish')

        state.refresh_from_db()
        self.assertEqual(state.tips_shown.count('add_first_dish'), 1)

    def test_dismiss_tip_adds_to_list(self):
        """dismiss_tip should add tip_id to tips_dismissed list."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        state.dismiss_tip('add_first_dish')

        state.refresh_from_db()
        self.assertIn('add_first_dish', state.tips_dismissed)

    def test_dismiss_tip_does_not_duplicate(self):
        """dismiss_tip should not add duplicate tip_id."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            tips_dismissed=['add_first_dish'],
        )

        state.dismiss_tip('add_first_dish')

        state.refresh_from_db()
        self.assertEqual(state.tips_dismissed.count('add_first_dish'), 1)

    def test_should_show_tip_returns_true_if_not_dismissed(self):
        """should_show_tip should return True if tip not dismissed."""
        state = ChefOnboardingState.objects.create(chef=self.chef)

        self.assertTrue(state.should_show_tip('add_first_dish'))

    def test_should_show_tip_returns_false_if_dismissed(self):
        """should_show_tip should return False if tip is dismissed."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            tips_dismissed=['add_first_dish'],
        )

        self.assertFalse(state.should_show_tip('add_first_dish'))

    def test_str_representation(self):
        """__str__ should return readable representation."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            setup_completed=True,
        )

        self.assertIn('completed', str(state))
        self.assertIn(str(self.chef.id), str(state))


# =============================================================================
# CHEF NOTIFICATION MODEL TESTS
# =============================================================================


class ChefNotificationModelTests(TestCase):
    """Tests for ChefNotification model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="notification_model_chef",
            email="notification_model@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.user, bio="Test chef")

    def test_create_notification_basic(self):
        """create_notification should create a basic notification."""
        notification = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='welcome',
            title='Welcome!',
            message='Welcome to the platform',
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.chef, self.chef)
        self.assertEqual(notification.notification_type, 'welcome')
        self.assertEqual(notification.title, 'Welcome!')
        self.assertEqual(notification.message, 'Welcome to the platform')
        self.assertEqual(notification.status, ChefNotification.STATUS_PENDING)

    def test_create_notification_with_action_context(self):
        """create_notification should store action_context."""
        notification = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='birthday',
            title='Birthday Reminder',
            message='John Doe has a birthday coming up',
            action_context={'prePrompt': 'Plan a birthday meal for John Doe'},
        )

        self.assertEqual(notification.action_context, {
            'prePrompt': 'Plan a birthday meal for John Doe'
        })

    def test_create_notification_with_dedup_key_prevents_duplicates(self):
        """create_notification with dedup_key should prevent duplicates."""
        # Create first notification
        notification1 = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='birthday',
            title='Birthday 1',
            message='Message 1',
            dedup_key='birthday_john_2024-03-15',
        )

        # Try to create duplicate
        notification2 = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='birthday',
            title='Birthday 2',
            message='Message 2',
            dedup_key='birthday_john_2024-03-15',
        )

        # Should return the existing notification
        self.assertEqual(notification1.id, notification2.id)
        self.assertEqual(notification2.title, 'Birthday 1')  # Original title

        # Should only have one notification in DB
        count = ChefNotification.objects.filter(
            chef=self.chef,
            dedup_key='birthday_john_2024-03-15'
        ).count()
        self.assertEqual(count, 1)

    def test_create_notification_dedup_key_expires_after_7_days(self):
        """create_notification dedup_key should expire after 7 days."""
        # Create old notification
        old_notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='birthday',
            title='Old Birthday',
            message='Old message',
            dedup_key='birthday_john_2024-03-15',
        )
        # Manually set created_at to 8 days ago
        old_notification.created_at = timezone.now() - timezone.timedelta(days=8)
        old_notification.save(update_fields=['created_at'])

        # Create new notification with same dedup_key
        new_notification = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='birthday',
            title='New Birthday',
            message='New message',
            dedup_key='birthday_john_2024-03-15',
        )

        # Should create a new notification
        self.assertNotEqual(old_notification.id, new_notification.id)
        self.assertEqual(new_notification.title, 'New Birthday')

    def test_create_notification_without_dedup_key_allows_duplicates(self):
        """create_notification without dedup_key should allow duplicates."""
        notification1 = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='system',
            title='System Notice',
            message='Message 1',
        )

        notification2 = ChefNotification.create_notification(
            chef=self.chef,
            notification_type='system',
            title='System Notice',
            message='Message 2',
        )

        # Should create two separate notifications
        self.assertNotEqual(notification1.id, notification2.id)

    def test_get_unread_count_counts_pending_and_sent(self):
        """get_unread_count should count pending and sent notifications."""
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Pending',
            message='Pending',
            status=ChefNotification.STATUS_PENDING,
        )
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Sent',
            message='Sent',
            status=ChefNotification.STATUS_SENT,
        )
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Read',
            message='Read',
            status=ChefNotification.STATUS_READ,
        )
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Dismissed',
            message='Dismissed',
            status=ChefNotification.STATUS_DISMISSED,
        )

        count = ChefNotification.get_unread_count(self.chef)

        # Should count only pending and sent
        self.assertEqual(count, 2)

    def test_get_unread_count_returns_zero_for_no_notifications(self):
        """get_unread_count should return 0 when no notifications exist."""
        count = ChefNotification.get_unread_count(self.chef)
        self.assertEqual(count, 0)

    def test_get_pending_for_chef_returns_pending_and_sent(self):
        """get_pending_for_chef should return pending/sent notifications."""
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Pending',
            message='Pending',
            status=ChefNotification.STATUS_PENDING,
        )
        ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Read',
            message='Read',
            status=ChefNotification.STATUS_READ,
        )

        notifications = ChefNotification.get_pending_for_chef(self.chef)

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Pending')

    def test_get_pending_for_chef_respects_limit(self):
        """get_pending_for_chef should respect limit parameter."""
        for i in range(10):
            ChefNotification.objects.create(
                chef=self.chef,
                notification_type='system',
                title=f'Notification {i}',
                message='Message',
            )

        notifications = ChefNotification.get_pending_for_chef(self.chef, limit=5)

        self.assertEqual(len(notifications), 5)

    def test_get_pending_for_chef_orders_by_created_at_desc(self):
        """get_pending_for_chef should order by created_at descending."""
        old = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Old',
            message='Old',
        )
        old.created_at = timezone.now() - timezone.timedelta(hours=1)
        old.save(update_fields=['created_at'])

        new = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='New',
            message='New',
        )

        notifications = ChefNotification.get_pending_for_chef(self.chef)

        # New should be first
        self.assertEqual(notifications[0].title, 'New')
        self.assertEqual(notifications[1].title, 'Old')

    def test_mark_sent_updates_status_and_channel(self):
        """mark_sent should update status and channel flag."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
        )

        notification.mark_sent('in_app')

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_SENT)
        self.assertTrue(notification.sent_in_app)
        self.assertIsNotNone(notification.sent_at)

    def test_mark_sent_email_channel(self):
        """mark_sent should mark email channel when specified."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
        )

        notification.mark_sent('email')

        notification.refresh_from_db()
        self.assertTrue(notification.sent_email)

    def test_mark_sent_push_channel(self):
        """mark_sent should mark push channel when specified."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
        )

        notification.mark_sent('push')

        notification.refresh_from_db()
        self.assertTrue(notification.sent_push)

    def test_mark_read_updates_status_and_timestamp(self):
        """mark_read should update status and timestamp."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
        )

        notification.mark_read()

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_READ)
        self.assertIsNotNone(notification.read_at)

    def test_mark_read_does_not_update_dismissed(self):
        """mark_read should not change dismissed status."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
            status=ChefNotification.STATUS_DISMISSED,
        )

        notification.mark_read()

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_DISMISSED)

    def test_mark_dismissed_updates_status_and_timestamp(self):
        """mark_dismissed should update status and timestamp."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='system',
            title='Test',
            message='Test',
        )

        notification.mark_dismissed()

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_DISMISSED)
        self.assertIsNotNone(notification.dismissed_at)

    def test_str_representation(self):
        """__str__ should return readable representation."""
        notification = ChefNotification.objects.create(
            chef=self.chef,
            notification_type='birthday',
            title='Birthday Reminder',
            message='Test',
        )

        self.assertIn('birthday', str(notification))
        self.assertIn('Birthday Reminder', str(notification))

    def test_notification_types_are_valid(self):
        """All notification types should be valid choices."""
        valid_types = [t[0] for t in ChefNotification.NOTIFICATION_TYPES]

        self.assertIn('welcome', valid_types)
        self.assertIn('birthday', valid_types)
        self.assertIn('anniversary', valid_types)
        self.assertIn('followup', valid_types)
        self.assertIn('todo', valid_types)
        self.assertIn('seasonal', valid_types)
        self.assertIn('milestone', valid_types)
        self.assertIn('tip', valid_types)
        self.assertIn('system', valid_types)

    def test_status_choices_are_valid(self):
        """All status choices should be valid."""
        valid_statuses = [s[0] for s in ChefNotification.STATUS_CHOICES]

        self.assertIn('pending', valid_statuses)
        self.assertIn('sent', valid_statuses)
        self.assertIn('read', valid_statuses)
        self.assertIn('dismissed', valid_statuses)
