# chefs/tests/test_cert_expiry.py
"""
Tests for certification expiry tracking and notifications.
"""

import pytest
from datetime import date, timedelta
from django.utils import timezone

from chefs.models import Chef, ChefProactiveSettings, ChefNotification
from chefs.tasks.proactive_engine import check_certification_expiry


@pytest.mark.django_db
class TestCertExpiryFields:
    """Test the new certification expiry fields on Chef model."""
    
    def test_food_handlers_cert_fields_exist(self, chef):
        """Chef model should have food handler cert fields."""
        assert hasattr(chef, 'food_handlers_cert')
        assert hasattr(chef, 'food_handlers_cert_number')
        assert hasattr(chef, 'food_handlers_cert_expiry')
        assert hasattr(chef, 'food_handlers_cert_verified_at')
    
    def test_food_handlers_cert_number_can_be_set(self, chef):
        """Can set food handler cert number."""
        chef.food_handlers_cert_number = "FH-12345-CA"
        chef.save()
        chef.refresh_from_db()
        assert chef.food_handlers_cert_number == "FH-12345-CA"
    
    def test_food_handlers_cert_expiry_can_be_set(self, chef):
        """Can set food handler cert expiry date."""
        expiry = date.today() + timedelta(days=90)
        chef.food_handlers_cert_expiry = expiry
        chef.save()
        chef.refresh_from_db()
        assert chef.food_handlers_cert_expiry == expiry
    
    def test_food_handlers_cert_verified_at_can_be_set(self, chef):
        """Can set food handler cert verification timestamp."""
        now = timezone.now()
        chef.food_handlers_cert_verified_at = now
        chef.save()
        chef.refresh_from_db()
        assert chef.food_handlers_cert_verified_at is not None


@pytest.mark.django_db
class TestCertExpiryNotifications:
    """Test certification expiry notifications in proactive engine."""
    
    def test_no_notification_when_cert_expiry_disabled(self, chef, proactive_settings):
        """No notification when notify_cert_expiry is False."""
        proactive_settings.notify_cert_expiry = False
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=7)
        chef.save()
        
        # check_certification_expiry is not called when setting is disabled
        # This is handled by generate_insights_for_chef
        # So we test it indirectly
        from chefs.tasks.proactive_engine import generate_insights_for_chef
        count = generate_insights_for_chef(proactive_settings)
        
        notifications = ChefNotification.objects.filter(
            chef=chef,
            notification_type=ChefNotification.TYPE_CERT_EXPIRY
        )
        assert notifications.count() == 0
    
    def test_no_notification_when_cert_not_expiring(self, chef, proactive_settings):
        """No notification when cert is not expiring soon."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=90)  # Far in future
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 0
    
    def test_notification_30_days_before_expiry(self, chef, proactive_settings):
        """Notification when cert expires in 30 days."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=25)
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 1
        assert "25 days" in notifications[0].title
        assert notifications[0].action_context.get('urgency') == 'warning'
    
    def test_notification_7_days_before_expiry(self, chef, proactive_settings):
        """Urgent notification when cert expires in 7 days."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=5)
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 1
        assert "5 days" in notifications[0].title
        assert notifications[0].action_context.get('urgency') == 'urgent'
    
    def test_notification_when_expired(self, chef, proactive_settings):
        """Critical notification when cert has expired."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() - timedelta(days=5)  # Already expired
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 1
        assert "expired" in notifications[0].title.lower()
        assert notifications[0].action_context.get('urgency') == 'expired'
    
    def test_insurance_expiry_notification(self, chef, proactive_settings):
        """Notification for insurance expiry."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.insured = True
        chef.insurance_expiry = date.today() + timedelta(days=20)
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 1
        assert "insurance" in notifications[0].title.lower()
        assert notifications[0].action_context.get('cert_type') == 'insurance'
    
    def test_both_certs_expiring(self, chef, proactive_settings):
        """Both food handler and insurance expiring get notifications."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=20)
        chef.insured = True
        chef.insurance_expiry = date.today() + timedelta(days=25)
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert len(notifications) == 2
        cert_types = [n.action_context.get('cert_type') for n in notifications]
        assert 'food_handler' in cert_types
        assert 'insurance' in cert_types
    
    def test_deduplication_prevents_duplicate_notifications(self, chef, proactive_settings):
        """Same expiry date shouldn't create duplicate notifications."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=20)
        chef.save()
        
        # First check
        notifications1 = check_certification_expiry(proactive_settings)
        assert len(notifications1) == 1
        
        # Second check - should be deduplicated
        notifications2 = check_certification_expiry(proactive_settings)
        assert len(notifications2) == 0  # Already notified
    
    def test_notification_type_is_cert_expiry(self, chef, proactive_settings):
        """Notification should have TYPE_CERT_EXPIRY type."""
        proactive_settings.notify_cert_expiry = True
        proactive_settings.save()
        
        chef.food_handlers_cert = True
        chef.food_handlers_cert_expiry = date.today() + timedelta(days=20)
        chef.save()
        
        notifications = check_certification_expiry(proactive_settings)
        assert notifications[0].notification_type == ChefNotification.TYPE_CERT_EXPIRY


@pytest.mark.django_db
class TestNotifyCertExpirySetting:
    """Test the notify_cert_expiry setting on ChefProactiveSettings."""
    
    def test_notify_cert_expiry_default_true(self, chef):
        """notify_cert_expiry should default to True."""
        settings = ChefProactiveSettings.get_or_create_for_chef(chef)
        assert settings.notify_cert_expiry is True
    
    def test_notify_cert_expiry_can_be_disabled(self, chef):
        """Chef can disable cert expiry notifications."""
        settings = ChefProactiveSettings.get_or_create_for_chef(chef)
        settings.notify_cert_expiry = False
        settings.save()
        settings.refresh_from_db()
        assert settings.notify_cert_expiry is False
