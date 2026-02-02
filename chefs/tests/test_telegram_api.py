"""
Tests for Telegram API Endpoints - Phase 3.

Tests cover:
- POST /chefs/api/telegram/generate-link/ - returns QR code data URL + deep link
- POST /chefs/api/telegram/unlink/ - unlinks Telegram account
- GET /chefs/api/telegram/status/ - returns link status and settings
- PATCH /chefs/api/telegram/settings/ - update notification settings

These tests use mocks to allow running without PostgreSQL.
Integration tests with real DB should run in CI.

Run with: pytest chefs/tests/test_telegram_api.py -v
"""

import json
from datetime import time as dt_time, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from django.test import RequestFactory
from django.utils import timezone


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_chef():
    """Create a mock Chef instance."""
    chef = MagicMock()
    chef.id = 1
    chef.user = MagicMock()
    chef.user.id = 1
    chef.user.username = "test_chef"
    chef.user.is_authenticated = True
    return chef


@pytest.fixture
def mock_request(mock_chef):
    """Create a mock authenticated request."""
    factory = RequestFactory()
    request = factory.get('/')
    request.user = mock_chef.user
    return request


@pytest.fixture
def mock_telegram_link(mock_chef):
    """Create a mock ChefTelegramLink."""
    link = MagicMock()
    link.telegram_user_id = 123456789
    link.telegram_username = "test_tg_user"
    link.telegram_first_name = "Test"
    link.linked_at = timezone.now()
    link.is_active = True
    link.chef = mock_chef
    return link


@pytest.fixture
def mock_telegram_settings(mock_chef):
    """Create a mock ChefTelegramSettings."""
    settings = MagicMock()
    settings.chef = mock_chef
    settings.notify_new_orders = True
    settings.notify_order_updates = True
    settings.notify_schedule_reminders = True
    settings.notify_customer_messages = False
    settings.quiet_hours_start = dt_time(22, 0)
    settings.quiet_hours_end = dt_time(8, 0)
    settings.quiet_hours_enabled = True
    return settings


# =============================================================================
# POST /chefs/api/telegram/generate-link/ TESTS
# =============================================================================


class TestGenerateTelegramLink:
    """Tests for POST /chefs/api/telegram/generate-link/."""

    def test_generate_link_returns_qr_code_and_deep_link(self, mock_chef):
        """Successful request returns QR code data URL and deep link."""
        from chefs.api.telegram_views import telegram_generate_link

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/generate-link/')
        request.user = mock_chef.user

        mock_token = MagicMock()
        mock_token.token = "test_token_abc123"
        mock_token.expires_at = timezone.now() + timedelta(minutes=10)

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.TelegramLinkService') as MockService:
            
            MockChef.objects.get.return_value = mock_chef
            
            mock_service = MagicMock()
            mock_service.generate_link_token.return_value = mock_token
            mock_service.get_deep_link.return_value = "https://t.me/SautaiChefBot?start=test_token_abc123"
            mock_service.get_qr_code_data_url.return_value = "data:image/png;base64,iVBOR..."
            MockService.return_value = mock_service

            response = telegram_generate_link(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'deep_link' in data
        assert 'qr_code' in data
        assert 'expires_at' in data
        assert data['deep_link'].startswith('https://t.me/')
        assert data['qr_code'].startswith('data:image/png;base64,')

    def test_generate_link_requires_authentication(self):
        """Unauthenticated request returns 401 or 403."""
        from chefs.api.telegram_views import telegram_generate_link

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/generate-link/')
        request.user = MagicMock()
        request.user.is_authenticated = False

        # The decorator should handle this, but let's verify the view behavior
        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.DoesNotExist = Exception
            MockChef.objects.get.side_effect = MockChef.DoesNotExist

            response = telegram_generate_link(request)

        # Should fail because user is not a chef
        assert response.status_code in [401, 403]

    def test_generate_link_requires_chef_account(self, mock_request):
        """Request from non-chef user returns 403."""
        from chefs.api.telegram_views import telegram_generate_link
        from chefs.models import Chef

        # Create a POST request (this endpoint only accepts POST)
        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/generate-link/')
        request.user = mock_request.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.DoesNotExist = Chef.DoesNotExist
            MockChef.objects.get.side_effect = Chef.DoesNotExist

            response = telegram_generate_link(request)

        assert response.status_code == 403
        data = json.loads(response.content)
        assert 'error' in data

    def test_generate_link_only_accepts_post(self, mock_chef):
        """GET request returns 405 Method Not Allowed."""
        from chefs.api.telegram_views import telegram_generate_link

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/generate-link/')
        request.user = mock_chef.user

        response = telegram_generate_link(request)

        assert response.status_code == 405


# =============================================================================
# POST /chefs/api/telegram/unlink/ TESTS
# =============================================================================


class TestUnlinkTelegram:
    """Tests for POST /chefs/api/telegram/unlink/."""

    def test_unlink_success(self, mock_chef, mock_telegram_link):
        """Successful unlink returns 200."""
        from chefs.api.telegram_views import telegram_unlink

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/unlink/')
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.TelegramLinkService') as MockService:
            
            MockChef.objects.get.return_value = mock_chef
            
            mock_service = MagicMock()
            mock_service.unlink.return_value = True
            MockService.return_value = mock_service

            response = telegram_unlink(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True

    def test_unlink_when_not_linked(self, mock_chef):
        """Unlink when not linked returns 400."""
        from chefs.api.telegram_views import telegram_unlink

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/unlink/')
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.TelegramLinkService') as MockService:
            
            MockChef.objects.get.return_value = mock_chef
            
            mock_service = MagicMock()
            mock_service.unlink.return_value = False  # Not linked
            MockService.return_value = mock_service

            response = telegram_unlink(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert 'error' in data

    def test_unlink_requires_chef_account(self, mock_request):
        """Request from non-chef user returns 403."""
        from chefs.api.telegram_views import telegram_unlink
        from chefs.models import Chef

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/unlink/')
        request.user = mock_request.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.DoesNotExist = Chef.DoesNotExist
            MockChef.objects.get.side_effect = Chef.DoesNotExist

            response = telegram_unlink(request)

        assert response.status_code == 403

    def test_unlink_only_accepts_post(self, mock_chef):
        """GET request returns 405 Method Not Allowed."""
        from chefs.api.telegram_views import telegram_unlink

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/unlink/')
        request.user = mock_chef.user

        response = telegram_unlink(request)

        assert response.status_code == 405


# =============================================================================
# GET /chefs/api/telegram/status/ TESTS
# =============================================================================


class TestTelegramStatus:
    """Tests for GET /chefs/api/telegram/status/."""

    def test_status_when_linked(self, mock_chef, mock_telegram_link, mock_telegram_settings):
        """Status when linked returns link info and settings."""
        from chefs.api.telegram_views import telegram_status

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/status/')
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.objects.get.return_value = mock_chef
            mock_chef.telegram_link = mock_telegram_link
            mock_chef.telegram_settings = mock_telegram_settings

            response = telegram_status(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        
        assert data['linked'] is True
        assert data['telegram_username'] == "test_tg_user"
        assert data['telegram_first_name'] == "Test"
        assert 'linked_at' in data
        assert 'settings' in data
        assert data['settings']['notify_new_orders'] is True
        assert data['settings']['notify_order_updates'] is True
        assert data['settings']['quiet_hours_enabled'] is True

    def test_status_when_not_linked(self, mock_chef):
        """Status when not linked returns linked=False."""
        from chefs.api.telegram_views import telegram_status
        from chefs.models.telegram_integration import ChefTelegramLink

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/status/')
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.objects.get.return_value = mock_chef
            # Simulate no telegram_link
            type(mock_chef).telegram_link = PropertyMock(side_effect=ChefTelegramLink.DoesNotExist)

            response = telegram_status(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['linked'] is False
        assert 'settings' not in data or data.get('settings') is None

    def test_status_when_link_inactive(self, mock_chef, mock_telegram_link):
        """Status when link is inactive returns linked=False."""
        from chefs.api.telegram_views import telegram_status

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/status/')
        request.user = mock_chef.user

        mock_telegram_link.is_active = False

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.objects.get.return_value = mock_chef
            mock_chef.telegram_link = mock_telegram_link

            response = telegram_status(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['linked'] is False

    def test_status_requires_chef_account(self, mock_request):
        """Request from non-chef user returns 403."""
        from chefs.api.telegram_views import telegram_status
        from chefs.models import Chef

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.DoesNotExist = Chef.DoesNotExist
            MockChef.objects.get.side_effect = Chef.DoesNotExist

            response = telegram_status(mock_request)

        assert response.status_code == 403

    def test_status_only_accepts_get(self, mock_chef):
        """POST request returns 405 Method Not Allowed."""
        from chefs.api.telegram_views import telegram_status

        factory = RequestFactory()
        request = factory.post('/chefs/api/telegram/status/')
        request.user = mock_chef.user

        response = telegram_status(request)

        assert response.status_code == 405


# =============================================================================
# PATCH /chefs/api/telegram/settings/ TESTS
# =============================================================================


class TestTelegramSettings:
    """Tests for PATCH /chefs/api/telegram/settings/."""

    def test_update_single_setting(self, mock_chef, mock_telegram_settings):
        """Update a single notification setting."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({'notify_new_orders': False}),
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.ChefTelegramSettings') as MockSettings:
            
            MockChef.objects.get.return_value = mock_chef
            MockSettings.objects.get.return_value = mock_telegram_settings

            response = telegram_settings(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'settings' in data
        # The setting should have been updated
        assert mock_telegram_settings.notify_new_orders is False
        mock_telegram_settings.save.assert_called_once()

    def test_update_multiple_settings(self, mock_chef, mock_telegram_settings):
        """Update multiple notification settings at once."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({
                'notify_new_orders': False,
                'notify_order_updates': False,
                'quiet_hours_enabled': False,
            }),
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.ChefTelegramSettings') as MockSettings:
            
            MockChef.objects.get.return_value = mock_chef
            MockSettings.objects.get.return_value = mock_telegram_settings

            response = telegram_settings(request)

        assert response.status_code == 200
        assert mock_telegram_settings.notify_new_orders is False
        assert mock_telegram_settings.notify_order_updates is False
        assert mock_telegram_settings.quiet_hours_enabled is False

    def test_update_quiet_hours_times(self, mock_chef, mock_telegram_settings):
        """Update quiet hours start and end times."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({
                'quiet_hours_start': '23:00',
                'quiet_hours_end': '07:00',
            }),
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.ChefTelegramSettings') as MockSettings:
            
            MockChef.objects.get.return_value = mock_chef
            MockSettings.objects.get.return_value = mock_telegram_settings

            response = telegram_settings(request)

        assert response.status_code == 200
        # Times should be parsed and set
        assert mock_telegram_settings.quiet_hours_start == dt_time(23, 0)
        assert mock_telegram_settings.quiet_hours_end == dt_time(7, 0)

    def test_update_settings_invalid_field(self, mock_chef, mock_telegram_settings):
        """Updating invalid field is ignored."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({
                'invalid_field': True,
                'notify_new_orders': False,  # Valid field
            }),
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.ChefTelegramSettings') as MockSettings:
            
            MockChef.objects.get.return_value = mock_chef
            MockSettings.objects.get.return_value = mock_telegram_settings

            response = telegram_settings(request)

        # Should still succeed, just ignore invalid field
        assert response.status_code == 200
        assert mock_telegram_settings.notify_new_orders is False

    def test_update_settings_requires_linked_account(self, mock_chef):
        """Cannot update settings if Telegram not linked."""
        from chefs.api.telegram_views import telegram_settings
        from chefs.models.telegram_integration import ChefTelegramSettings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({'notify_new_orders': False}),
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef, \
             patch('chefs.api.telegram_views.ChefTelegramSettings') as MockSettings:
            
            MockChef.objects.get.return_value = mock_chef
            MockSettings.DoesNotExist = ChefTelegramSettings.DoesNotExist
            MockSettings.objects.get.side_effect = ChefTelegramSettings.DoesNotExist

            response = telegram_settings(request)

        assert response.status_code == 404
        data = json.loads(response.content)
        assert 'error' in data

    def test_update_settings_requires_chef_account(self, mock_request):
        """Request from non-chef user returns 403."""
        from chefs.api.telegram_views import telegram_settings
        from chefs.models import Chef

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data=json.dumps({'notify_new_orders': False}),
            content_type='application/json'
        )
        request.user = mock_request.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.DoesNotExist = Chef.DoesNotExist
            MockChef.objects.get.side_effect = Chef.DoesNotExist

            response = telegram_settings(request)

        assert response.status_code == 403

    def test_update_settings_only_accepts_patch(self, mock_chef):
        """GET request returns 405 Method Not Allowed."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.get('/chefs/api/telegram/settings/')
        request.user = mock_chef.user

        response = telegram_settings(request)

        assert response.status_code == 405

    def test_update_settings_invalid_json(self, mock_chef):
        """Invalid JSON returns 400."""
        from chefs.api.telegram_views import telegram_settings

        factory = RequestFactory()
        request = factory.patch(
            '/chefs/api/telegram/settings/',
            data='not valid json{',
            content_type='application/json'
        )
        request.user = mock_chef.user

        with patch('chefs.api.telegram_views.Chef') as MockChef:
            MockChef.objects.get.return_value = mock_chef

            response = telegram_settings(request)

        assert response.status_code == 400
