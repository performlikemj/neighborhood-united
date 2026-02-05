# chefs/tests/test_proactive_engine.py
"""
TDD tests for proactive engine Celery tasks.

Tests the notification generation logic for:
- Special occasions (birthdays, anniversaries)
- Follow-up suggestions
- Todo reminders
- Milestones
- Seasonal suggestions
- Welcome notifications
"""

import pytest
from datetime import time, timedelta, date
from unittest.mock import patch, MagicMock
from django.utils import timezone


@pytest.mark.django_db
class TestShouldRunForFrequency:
    """Tests for should_run_for_frequency helper."""
    
    def test_realtime_always_runs(self, chef, proactive_settings):
        """Realtime frequency always returns True."""
        from chefs.tasks.proactive_engine import should_run_for_frequency
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_REALTIME
        proactive_settings.save()
        
        assert should_run_for_frequency(proactive_settings) is True
    
    def test_daily_no_prior_notification(self, chef, proactive_settings):
        """Daily runs when no prior notification."""
        from chefs.tasks.proactive_engine import should_run_for_frequency
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_DAILY
        proactive_settings.save()
        
        assert should_run_for_frequency(proactive_settings) is True
    
    def test_weekly_no_prior_notification(self, chef, proactive_settings):
        """Weekly runs when no prior notification."""
        from chefs.tasks.proactive_engine import should_run_for_frequency
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_WEEKLY
        proactive_settings.save()
        
        assert should_run_for_frequency(proactive_settings) is True


@pytest.mark.django_db
class TestGenerateInsightsForChef:
    """Tests for generate_insights_for_chef."""
    
    def test_calls_birthday_check_when_enabled(self, chef, proactive_settings):
        """Birthday check called when notify_birthdays enabled."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        proactive_settings.notify_birthdays = True
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.check_special_occasions', return_value=[]) as mock:
            generate_insights_for_chef(proactive_settings)
            mock.assert_called_once_with(proactive_settings)
    
    def test_calls_followups_when_enabled(self, chef, proactive_settings):
        """Followup check called when notify_followups enabled."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        # Disable others to isolate
        proactive_settings.notify_birthdays = False
        proactive_settings.notify_anniversaries = False
        proactive_settings.notify_followups = True
        proactive_settings.notify_todos = False
        proactive_settings.notify_milestones = False
        proactive_settings.notify_seasonal = False
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.check_followups', return_value=[]) as mock:
            generate_insights_for_chef(proactive_settings)
            mock.assert_called_once_with(proactive_settings)
    
    def test_calls_todos_when_enabled(self, chef, proactive_settings):
        """Todo check called when notify_todos enabled."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        proactive_settings.notify_birthdays = False
        proactive_settings.notify_anniversaries = False
        proactive_settings.notify_followups = False
        proactive_settings.notify_todos = True
        proactive_settings.notify_milestones = False
        proactive_settings.notify_seasonal = False
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.check_todos', return_value=[]) as mock:
            generate_insights_for_chef(proactive_settings)
            mock.assert_called_once_with(proactive_settings)
    
    def test_calls_milestones_when_enabled(self, chef, proactive_settings):
        """Milestone check called when notify_milestones enabled."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        proactive_settings.notify_birthdays = False
        proactive_settings.notify_anniversaries = False
        proactive_settings.notify_followups = False
        proactive_settings.notify_todos = False
        proactive_settings.notify_milestones = True
        proactive_settings.notify_seasonal = False
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.check_milestones', return_value=[]) as mock:
            generate_insights_for_chef(proactive_settings)
            mock.assert_called_once_with(proactive_settings)
    
    def test_calls_seasonal_when_enabled(self, chef, proactive_settings):
        """Seasonal check called when notify_seasonal enabled."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        proactive_settings.notify_birthdays = False
        proactive_settings.notify_anniversaries = False
        proactive_settings.notify_followups = False
        proactive_settings.notify_todos = False
        proactive_settings.notify_milestones = False
        proactive_settings.notify_seasonal = True
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.check_seasonal', return_value=[]) as mock:
            generate_insights_for_chef(proactive_settings)
            mock.assert_called_once_with(proactive_settings)
    
    def test_returns_total_notification_count(self, chef, proactive_settings):
        """Returns sum of all generated notifications."""
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        
        proactive_settings.notify_birthdays = True
        proactive_settings.notify_followups = True
        proactive_settings.save()
        
        mock_notif = MagicMock()
        with patch('chefs.tasks.proactive_engine.check_special_occasions', return_value=[mock_notif, mock_notif]):
            with patch('chefs.tasks.proactive_engine.check_followups', return_value=[mock_notif]):
                count = generate_insights_for_chef(proactive_settings)
        
        assert count == 3


@pytest.mark.django_db
class TestCheckSpecialOccasions:
    """Tests for check_special_occasions."""
    
    def test_no_notifications_without_client_contexts(self, chef, proactive_settings):
        """No notifications when chef has no clients."""
        from chefs.tasks.proactive_engine import check_special_occasions
        
        proactive_settings.notify_birthdays = True
        proactive_settings.save()
        
        notifications = check_special_occasions(proactive_settings)
        
        assert notifications == []
    
    def test_creates_birthday_notification(self, chef, customer, proactive_settings):
        """Creates notification for upcoming birthday."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from chefs.models import ClientContext
        
        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()
        
        # Create client context with birthday 3 days from now
        upcoming = (timezone.now().date() + timedelta(days=3)).strftime('%m-%d')
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            special_occasions=[{'name': 'Birthday', 'date': upcoming}]
        )
        
        notifications = check_special_occasions(proactive_settings)
        
        assert len(notifications) == 1
        assert 'Birthday' in notifications[0].title
        assert '3 days' in notifications[0].title
    
    def test_creates_anniversary_notification(self, chef, customer, proactive_settings):
        """Creates notification for upcoming anniversary."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from chefs.models import ClientContext
        
        proactive_settings.notify_anniversaries = True
        proactive_settings.anniversary_lead_days = 7
        proactive_settings.save()
        
        # Create client context with anniversary 5 days from now
        upcoming = (timezone.now().date() + timedelta(days=5)).strftime('%m-%d')
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            special_occasions=[{'name': 'Wedding Anniversary', 'date': upcoming}]
        )
        
        notifications = check_special_occasions(proactive_settings)
        
        assert len(notifications) == 1
        assert 'Anniversary' in notifications[0].title
    
    def test_ignores_occasions_beyond_lead_days(self, chef, customer, proactive_settings):
        """Doesn't notify for occasions beyond lead days threshold."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from chefs.models import ClientContext
        
        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()
        
        # Create client context with birthday 14 days from now (beyond 7 day lead)
        future = (timezone.now().date() + timedelta(days=14)).strftime('%m-%d')
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            special_occasions=[{'name': 'Birthday', 'date': future}]
        )
        
        notifications = check_special_occasions(proactive_settings)
        
        assert len(notifications) == 0
    
    def test_deduplication_prevents_duplicates(self, chef, customer, proactive_settings):
        """Doesn't create duplicate notifications for same occasion."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from chefs.models import ClientContext, ChefNotification
        
        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()
        
        upcoming = (timezone.now().date() + timedelta(days=3)).strftime('%m-%d')
        context = ClientContext.objects.create(
            chef=chef,
            client=customer,
            special_occasions=[{'name': 'Birthday', 'date': upcoming}]
        )
        
        # First call creates notification
        notifications1 = check_special_occasions(proactive_settings)
        assert len(notifications1) == 1
        
        # Second call should not create duplicate (dedup key)
        notifications2 = check_special_occasions(proactive_settings)
        assert len(notifications2) == 0


@pytest.mark.django_db
class TestCheckLeadBirthdays:
    """Tests for birthday notifications from Lead.birthday_month/day fields."""

    def test_creates_notification_for_upcoming_lead_birthday(self, chef, proactive_settings):
        """Creates notification when lead has birthday within lead days."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()

        # Create lead with birthday 3 days from now
        upcoming = timezone.now().date() + timedelta(days=3)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            birthday_month=upcoming.month,
            birthday_day=upcoming.day,
        )

        notifications = check_special_occasions(proactive_settings)

        assert len(notifications) == 1
        assert 'birthday' in notifications[0].title.lower()
        assert '3 days' in notifications[0].title

    def test_ignores_lead_birthday_beyond_lead_days(self, chef, proactive_settings):
        """Doesn't notify for lead birthday beyond lead days threshold."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()

        # Create lead with birthday 14 days from now
        future = timezone.now().date() + timedelta(days=14)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            birthday_month=future.month,
            birthday_day=future.day,
        )

        notifications = check_special_occasions(proactive_settings)

        assert len(notifications) == 0

    def test_handles_lead_birthday_next_year(self, chef, proactive_settings):
        """Handles birthday that already passed this year (checks next year)."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()

        # Create lead with birthday yesterday (should check next year)
        yesterday = timezone.now().date() - timedelta(days=1)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            birthday_month=yesterday.month,
            birthday_day=yesterday.day,
        )

        notifications = check_special_occasions(proactive_settings)

        # Should NOT trigger (next year's date is ~364 days away)
        assert len(notifications) == 0

    def test_deduplication_for_lead_birthdays(self, chef, proactive_settings):
        """Doesn't create duplicate notifications for same lead birthday."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.save()

        upcoming = timezone.now().date() + timedelta(days=3)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            birthday_month=upcoming.month,
            birthday_day=upcoming.day,
        )

        # First call creates notification
        notifications1 = check_special_occasions(proactive_settings)
        assert len(notifications1) == 1

        # Second call should not create duplicate
        notifications2 = check_special_occasions(proactive_settings)
        assert len(notifications2) == 0


@pytest.mark.django_db
class TestCheckLeadAnniversaries:
    """Tests for anniversary notifications from Lead.anniversary field."""

    def test_creates_notification_for_upcoming_lead_anniversary(self, chef, proactive_settings):
        """Creates notification when lead has anniversary within lead days."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_anniversaries = True
        proactive_settings.anniversary_lead_days = 7
        proactive_settings.save()

        # Create lead with anniversary 5 days from now
        upcoming = timezone.now().date() + timedelta(days=5)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            anniversary=upcoming,
        )

        notifications = check_special_occasions(proactive_settings)

        assert len(notifications) == 1
        assert 'anniversary' in notifications[0].title.lower()
        assert '5 days' in notifications[0].title

    def test_ignores_lead_anniversary_beyond_lead_days(self, chef, proactive_settings):
        """Doesn't notify for lead anniversary beyond lead days threshold."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_anniversaries = True
        proactive_settings.anniversary_lead_days = 7
        proactive_settings.save()

        # Create lead with anniversary 20 days from now
        future = timezone.now().date() + timedelta(days=20)
        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            anniversary=future,
        )

        notifications = check_special_occasions(proactive_settings)

        assert len(notifications) == 0

    def test_lead_anniversary_checks_next_year_occurrence(self, chef, proactive_settings):
        """Anniversary from previous year still triggers for this year's occurrence."""
        from chefs.tasks.proactive_engine import check_special_occasions
        from crm.models import Lead

        proactive_settings.notify_anniversaries = True
        proactive_settings.anniversary_lead_days = 7
        proactive_settings.save()

        # Create lead with anniversary date 3 days from now, but set year to last year
        upcoming = timezone.now().date() + timedelta(days=3)
        anniversary_date = date(year=2020, month=upcoming.month, day=upcoming.day)

        Lead.objects.create(
            owner=chef.user,
            first_name="Test",
            last_name="Client",
            anniversary=anniversary_date,
        )

        notifications = check_special_occasions(proactive_settings)

        assert len(notifications) == 1
        assert 'anniversary' in notifications[0].title.lower()


@pytest.mark.django_db
class TestCheckFollowups:
    """Tests for check_followups."""
    
    def test_no_notifications_without_orders(self, chef, customer, proactive_settings):
        """No followup if client has no orders."""
        from chefs.tasks.proactive_engine import check_followups
        from chefs.models import ClientContext
        
        proactive_settings.notify_followups = True
        proactive_settings.save()
        
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            total_orders=0
        )
        
        notifications = check_followups(proactive_settings)
        
        assert len(notifications) == 0
    
    def test_creates_followup_for_inactive_client(self, chef, customer, proactive_settings):
        """Creates notification for client who hasn't ordered recently."""
        from chefs.tasks.proactive_engine import check_followups
        from chefs.models import ClientContext
        
        proactive_settings.notify_followups = True
        proactive_settings.followup_threshold_days = 21
        proactive_settings.save()
        
        # Create client with old order
        old_date = timezone.now().date() - timedelta(days=30)
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            total_orders=5,
            last_order_date=old_date
        )
        
        notifications = check_followups(proactive_settings)
        
        assert len(notifications) == 1
        assert '30 days' in notifications[0].title
    
    def test_no_followup_for_recent_client(self, chef, customer, proactive_settings):
        """No followup for client with recent order."""
        from chefs.tasks.proactive_engine import check_followups
        from chefs.models import ClientContext
        
        proactive_settings.notify_followups = True
        proactive_settings.followup_threshold_days = 21
        proactive_settings.save()
        
        recent_date = timezone.now().date() - timedelta(days=5)
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            total_orders=3,
            last_order_date=recent_date
        )
        
        notifications = check_followups(proactive_settings)
        
        assert len(notifications) == 0


@pytest.mark.django_db
class TestCheckMilestones:
    """Tests for check_milestones."""
    
    def test_no_notifications_without_milestones(self, chef, customer, proactive_settings):
        """No notifications when no one hit a milestone."""
        from chefs.tasks.proactive_engine import check_milestones
        from chefs.models import ClientContext
        
        proactive_settings.notify_milestones = True
        proactive_settings.save()
        
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            total_orders=3  # Not a milestone number
        )
        
        notifications = check_milestones(proactive_settings)
        
        assert len(notifications) == 0
    
    def test_creates_milestone_notification(self, chef, customer, proactive_settings):
        """Creates notification for milestone (10th order)."""
        from chefs.tasks.proactive_engine import check_milestones
        from chefs.models import ClientContext
        
        proactive_settings.notify_milestones = True
        proactive_settings.save()
        
        ClientContext.objects.create(
            chef=chef,
            client=customer,
            total_orders=10  # Milestone!
        )
        
        notifications = check_milestones(proactive_settings)
        
        assert len(notifications) == 1
        assert '10 orders' in notifications[0].title


@pytest.mark.django_db
class TestCheckSeasonal:
    """Tests for check_seasonal."""
    
    def test_creates_seasonal_notification(self, chef, proactive_settings):
        """Creates seasonal notification."""
        from chefs.tasks.proactive_engine import check_seasonal
        
        proactive_settings.notify_seasonal = True
        proactive_settings.save()
        
        seasonal_data = {
            timezone.now().month: {
                'vegetables': ['asparagus', 'peas'],
                'fruits': ['strawberries']
            }
        }
        with patch('meals.sous_chef_tools.SEASONAL_INGREDIENTS', seasonal_data, create=True):
            notifications = check_seasonal(proactive_settings)
        
        assert len(notifications) == 1
        assert 'season' in notifications[0].title.lower()
    
    def test_deduplication_prevents_duplicates_same_month(self, chef, proactive_settings):
        """Doesn't create seasonal notification twice in same month."""
        from chefs.tasks.proactive_engine import check_seasonal
        
        proactive_settings.notify_seasonal = True
        proactive_settings.save()
        
        seasonal_data = {
            timezone.now().month: {'vegetables': ['asparagus']}
        }
        
        with patch('meals.sous_chef_tools.SEASONAL_INGREDIENTS', seasonal_data, create=True):
            # First call creates notification
            notifications1 = check_seasonal(proactive_settings)
            assert len(notifications1) == 1
            
            # Second call should not create duplicate (dedup key)
            notifications2 = check_seasonal(proactive_settings)
            assert len(notifications2) == 0
    
    def test_no_notification_if_no_seasonal_data(self, chef, proactive_settings):
        """No notification if no seasonal data for current month."""
        from chefs.tasks.proactive_engine import check_seasonal
        
        proactive_settings.notify_seasonal = True
        proactive_settings.save()
        
        with patch('meals.sous_chef_tools.SEASONAL_INGREDIENTS', {}, create=True):
            notifications = check_seasonal(proactive_settings)
        
        assert len(notifications) == 0


@pytest.mark.django_db
class TestRunProactiveCheck:
    """Tests for main run_proactive_check task."""
    
    def test_processes_enabled_chefs(self, chef, proactive_settings):
        """Processes chefs with proactive enabled."""
        from chefs.tasks.proactive_engine import run_proactive_check
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.enabled = True
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_REALTIME
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.generate_insights_for_chef', return_value=0) as mock:
            result = run_proactive_check()
            mock.assert_called_once()
    
    def test_skips_disabled_chefs(self, chef, proactive_settings):
        """Skips chefs with proactive disabled."""
        from chefs.tasks.proactive_engine import run_proactive_check
        
        proactive_settings.enabled = False
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.generate_insights_for_chef') as mock:
            result = run_proactive_check()
            mock.assert_not_called()
    
    def test_skips_chefs_in_quiet_hours(self, chef, proactive_settings):
        """Skips chefs during quiet hours."""
        from chefs.tasks.proactive_engine import run_proactive_check
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.enabled = True
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_REALTIME
        proactive_settings.quiet_hours_enabled = True
        proactive_settings.quiet_hours_start = time(0, 0)
        proactive_settings.quiet_hours_end = time(23, 59)  # All day
        proactive_settings.quiet_hours_timezone = 'UTC'
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.generate_insights_for_chef') as mock:
            result = run_proactive_check()
            mock.assert_not_called()
    
    def test_returns_processed_count(self, chef, proactive_settings):
        """Returns count of processed chefs and notifications."""
        from chefs.tasks.proactive_engine import run_proactive_check
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.enabled = True
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_REALTIME
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.generate_insights_for_chef', return_value=3):
            result = run_proactive_check()
        
        assert result['processed'] == 1
        assert result['notifications'] == 3
    
    def test_handles_errors_gracefully(self, chef, proactive_settings):
        """Continues processing even if one chef fails."""
        from chefs.tasks.proactive_engine import run_proactive_check
        from chefs.models import ChefProactiveSettings
        
        proactive_settings.enabled = True
        proactive_settings.notification_frequency = ChefProactiveSettings.FREQUENCY_REALTIME
        proactive_settings.save()
        
        with patch('chefs.tasks.proactive_engine.generate_insights_for_chef', side_effect=Exception('Test error')):
            # Should not raise
            result = run_proactive_check()
        
        assert result['processed'] == 0  # Failed, so not counted


@pytest.mark.django_db
class TestSendWelcomeNotification:
    """Tests for send_welcome_notification task."""
    
    def test_creates_welcome_notification(self, chef):
        """Creates welcome notification for new chef."""
        from chefs.tasks.proactive_engine import send_welcome_notification
        from chefs.models import ChefNotification
        
        result = send_welcome_notification(chef.id)
        
        notification = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_WELCOME
        ).first()
        
        assert notification is not None
        assert 'Welcome' in notification.title
        assert result['status'] == 'sent'
    
    def test_marks_chef_as_welcomed(self, chef):
        """Sets welcomed flag on onboarding state."""
        from chefs.tasks.proactive_engine import send_welcome_notification
        from chefs.models import ChefOnboardingState
        
        send_welcome_notification(chef.id)
        
        state = ChefOnboardingState.objects.get(chef=chef)
        assert state.welcomed is True
    
    def test_idempotent_no_duplicate_welcome(self, chef, onboarding_state):
        """Doesn't send duplicate welcome."""
        from chefs.tasks.proactive_engine import send_welcome_notification
        from chefs.models import ChefNotification
        
        onboarding_state.welcomed = True
        onboarding_state.save()
        
        result = send_welcome_notification(chef.id)
        
        count = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_WELCOME
        ).count()
        
        assert count == 0
        assert result['status'] == 'already_welcomed'
    
    def test_handles_missing_chef(self):
        """Handles non-existent chef ID gracefully."""
        from chefs.tasks.proactive_engine import send_welcome_notification
        
        # Should not raise
        result = send_welcome_notification(99999)
        
        assert result['status'] == 'error'
