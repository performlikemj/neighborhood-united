# chefs/tests/test_proactive_integration.py
"""
Integration test for proactive engine.

Tests the full E2E flow:
1. Chef with proactive enabled
2. Leads with upcoming birthdays/anniversaries
3. Run proactive check
4. Verify notifications created
"""

import pytest
from datetime import timedelta, date
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
class TestProactiveIntegration:
    """Full integration test of the proactive notification system."""

    def test_birthday_notification_created_for_lead(self, chef, proactive_settings):
        """
        E2E test: Lead with upcoming birthday creates notification.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification
        from chefs.tasks.proactive_engine import run_proactive_check

        # Setup: Enable proactive with birthdays
        proactive_settings.enabled = True
        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.notification_frequency = 'realtime'
        proactive_settings.save()

        # Create lead with birthday in 5 days
        today = timezone.now().date()
        birthday = today + timedelta(days=5)
        
        lead = Lead.objects.create(
            owner=chef.user,
            first_name="Birthday",
            last_name="Test",
            email="birthday_test@example.com",
            birthday_month=birthday.month,
            birthday_day=birthday.day,
            status="qualified",
        )

        # Clear any existing notifications
        ChefNotification.objects.filter(chef=chef).delete()

        # Run proactive check
        result = run_proactive_check()

        # Verify notification created
        notifications = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY
        )
        
        assert notifications.count() == 1, f"Expected 1 birthday notification, got {notifications.count()}"
        
        notif = notifications.first()
        assert "Birthday Test" in notif.title
        assert "5 days" in notif.title
        assert notif.status in [ChefNotification.STATUS_PENDING, ChefNotification.STATUS_SENT]
        
        print(f"\n✅ Birthday notification created: {notif.title}")

    def test_anniversary_notification_created_for_lead(self, chef, proactive_settings):
        """
        E2E test: Lead with upcoming anniversary creates notification.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification
        from chefs.tasks.proactive_engine import run_proactive_check

        # Setup
        proactive_settings.enabled = True
        proactive_settings.notify_anniversaries = True
        proactive_settings.anniversary_lead_days = 7
        proactive_settings.notification_frequency = 'realtime'
        proactive_settings.save()

        # Create lead with anniversary in 3 days
        today = timezone.now().date()
        anniversary = today + timedelta(days=3)
        
        lead = Lead.objects.create(
            owner=chef.user,
            first_name="Anniversary",
            last_name="Test",
            email="anniversary_test@example.com",
            anniversary=anniversary,
            status="qualified",
        )

        # Clear existing
        ChefNotification.objects.filter(chef=chef).delete()

        # Run
        result = run_proactive_check()

        # Verify
        notifications = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_ANNIVERSARY
        )
        
        assert notifications.count() == 1, f"Expected 1 anniversary notification, got {notifications.count()}"
        
        notif = notifications.first()
        assert "Anniversary Test" in notif.title
        assert "3 days" in notif.title
        
        print(f"\n✅ Anniversary notification created: {notif.title}")

    def test_deduplication_prevents_duplicate_notifications(self, chef, proactive_settings):
        """
        E2E test: Running proactive check twice doesn't create duplicates.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification
        from chefs.tasks.proactive_engine import run_proactive_check

        # Setup
        proactive_settings.enabled = True
        proactive_settings.notify_birthdays = True
        proactive_settings.birthday_lead_days = 7
        proactive_settings.notification_frequency = 'realtime'
        proactive_settings.save()

        # Create lead
        today = timezone.now().date()
        birthday = today + timedelta(days=5)
        
        Lead.objects.create(
            owner=chef.user,
            first_name="Dedup",
            last_name="Test",
            email="dedup_test@example.com",
            birthday_month=birthday.month,
            birthday_day=birthday.day,
            status="qualified",
        )

        # Clear
        ChefNotification.objects.filter(chef=chef).delete()

        # Run twice
        run_proactive_check()
        run_proactive_check()

        # Should still only have 1 notification
        notifications = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_BIRTHDAY
        )
        
        assert notifications.count() == 1, f"Deduplication failed: got {notifications.count()} notifications"
        
        print(f"\n✅ Deduplication works: only 1 notification after 2 runs")

    def test_quiet_hours_blocks_notifications(self, chef, proactive_settings):
        """
        E2E test: Notifications not sent during quiet hours.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification
        from chefs.tasks.proactive_engine import run_proactive_check
        from datetime import time
        from unittest.mock import patch
        import pytz

        # Setup with quiet hours covering now
        proactive_settings.enabled = True
        proactive_settings.notify_birthdays = True
        proactive_settings.quiet_hours_enabled = True
        proactive_settings.quiet_hours_start = time(0, 0)  # Midnight
        proactive_settings.quiet_hours_end = time(23, 59)  # All day
        proactive_settings.quiet_hours_timezone = 'UTC'
        proactive_settings.notification_frequency = 'realtime'
        proactive_settings.save()

        # Create lead
        today = timezone.now().date()
        birthday = today + timedelta(days=5)
        
        Lead.objects.create(
            owner=chef.user,
            first_name="QuietHours",
            last_name="Test",
            email="quiet_test@example.com",
            birthday_month=birthday.month,
            birthday_day=birthday.day,
            status="qualified",
        )

        # Clear
        ChefNotification.objects.filter(chef=chef).delete()

        # Run
        result = run_proactive_check()

        # Should have no notifications (quiet hours active)
        notifications = ChefNotification.objects.filter(chef=chef)
        
        assert notifications.count() == 0, f"Quiet hours not respected: got {notifications.count()} notifications"
        
        print(f"\n✅ Quiet hours respected: 0 notifications")

    def test_disabled_proactive_creates_no_notifications(self, chef, proactive_settings):
        """
        E2E test: Disabled proactive doesn't create notifications.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification
        from chefs.tasks.proactive_engine import run_proactive_check

        # Setup with proactive OFF
        proactive_settings.enabled = False
        proactive_settings.save()

        # Create lead
        today = timezone.now().date()
        birthday = today + timedelta(days=5)
        
        Lead.objects.create(
            owner=chef.user,
            first_name="Disabled",
            last_name="Test",
            email="disabled_test@example.com",
            birthday_month=birthday.month,
            birthday_day=birthday.day,
            status="qualified",
        )

        # Clear
        ChefNotification.objects.filter(chef=chef).delete()

        # Run
        result = run_proactive_check()

        # Should have no notifications
        notifications = ChefNotification.objects.filter(chef=chef)
        
        assert notifications.count() == 0, f"Disabled proactive still created notifications: {notifications.count()}"
        
        print(f"\n✅ Disabled proactive: 0 notifications")

    def test_full_flow_multiple_notification_types(self, chef, proactive_settings):
        """
        E2E test: Multiple notification types in one run.
        """
        from crm.models import Lead
        from chefs.models import ChefNotification, ClientContext
        from chefs.tasks.proactive_engine import run_proactive_check

        # Setup: Enable all notification types
        proactive_settings.enabled = True
        proactive_settings.notify_birthdays = True
        proactive_settings.notify_anniversaries = True
        proactive_settings.birthday_lead_days = 10
        proactive_settings.anniversary_lead_days = 10
        proactive_settings.notification_frequency = 'realtime'
        proactive_settings.save()

        today = timezone.now().date()

        # Create lead with birthday
        Lead.objects.create(
            owner=chef.user,
            first_name="Multi",
            last_name="Birthday",
            email="multi_bday@example.com",
            birthday_month=(today + timedelta(days=7)).month,
            birthday_day=(today + timedelta(days=7)).day,
            status="qualified",
        )

        # Create lead with anniversary
        Lead.objects.create(
            owner=chef.user,
            first_name="Multi",
            last_name="Anniversary",
            email="multi_anniv@example.com",
            anniversary=today + timedelta(days=5),
            status="qualified",
        )

        # Clear
        ChefNotification.objects.filter(chef=chef).delete()

        # Run
        result = run_proactive_check()

        # Check results
        all_notifs = ChefNotification.objects.filter(chef=chef)
        birthday_notifs = all_notifs.filter(notification_type=ChefNotification.TYPE_BIRTHDAY)
        anniversary_notifs = all_notifs.filter(notification_type=ChefNotification.TYPE_ANNIVERSARY)

        print(f"\n📊 Results:")
        print(f"   Total notifications: {all_notifs.count()}")
        print(f"   Birthday: {birthday_notifs.count()}")
        print(f"   Anniversary: {anniversary_notifs.count()}")

        assert birthday_notifs.count() >= 1, "Expected at least 1 birthday notification"
        assert anniversary_notifs.count() >= 1, "Expected at least 1 anniversary notification"

        for notif in all_notifs:
            print(f"   - [{notif.notification_type}] {notif.title}")

        print(f"\n✅ Multiple notification types working!")
