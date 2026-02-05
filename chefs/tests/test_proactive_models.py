# chefs/tests/test_proactive_models.py
"""
TDD tests for proactive notification models.

Tests ChefProactiveSettings, ChefOnboardingState, and ChefNotification.
"""

import pytest
from datetime import time, timedelta
from unittest.mock import patch
from django.utils import timezone


@pytest.mark.django_db
class TestChefProactiveSettings:
    """Tests for ChefProactiveSettings model."""
    
    def test_master_switch_off_by_default(self, chef):
        """Master switch (enabled) should be OFF by default."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        assert settings.enabled is False
    
    def test_notification_toggles_default_to_true(self, chef):
        """Individual notification toggles default to True (but master is off)."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        # Individual toggles are True by default (but master switch is off)
        assert settings.notify_birthdays is True
        assert settings.notify_anniversaries is True
        assert settings.notify_followups is True
        assert settings.notify_todos is True
        assert settings.notify_seasonal is True
        assert settings.notify_milestones is True
    
    def test_channel_defaults(self, chef):
        """In-app should be default channel, others off."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        assert settings.channel_in_app is True
        assert settings.channel_email is False
        assert settings.channel_push is False
    
    def test_default_thresholds(self, chef):
        """Default lead days and followup threshold."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        assert settings.birthday_lead_days == 7
        assert settings.anniversary_lead_days == 7
        assert settings.followup_threshold_days == 30
    
    def test_default_frequency_is_daily(self, chef):
        """Default frequency should be daily."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        assert settings.notification_frequency == 'daily'
    
    def test_str_representation_disabled(self, chef):
        """String shows disabled status."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(chef=chef)
        
        assert "disabled" in str(settings)
        assert str(chef.id) in str(settings)
    
    def test_str_representation_enabled(self, chef):
        """String shows enabled status when master switch is on."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            enabled=True
        )
        
        assert "enabled" in str(settings)
    
    def test_is_within_quiet_hours_disabled(self, chef):
        """Returns False when quiet hours disabled."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=False
        )
        
        assert settings.is_within_quiet_hours() is False
    
    def test_is_within_quiet_hours_no_times_set(self, chef):
        """Returns False when quiet hours enabled but times not set."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=None,
            quiet_hours_end=None
        )
        
        assert settings.is_within_quiet_hours() is False
    
    def test_is_within_quiet_hours_daytime_range_inside(self, chef):
        """Returns True when within daytime quiet hours."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=time(10, 0),
            quiet_hours_end=time(14, 0),
            quiet_hours_timezone='UTC'
        )
        
        # Mock time to 12:00 UTC (within 10:00-14:00)
        mock_now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=mock_now):
            assert settings.is_within_quiet_hours() is True
    
    def test_is_within_quiet_hours_daytime_range_outside(self, chef):
        """Returns False when outside daytime quiet hours."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=time(10, 0),
            quiet_hours_end=time(14, 0),
            quiet_hours_timezone='UTC'
        )
        
        # Mock time to 16:00 UTC (outside 10:00-14:00)
        mock_now = timezone.now().replace(hour=16, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=mock_now):
            assert settings.is_within_quiet_hours() is False
    
    def test_is_within_quiet_hours_overnight_inside_evening(self, chef):
        """Returns True when within overnight quiet hours (evening side)."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(8, 0),
            quiet_hours_timezone='UTC'
        )
        
        # Mock time to 23:00 UTC (within 22:00-08:00)
        mock_now = timezone.now().replace(hour=23, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=mock_now):
            assert settings.is_within_quiet_hours() is True
    
    def test_is_within_quiet_hours_overnight_inside_morning(self, chef):
        """Returns True when within overnight quiet hours (morning side)."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(8, 0),
            quiet_hours_timezone='UTC'
        )
        
        # Mock time to 06:00 UTC (within 22:00-08:00)
        mock_now = timezone.now().replace(hour=6, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=mock_now):
            assert settings.is_within_quiet_hours() is True
    
    def test_is_within_quiet_hours_overnight_outside(self, chef):
        """Returns False when outside overnight quiet hours."""
        from chefs.models import ChefProactiveSettings
        
        settings = ChefProactiveSettings.objects.create(
            chef=chef,
            quiet_hours_enabled=True,
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(8, 0),
            quiet_hours_timezone='UTC'
        )
        
        # Mock time to 14:00 UTC (outside 22:00-08:00)
        mock_now = timezone.now().replace(hour=14, minute=0, second=0, microsecond=0)
        with patch('django.utils.timezone.now', return_value=mock_now):
            assert settings.is_within_quiet_hours() is False
    
    def test_get_or_create_for_chef_creates(self, chef):
        """Creates settings when none exist."""
        from chefs.models import ChefProactiveSettings
        
        assert not ChefProactiveSettings.objects.filter(chef=chef).exists()
        
        settings = ChefProactiveSettings.get_or_create_for_chef(chef)
        
        assert settings.chef == chef
        assert settings.enabled is False  # Master switch off
        assert ChefProactiveSettings.objects.filter(chef=chef).exists()
    
    def test_get_or_create_for_chef_returns_existing(self, chef):
        """Returns existing settings without creating new."""
        from chefs.models import ChefProactiveSettings
        
        existing = ChefProactiveSettings.objects.create(
            chef=chef,
            enabled=True,
            notification_frequency='weekly'
        )
        
        settings = ChefProactiveSettings.get_or_create_for_chef(chef)
        
        assert settings.id == existing.id
        assert settings.enabled is True


@pytest.mark.django_db
class TestChefOnboardingState:
    """Tests for ChefOnboardingState model."""
    
    def test_defaults(self, chef):
        """Onboarding state should start fresh."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert state.welcomed is False
        assert state.welcomed_at is None
        assert state.setup_started is False
        assert state.setup_completed is False
        assert state.setup_skipped is False
        assert state.personality_set is False
        assert state.personality_choice == ''
    
    def test_milestone_defaults(self, chef):
        """Feature milestones should start as False."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert state.first_dish_added is False
        assert state.first_dish_added_at is None
        assert state.first_client_added is False
        assert state.first_conversation is False
        assert state.first_memory_saved is False
        assert state.first_order_completed is False
    
    def test_tips_defaults(self, chef):
        """Tips tracking should start empty."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert state.tips_shown == []
        assert state.tips_dismissed == []
    
    def test_str_completed(self, chef):
        """String shows completed status."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(
            chef=chef,
            setup_completed=True
        )
        
        assert "completed" in str(state)
    
    def test_str_in_progress(self, chef):
        """String shows in progress status."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert "in progress" in str(state)
    
    def test_mark_welcomed(self, chef):
        """mark_welcomed sets flag and timestamp."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert state.welcomed is False
        
        state.mark_welcomed()
        state.refresh_from_db()
        
        assert state.welcomed is True
        assert state.welcomed_at is not None
    
    def test_mark_welcomed_idempotent(self, chef):
        """Calling mark_welcomed twice doesn't change timestamp."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        state.mark_welcomed()
        state.refresh_from_db()
        
        original_timestamp = state.welcomed_at
        
        state.mark_welcomed()
        state.refresh_from_db()
        
        assert state.welcomed_at == original_timestamp
    
    def test_mark_setup_started(self, chef):
        """mark_setup_started sets flag and timestamp."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        state.mark_setup_started()
        state.refresh_from_db()
        
        assert state.setup_started is True
        assert state.setup_started_at is not None
    
    def test_mark_setup_completed(self, chef):
        """mark_setup_completed sets flag and clears skipped."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef, setup_skipped=True)
        state.mark_setup_completed()
        state.refresh_from_db()
        
        assert state.setup_completed is True
        assert state.setup_completed_at is not None
        assert state.setup_skipped is False  # Cleared
    
    def test_mark_setup_skipped(self, chef):
        """mark_setup_skipped sets flag."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        state.mark_setup_skipped()
        state.refresh_from_db()
        
        assert state.setup_skipped is True
        assert state.setup_skipped_at is not None
    
    def test_mark_setup_skipped_not_if_completed(self, chef):
        """Cannot skip if already completed."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef, setup_completed=True)
        state.mark_setup_skipped()
        state.refresh_from_db()
        
        assert state.setup_skipped is False  # Should not change
    
    def test_record_milestone_first_dish(self, chef):
        """record_milestone sets first_dish milestone."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        result = state.record_milestone('first_dish')
        state.refresh_from_db()
        
        assert result is True
        assert state.first_dish_added is True
        assert state.first_dish_added_at is not None
    
    def test_record_milestone_idempotent(self, chef):
        """Recording same milestone twice returns False."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        state.record_milestone('first_client')
        state.refresh_from_db()
        
        original_timestamp = state.first_client_added_at
        
        result = state.record_milestone('first_client')
        state.refresh_from_db()
        
        assert result is False
        assert state.first_client_added_at == original_timestamp
    
    def test_record_milestone_invalid(self, chef):
        """Invalid milestone name returns False."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        result = state.record_milestone('invalid_milestone')
        
        assert result is False
    
    def test_show_tip_records_in_list(self, chef):
        """show_tip adds tip to tips_shown list."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        state.show_tip('add_first_dish')
        state.refresh_from_db()
        
        assert 'add_first_dish' in state.tips_shown
    
    def test_dismiss_tip_records_in_list(self, chef):
        """dismiss_tip adds tip to tips_dismissed list."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        state.dismiss_tip('annoying_tip')
        state.refresh_from_db()
        
        assert 'annoying_tip' in state.tips_dismissed
    
    def test_should_show_tip_true_when_not_dismissed(self, chef):
        """should_show_tip returns True when tip not dismissed."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(chef=chef)
        
        assert state.should_show_tip('new_tip') is True
    
    def test_should_show_tip_false_when_dismissed(self, chef):
        """should_show_tip returns False when tip is dismissed."""
        from chefs.models import ChefOnboardingState
        
        state = ChefOnboardingState.objects.create(
            chef=chef,
            tips_dismissed=['dismissed_tip']
        )
        
        assert state.should_show_tip('dismissed_tip') is False
    
    def test_get_or_create_for_chef_creates(self, chef):
        """Creates state when none exists."""
        from chefs.models import ChefOnboardingState
        
        assert not ChefOnboardingState.objects.filter(chef=chef).exists()
        
        state = ChefOnboardingState.get_or_create_for_chef(chef)
        
        assert state.chef == chef
        assert ChefOnboardingState.objects.filter(chef=chef).exists()
    
    def test_get_or_create_for_chef_returns_existing(self, chef):
        """Returns existing state."""
        from chefs.models import ChefOnboardingState
        
        existing = ChefOnboardingState.objects.create(
            chef=chef,
            welcomed=True,
            setup_started=True
        )
        
        state = ChefOnboardingState.get_or_create_for_chef(chef)
        
        assert state.id == existing.id
        assert state.welcomed is True


@pytest.mark.django_db
class TestChefNotification:
    """Tests for ChefNotification model."""
    
    def test_creation_defaults(self, chef):
        """Notification created with correct defaults."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Test Title',
            message='Test message'
        )
        
        assert notification.status == ChefNotification.STATUS_PENDING
        assert notification.sent_in_app is False
        assert notification.sent_email is False
        assert notification.sent_push is False
        assert notification.sent_at is None
        assert notification.read_at is None
        assert notification.dismissed_at is None
        assert notification.action_context == {}
    
    def test_str_representation(self, chef):
        """String shows type and title."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Birthday reminder',
            message='Test message'
        )
        
        str_repr = str(notification)
        assert 'birthday' in str_repr
        assert 'Birthday reminder' in str_repr
    
    def test_mark_sent_in_app(self, chef):
        """mark_sent with in_app channel updates correctly."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_FOLLOWUP,
            title='Test',
            message='Test'
        )
        
        notification.mark_sent('in_app')
        notification.refresh_from_db()
        
        assert notification.status == ChefNotification.STATUS_SENT
        assert notification.sent_at is not None
        assert notification.sent_in_app is True
        assert notification.sent_email is False
    
    def test_mark_sent_email(self, chef):
        """mark_sent with email channel."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_TODO,
            title='Test',
            message='Test'
        )
        
        notification.mark_sent('email')
        notification.refresh_from_db()
        
        assert notification.sent_email is True
        assert notification.sent_in_app is False
    
    def test_mark_read(self, chef):
        """mark_read updates status and timestamp."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_MILESTONE,
            title='Test',
            message='Test',
            status=ChefNotification.STATUS_SENT
        )
        
        notification.mark_read()
        notification.refresh_from_db()
        
        assert notification.status == ChefNotification.STATUS_READ
        assert notification.read_at is not None
    
    def test_mark_dismissed(self, chef):
        """mark_dismissed updates status and timestamp."""
        from chefs.models import ChefNotification
        
        notification = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_SEASONAL,
            title='Test',
            message='Test'
        )
        
        notification.mark_dismissed()
        notification.refresh_from_db()
        
        assert notification.status == ChefNotification.STATUS_DISMISSED
        assert notification.dismissed_at is not None
    
    def test_create_notification_with_dedup(self, chef):
        """create_notification respects deduplication."""
        from chefs.models import ChefNotification
        
        # Create first notification
        notif1 = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Test',
            message='Test',
            dedup_key='unique_key_123'
        )
        
        # Create second with same dedup key
        notif2 = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Different',
            message='Different',
            dedup_key='unique_key_123'
        )
        
        # Should return existing notification
        assert notif2.id == notif1.id
    
    def test_create_notification_dedup_only_recent(self, chef):
        """Deduplication only checks notifications from last 7 days."""
        from chefs.models import ChefNotification
        
        # Create old notification
        old_notif = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Old',
            message='Old',
            dedup_key='unique_key_456'
        )
        # Backdate it
        old_notif.created_at = timezone.now() - timedelta(days=10)
        old_notif.save()
        
        # Create new with same dedup key
        new_notif = ChefNotification.create_notification(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='New',
            message='New',
            dedup_key='unique_key_456'
        )
        
        # Should create new notification (old one is too old)
        assert new_notif.id != old_notif.id
    
    def test_get_unread_count(self, chef):
        """get_unread_count returns correct count."""
        from chefs.models import ChefNotification
        
        # Create mix of notifications
        ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Pending',
            message='Test',
            status=ChefNotification.STATUS_PENDING
        )
        ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_FOLLOWUP,
            title='Sent',
            message='Test',
            status=ChefNotification.STATUS_SENT
        )
        ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_TODO,
            title='Read',
            message='Test',
            status=ChefNotification.STATUS_READ
        )
        ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_MILESTONE,
            title='Dismissed',
            message='Test',
            status=ChefNotification.STATUS_DISMISSED
        )
        
        count = ChefNotification.get_unread_count(chef)
        
        # Only pending and sent count as unread
        assert count == 2
    
    def test_get_pending_for_chef(self, chef):
        """get_pending_for_chef returns correct notifications."""
        from chefs.models import ChefNotification
        
        # Create notifications
        pending = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='Pending',
            message='Test',
            status=ChefNotification.STATUS_PENDING
        )
        sent = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_FOLLOWUP,
            title='Sent',
            message='Test',
            status=ChefNotification.STATUS_SENT
        )
        read = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_TODO,
            title='Read',
            message='Test',
            status=ChefNotification.STATUS_READ
        )
        
        result = list(ChefNotification.get_pending_for_chef(chef))
        
        assert len(result) == 2
        assert pending in result
        assert sent in result
        assert read not in result
    
    def test_ordering_newest_first(self, chef):
        """Notifications ordered by created_at descending."""
        from chefs.models import ChefNotification
        import time
        
        n1 = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY,
            title='First',
            message='Test'
        )
        
        time.sleep(0.01)  # Ensure different timestamps
        
        n2 = ChefNotification.objects.create(
            chef=chef,
            notification_type=ChefNotification.TYPE_FOLLOWUP,
            title='Second',
            message='Test'
        )
        
        notifications = list(ChefNotification.objects.filter(chef=chef))
        
        assert notifications[0].id == n2.id  # Newest first
        assert notifications[1].id == n1.id
