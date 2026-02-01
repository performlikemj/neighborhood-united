"""
Tests for Sous Chef Proactive Engine API.

Tests cover:
- Security (authentication, authorization, data isolation)
- Onboarding API endpoints
- Proactive Settings API endpoints
- Notifications API endpoints

Run with: pytest chefs/tests/test_proactive_api.py -v
"""

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from custom_auth.models import CustomUser
from chefs.models import (
    Chef,
    ChefOnboardingState,
    ChefProactiveSettings,
    ChefNotification,
)


# =============================================================================
# SECURITY TESTS
# =============================================================================


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class ProactiveApiSecurityTests(TestCase):
    """Tests for authentication and authorization security across all endpoints."""

    def setUp(self):
        self.client = APIClient()

        # Create a regular customer (non-chef)
        self.customer = CustomUser.objects.create_user(
            username="customer_proactive",
            email="customer_proactive@example.com",
            password="testpass123",
        )

        # Create a chef user
        self.chef_user = CustomUser.objects.create_user(
            username="chef_proactive",
            email="chef_proactive@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")

        # Create another chef for isolation tests
        self.other_chef_user = CustomUser.objects.create_user(
            username="other_chef_proactive",
            email="other_proactive@example.com",
            password="testpass123",
        )
        self.other_chef = Chef.objects.create(user=self.other_chef_user, bio="Other chef")

    def _authenticate(self, user=None):
        if user is None:
            self.client.force_authenticate(user=None)
        else:
            self.client.force_authenticate(user=user)

    # -------------------------------------------------------------------------
    # Onboarding API Security Tests
    # -------------------------------------------------------------------------

    def test_onboarding_get_requires_authentication(self):
        """Onboarding GET endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_onboarding')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [401, 403])

    def test_onboarding_get_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from accessing onboarding."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_onboarding')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.data)

    def test_onboarding_welcomed_requires_authentication(self):
        """Onboarding welcomed endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_onboarding_welcomed')
        resp = self.client.post(url)
        self.assertIn(resp.status_code, [401, 403])

    def test_onboarding_welcomed_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from marking welcomed."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_onboarding_welcomed')
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # Proactive Settings API Security Tests
    # -------------------------------------------------------------------------

    def test_proactive_get_requires_authentication(self):
        """Proactive GET endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_proactive')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [401, 403])

    def test_proactive_get_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from accessing proactive settings."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_proactive')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.data)

    def test_proactive_update_requires_authentication(self):
        """Proactive update endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {"enabled": True}, format='json')
        self.assertIn(resp.status_code, [401, 403])

    def test_proactive_update_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from updating proactive settings."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {"enabled": True}, format='json')
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # Notifications API Security Tests
    # -------------------------------------------------------------------------

    def test_notifications_list_requires_authentication(self):
        """Notifications list endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [401, 403])

    def test_notifications_list_forbidden_for_non_chef(self):
        """Non-chef users should be forbidden from accessing notifications."""
        self._authenticate(self.customer)
        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.data)

    def test_notifications_unread_count_requires_authentication(self):
        """Unread count endpoint should reject unauthenticated requests."""
        self._authenticate(None)
        url = reverse('chefs:chef_notifications_unread_count')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [401, 403])

    # -------------------------------------------------------------------------
    # Data Isolation Tests
    # -------------------------------------------------------------------------

    def test_chef_cannot_read_other_chef_notification(self):
        """A chef should not be able to access another chef's notification."""
        # Create notification for other_chef
        notification = ChefNotification.objects.create(
            chef=self.other_chef,
            notification_type='welcome',
            title='Welcome',
            message='Hello other chef',
        )

        self._authenticate(self.chef_user)
        url = reverse('chefs:chef_notification_detail', kwargs={'notification_id': notification.id})
        resp = self.client.get(url)

        # Should return 404, not the notification
        self.assertEqual(resp.status_code, 404)

    def test_chef_cannot_mark_other_chef_notification_read(self):
        """A chef should not be able to mark another chef's notification as read."""
        notification = ChefNotification.objects.create(
            chef=self.other_chef,
            notification_type='welcome',
            title='Welcome',
            message='Hello other chef',
        )

        self._authenticate(self.chef_user)
        url = reverse('chefs:chef_notification_read', kwargs={'notification_id': notification.id})
        resp = self.client.post(url)

        # Should return 404
        self.assertEqual(resp.status_code, 404)

        # Notification should remain unread
        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_PENDING)


# =============================================================================
# ONBOARDING API TESTS
# =============================================================================


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class OnboardingApiTests(TestCase):
    """Tests for onboarding API endpoints."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chef_onboarding",
            email="chef_onboarding@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

    def test_get_creates_onboarding_state_with_defaults(self):
        """GET should create onboarding state with defaults if it doesn't exist."""
        self.assertFalse(ChefOnboardingState.objects.filter(chef=self.chef).exists())

        url = reverse('chefs:chef_onboarding')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertTrue(ChefOnboardingState.objects.filter(chef=self.chef).exists())

        # Check defaults
        onboarding = resp.data['onboarding']
        self.assertFalse(onboarding['welcomed'])
        self.assertFalse(onboarding['setup_started'])
        self.assertFalse(onboarding['setup_completed'])
        self.assertFalse(onboarding['setup_skipped'])
        self.assertFalse(onboarding['first_dish_added'])
        self.assertEqual(onboarding['tips_shown'], [])
        self.assertEqual(onboarding['tips_dismissed'], [])

    def test_get_returns_existing_onboarding_state(self):
        """GET should return existing onboarding state without modification."""
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            welcomed=True,
            setup_started=True,
            first_dish_added=True,
            tips_shown=['tip_1', 'tip_2'],
        )

        url = reverse('chefs:chef_onboarding')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['welcomed'])
        self.assertTrue(onboarding['setup_started'])
        self.assertTrue(onboarding['first_dish_added'])
        self.assertEqual(onboarding['tips_shown'], ['tip_1', 'tip_2'])

    def test_welcomed_marks_welcomed_and_sets_timestamp(self):
        """POST welcomed should mark welcomed and set timestamp."""
        url = reverse('chefs:chef_onboarding_welcomed')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['welcomed'])
        self.assertIsNotNone(onboarding['welcomed_at'])

        # Verify in database
        state = ChefOnboardingState.objects.get(chef=self.chef)
        self.assertTrue(state.welcomed)
        self.assertIsNotNone(state.welcomed_at)

    def test_welcomed_is_idempotent(self):
        """POST welcomed multiple times should not change timestamp."""
        url = reverse('chefs:chef_onboarding_welcomed')

        # First call
        resp1 = self.client.post(url)
        timestamp1 = resp1.data['onboarding']['welcomed_at']

        # Second call
        resp2 = self.client.post(url)
        timestamp2 = resp2.data['onboarding']['welcomed_at']

        # Timestamps should be identical
        self.assertEqual(timestamp1, timestamp2)

    def test_start_marks_setup_started_and_welcomed(self):
        """POST start should mark setup started and also welcomed."""
        url = reverse('chefs:chef_onboarding_start')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['welcomed'])
        self.assertTrue(onboarding['setup_started'])
        self.assertIsNotNone(onboarding['setup_started_at'])

    def test_complete_marks_setup_completed_and_clears_skipped(self):
        """POST complete should mark setup completed and clear skipped."""
        # First skip
        state = ChefOnboardingState.objects.create(
            chef=self.chef,
            setup_skipped=True,
        )

        url = reverse('chefs:chef_onboarding_complete')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['setup_completed'])
        self.assertFalse(onboarding['setup_skipped'])  # Skipped should be cleared

    def test_complete_accepts_personality_choice(self):
        """POST complete can accept personality_choice in request body."""
        url = reverse('chefs:chef_onboarding_complete')
        resp = self.client.post(url, {'personality_choice': 'friendly'}, format='json')

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['personality_set'])
        self.assertEqual(onboarding['personality_choice'], 'friendly')

    def test_skip_marks_skipped_if_not_completed(self):
        """POST skip should mark skipped only if not already completed."""
        url = reverse('chefs:chef_onboarding_skip')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertTrue(onboarding['setup_skipped'])
        self.assertTrue(onboarding['welcomed'])  # Also marks welcomed

    def test_skip_does_not_mark_if_already_completed(self):
        """POST skip should not mark skipped if already completed."""
        ChefOnboardingState.objects.create(
            chef=self.chef,
            setup_completed=True,
        )

        url = reverse('chefs:chef_onboarding_skip')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        onboarding = resp.data['onboarding']
        self.assertFalse(onboarding['setup_skipped'])  # Should remain false

    def test_milestone_records_valid_milestone(self):
        """POST milestone should record a valid milestone."""
        url = reverse('chefs:chef_onboarding_milestone')
        resp = self.client.post(url, {'milestone': 'first_dish'}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['milestone'], 'first_dish')
        self.assertTrue(resp.data['newly_recorded'])
        self.assertTrue(resp.data['onboarding']['first_dish_added'])

    def test_milestone_rejects_invalid_milestone(self):
        """POST milestone should reject invalid milestone names."""
        url = reverse('chefs:chef_onboarding_milestone')
        resp = self.client.post(url, {'milestone': 'invalid_milestone'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_milestone_requires_milestone_field(self):
        """POST milestone should require milestone field."""
        url = reverse('chefs:chef_onboarding_milestone')
        resp = self.client.post(url, {}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_milestone_is_idempotent(self):
        """POST milestone is idempotent (second call returns newly_recorded=False)."""
        url = reverse('chefs:chef_onboarding_milestone')

        # First call
        resp1 = self.client.post(url, {'milestone': 'first_dish'}, format='json')
        self.assertTrue(resp1.data['newly_recorded'])

        # Second call
        resp2 = self.client.post(url, {'milestone': 'first_dish'}, format='json')
        self.assertFalse(resp2.data['newly_recorded'])

    def test_tip_show_adds_to_tips_shown_list(self):
        """POST tip/show should add tip_id to tips_shown list."""
        url = reverse('chefs:chef_onboarding_tip_show')
        resp = self.client.post(url, {'tip_id': 'add_first_dish'}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['tip_id'], 'add_first_dish')
        self.assertIn('add_first_dish', resp.data['tips_shown'])

    def test_tip_show_requires_tip_id(self):
        """POST tip/show should require tip_id field."""
        url = reverse('chefs:chef_onboarding_tip_show')
        resp = self.client.post(url, {}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_tip_dismiss_adds_to_tips_dismissed_list(self):
        """POST tip/dismiss should add tip_id to tips_dismissed list."""
        url = reverse('chefs:chef_onboarding_tip_dismiss')
        resp = self.client.post(url, {'tip_id': 'add_first_dish'}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['tip_id'], 'add_first_dish')
        self.assertIn('add_first_dish', resp.data['tips_dismissed'])

    def test_tip_dismiss_requires_tip_id(self):
        """POST tip/dismiss should require tip_id field."""
        url = reverse('chefs:chef_onboarding_tip_dismiss')
        resp = self.client.post(url, {}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_personality_updates_workspace_soul_prompt(self):
        """POST personality should update workspace soul_prompt."""
        from chefs.models import ChefWorkspace

        url = reverse('chefs:chef_onboarding_personality')
        resp = self.client.post(url, {'personality': 'friendly'}, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['personality'], 'friendly')
        self.assertTrue(resp.data['onboarding']['personality_set'])

        # Verify workspace was updated
        workspace = ChefWorkspace.objects.get(chef=self.chef)
        self.assertIn('warm', workspace.soul_prompt.lower())

    def test_personality_rejects_invalid_personality(self):
        """POST personality should reject invalid personality names."""
        url = reverse('chefs:chef_onboarding_personality')
        resp = self.client.post(url, {'personality': 'invalid'}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_personality_requires_personality_field(self):
        """POST personality should require personality field."""
        url = reverse('chefs:chef_onboarding_personality')
        resp = self.client.post(url, {}, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)


# =============================================================================
# PROACTIVE SETTINGS API TESTS
# =============================================================================


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class ProactiveSettingsApiTests(TestCase):
    """Tests for proactive settings API endpoints."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chef_proactive_settings",
            email="chef_proactive_settings@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

    def test_get_creates_settings_with_defaults(self):
        """GET should create proactive settings with defaults if it doesn't exist."""
        self.assertFalse(ChefProactiveSettings.objects.filter(chef=self.chef).exists())

        url = reverse('chefs:chef_proactive')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertTrue(ChefProactiveSettings.objects.filter(chef=self.chef).exists())

        # Check defaults - master switch OFF
        settings = resp.data['settings']
        self.assertFalse(settings['enabled'])
        self.assertTrue(settings['notify_birthdays'])
        self.assertTrue(settings['notify_followups'])
        self.assertEqual(settings['notification_frequency'], 'daily')
        self.assertTrue(settings['channel_in_app'])
        self.assertFalse(settings['channel_email'])

    def test_get_returns_existing_settings(self):
        """GET should return existing proactive settings."""
        ChefProactiveSettings.objects.create(
            chef=self.chef,
            enabled=True,
            notify_birthdays=False,
            notification_frequency='weekly',
        )

        url = reverse('chefs:chef_proactive')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        settings = resp.data['settings']
        self.assertTrue(settings['enabled'])
        self.assertFalse(settings['notify_birthdays'])
        self.assertEqual(settings['notification_frequency'], 'weekly')

    def test_update_boolean_fields(self):
        """PATCH should update boolean fields."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'enabled': True,
            'notify_birthdays': False,
            'channel_email': True,
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        settings = resp.data['settings']
        self.assertTrue(settings['enabled'])
        self.assertFalse(settings['notify_birthdays'])
        self.assertTrue(settings['channel_email'])

    def test_update_integer_fields(self):
        """PATCH should update integer fields."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'birthday_lead_days': 14,
            'followup_threshold_days': 60,
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        settings = resp.data['settings']
        self.assertEqual(settings['birthday_lead_days'], 14)
        self.assertEqual(settings['followup_threshold_days'], 60)

    def test_update_rejects_invalid_integer(self):
        """PATCH should reject invalid integer values."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'birthday_lead_days': 'not_a_number',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_update_notification_frequency(self):
        """PATCH should update notification_frequency with valid value."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'notification_frequency': 'weekly',
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['settings']['notification_frequency'], 'weekly')

    def test_update_rejects_invalid_frequency(self):
        """PATCH should reject invalid notification_frequency."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'notification_frequency': 'invalid',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_update_quiet_hours_time_fields(self):
        """PATCH should update quiet hours time fields."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'quiet_hours_enabled': True,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00',
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        settings = resp.data['settings']
        self.assertTrue(settings['quiet_hours_enabled'])
        self.assertEqual(settings['quiet_hours_start'], '22:00')
        self.assertEqual(settings['quiet_hours_end'], '08:00')

    def test_update_rejects_invalid_time_format(self):
        """PATCH should reject invalid time format."""
        ChefProactiveSettings.objects.create(chef=self.chef)

        url = reverse('chefs:chef_proactive_update')
        resp = self.client.patch(url, {
            'quiet_hours_start': 'invalid',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_enable_sets_enabled_true_and_records_milestone(self):
        """POST enable should set enabled=True and record milestone."""
        ChefProactiveSettings.objects.create(chef=self.chef, enabled=False)

        url = reverse('chefs:chef_proactive_enable')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['settings']['enabled'])

        # Verify milestone was recorded
        state = ChefOnboardingState.objects.get(chef=self.chef)
        self.assertTrue(state.proactive_enabled)

    def test_enable_is_idempotent(self):
        """POST enable should be idempotent."""
        ChefProactiveSettings.objects.create(chef=self.chef, enabled=True)
        ChefOnboardingState.objects.create(chef=self.chef, proactive_enabled=True)

        url = reverse('chefs:chef_proactive_enable')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['settings']['enabled'])

    def test_disable_sets_enabled_false(self):
        """POST disable should set enabled=False."""
        ChefProactiveSettings.objects.create(chef=self.chef, enabled=True)

        url = reverse('chefs:chef_proactive_disable')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['settings']['enabled'])

    def test_disable_preserves_other_settings(self):
        """POST disable should preserve other settings."""
        ChefProactiveSettings.objects.create(
            chef=self.chef,
            enabled=True,
            notify_birthdays=False,
            notification_frequency='weekly',
        )

        url = reverse('chefs:chef_proactive_disable')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        settings = resp.data['settings']
        self.assertFalse(settings['enabled'])
        self.assertFalse(settings['notify_birthdays'])  # Preserved
        self.assertEqual(settings['notification_frequency'], 'weekly')  # Preserved


# =============================================================================
# NOTIFICATIONS API TESTS
# =============================================================================


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class NotificationsApiTests(TestCase):
    """Tests for notifications API endpoints."""

    def setUp(self):
        self.client = APIClient()

        self.chef_user = CustomUser.objects.create_user(
            username="chef_notifications",
            email="chef_notifications@example.com",
            password="testpass123",
        )
        self.chef = Chef.objects.create(user=self.chef_user, bio="Test chef")
        self.client.force_authenticate(user=self.chef_user)

    def _create_notification(self, **kwargs):
        """Helper to create a notification for the test chef."""
        defaults = {
            'chef': self.chef,
            'notification_type': 'system',
            'title': 'Test notification',
            'message': 'Test message',
        }
        defaults.update(kwargs)
        return ChefNotification.objects.create(**defaults)

    def test_list_returns_notifications(self):
        """GET should return list of notifications."""
        self._create_notification(title='First')
        self._create_notification(title='Second')

        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'success')
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual(len(resp.data['notifications']), 2)

    def test_list_supports_status_filter(self):
        """GET should filter by status."""
        self._create_notification(title='Pending', status=ChefNotification.STATUS_PENDING)
        self._create_notification(title='Read', status=ChefNotification.STATUS_READ)

        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url, {'status': 'pending'})

        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['notifications'][0]['title'], 'Pending')

    def test_list_supports_type_filter(self):
        """GET should filter by notification type."""
        self._create_notification(title='Birthday', notification_type='birthday')
        self._create_notification(title='Todo', notification_type='todo')

        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url, {'type': 'birthday'})

        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['notifications'][0]['title'], 'Birthday')

    def test_list_supports_unread_only_filter(self):
        """GET with unread_only=true should filter to pending/sent only."""
        self._create_notification(title='Pending', status=ChefNotification.STATUS_PENDING)
        self._create_notification(title='Read', status=ChefNotification.STATUS_READ)
        self._create_notification(title='Dismissed', status=ChefNotification.STATUS_DISMISSED)

        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url, {'unread_only': 'true'})

        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['notifications'][0]['title'], 'Pending')

    def test_list_supports_pagination(self):
        """GET should support limit and offset pagination."""
        for i in range(5):
            self._create_notification(title=f'Notification {i}')

        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url, {'limit': 2, 'offset': 1})

        self.assertEqual(resp.data['total'], 5)
        self.assertEqual(resp.data['limit'], 2)
        self.assertEqual(resp.data['offset'], 1)
        self.assertEqual(len(resp.data['notifications']), 2)

    def test_list_enforces_max_limit(self):
        """GET should enforce maximum limit of 100."""
        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url, {'limit': 200})

        self.assertEqual(resp.data['limit'], 100)

    def test_unread_count_returns_correct_count(self):
        """GET unread-count should return count of pending/sent notifications."""
        self._create_notification(status=ChefNotification.STATUS_PENDING)
        self._create_notification(status=ChefNotification.STATUS_SENT)
        self._create_notification(status=ChefNotification.STATUS_READ)
        self._create_notification(status=ChefNotification.STATUS_DISMISSED)

        url = reverse('chefs:chef_notifications_unread_count')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['unread_count'], 2)

    def test_detail_returns_notification(self):
        """GET detail should return notification details."""
        notification = self._create_notification(
            title='Test',
            message='Test message',
            action_context={'prePrompt': 'Hello'},
        )

        url = reverse('chefs:chef_notification_detail', kwargs={'notification_id': notification.id})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['notification']['title'], 'Test')
        self.assertEqual(resp.data['notification']['message'], 'Test message')
        self.assertEqual(resp.data['notification']['action_context'], {'prePrompt': 'Hello'})

    def test_detail_returns_404_for_nonexistent(self):
        """GET detail should return 404 for nonexistent notification."""
        url = reverse('chefs:chef_notification_detail', kwargs={'notification_id': 99999})
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 404)

    def test_mark_read_updates_status_and_timestamp(self):
        """POST read should mark notification as read."""
        notification = self._create_notification(status=ChefNotification.STATUS_PENDING)

        url = reverse('chefs:chef_notification_read', kwargs={'notification_id': notification.id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['notification']['status'], 'read')
        self.assertIsNotNone(resp.data['notification']['read_at'])

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_READ)

    def test_mark_read_does_not_update_dismissed(self):
        """POST read should not update already dismissed notification."""
        notification = self._create_notification(status=ChefNotification.STATUS_DISMISSED)

        url = reverse('chefs:chef_notification_read', kwargs={'notification_id': notification.id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_DISMISSED)

    def test_dismiss_marks_notification_dismissed(self):
        """POST dismiss should mark notification as dismissed."""
        notification = self._create_notification()

        url = reverse('chefs:chef_notification_dismiss', kwargs={'notification_id': notification.id})
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['notification']['status'], 'dismissed')

        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_DISMISSED)

    # Note: DELETE endpoint is not currently exposed via URLs
    # The notification_delete function exists but is not routed
    # These tests are skipped until the endpoint is exposed

    def test_detail_endpoint_does_not_accept_delete(self):
        """GET detail endpoint should not accept DELETE method."""
        notification = self._create_notification()
        url = reverse('chefs:chef_notification_detail', kwargs={'notification_id': notification.id})
        resp = self.client.delete(url)

        # Should return 405 Method Not Allowed
        self.assertEqual(resp.status_code, 405)

    def test_mark_all_read_updates_all_unread(self):
        """POST mark-all-read should mark all pending/sent as read."""
        self._create_notification(status=ChefNotification.STATUS_PENDING)
        self._create_notification(status=ChefNotification.STATUS_SENT)
        self._create_notification(status=ChefNotification.STATUS_DISMISSED)

        url = reverse('chefs:chef_notifications_mark_all_read')
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['marked_count'], 2)

        # Verify all are now read
        pending_count = ChefNotification.objects.filter(
            chef=self.chef,
            status__in=[ChefNotification.STATUS_PENDING, ChefNotification.STATUS_SENT]
        ).count()
        self.assertEqual(pending_count, 0)


# =============================================================================
# DATA ISOLATION TESTS
# =============================================================================


@override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
)
class ProactiveDataIsolationTests(TestCase):
    """Tests for data isolation between chefs."""

    def setUp(self):
        self.client = APIClient()

        # Create two chefs
        self.chef_user_1 = CustomUser.objects.create_user(
            username="chef_iso_1",
            email="chef_iso_1@example.com",
            password="testpass123",
        )
        self.chef_1 = Chef.objects.create(user=self.chef_user_1)

        self.chef_user_2 = CustomUser.objects.create_user(
            username="chef_iso_2",
            email="chef_iso_2@example.com",
            password="testpass123",
        )
        self.chef_2 = Chef.objects.create(user=self.chef_user_2)

    def test_onboarding_state_isolation(self):
        """Each chef has their own onboarding state."""
        # Create state for chef 1
        ChefOnboardingState.objects.create(
            chef=self.chef_1,
            welcomed=True,
            first_dish_added=True,
        )

        # Chef 2 accesses their onboarding
        self.client.force_authenticate(user=self.chef_user_2)
        url = reverse('chefs:chef_onboarding')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        # Should get their own (newly created) state, not chef 1's
        self.assertFalse(resp.data['onboarding']['welcomed'])
        self.assertFalse(resp.data['onboarding']['first_dish_added'])

    def test_proactive_settings_isolation(self):
        """Each chef has their own proactive settings."""
        # Create settings for chef 1
        ChefProactiveSettings.objects.create(
            chef=self.chef_1,
            enabled=True,
            notify_birthdays=False,
        )

        # Chef 2 accesses their settings
        self.client.force_authenticate(user=self.chef_user_2)
        url = reverse('chefs:chef_proactive')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        # Should get their own (newly created) settings with defaults
        self.assertFalse(resp.data['settings']['enabled'])
        self.assertTrue(resp.data['settings']['notify_birthdays'])

    def test_notifications_isolation(self):
        """Each chef only sees their own notifications."""
        # Create notifications for chef 1
        ChefNotification.objects.create(
            chef=self.chef_1,
            notification_type='welcome',
            title='Welcome Chef 1',
            message='Hello Chef 1',
        )
        ChefNotification.objects.create(
            chef=self.chef_1,
            notification_type='birthday',
            title='Birthday reminder',
            message='Birthday coming up',
        )

        # Chef 2 accesses notifications
        self.client.force_authenticate(user=self.chef_user_2)
        url = reverse('chefs:chef_notifications')
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 0)  # Should see no notifications

    def test_notification_update_isolation(self):
        """Chef cannot modify another chef's notification."""
        # Create notification for chef 1
        notification = ChefNotification.objects.create(
            chef=self.chef_1,
            notification_type='welcome',
            title='Welcome',
            message='Hello',
        )

        # Chef 2 tries to mark it as read
        self.client.force_authenticate(user=self.chef_user_2)
        url = reverse('chefs:chef_notification_read', kwargs={'notification_id': notification.id})
        resp = self.client.post(url)

        # Should return 404
        self.assertEqual(resp.status_code, 404)

        # Notification should remain unchanged
        notification.refresh_from_db()
        self.assertEqual(notification.status, ChefNotification.STATUS_PENDING)

    def test_notification_detail_isolation(self):
        """Chef cannot view another chef's notification details."""
        # Create notification for chef 1
        notification = ChefNotification.objects.create(
            chef=self.chef_1,
            notification_type='welcome',
            title='Welcome',
            message='Hello',
        )

        # Chef 2 tries to view it
        self.client.force_authenticate(user=self.chef_user_2)
        url = reverse('chefs:chef_notification_detail', kwargs={'notification_id': notification.id})
        resp = self.client.get(url)

        # Should return 404
        self.assertEqual(resp.status_code, 404)
