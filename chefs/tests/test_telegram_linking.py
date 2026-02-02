"""
Tests for Telegram Linking Service - Phase 2.

Tests cover:
- TelegramLinkService: Token generation, deep links, QR codes
- Linking flow: Valid tokens, expired tokens, used tokens
- Unlinking: Deactivation flow

These tests use mocks for database operations to allow running without PostgreSQL.
Integration tests with real DB should run in CI.

Run with: pytest chefs/tests/test_telegram_linking.py -v
"""

import base64
from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from django.utils import timezone


# =============================================================================
# TELEGRAM LINK SERVICE - TOKEN GENERATION TESTS
# =============================================================================


class TestTelegramLinkServiceTokenGeneration:
    """Tests for TelegramLinkService token generation."""

    def test_generate_link_token_creates_valid_token(self):
        """Token is created with 10-minute expiry and is valid."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()
        chef.id = 1
        chef.user.username = "test_chef"

        # Mock the TelegramLinkToken.objects.create
        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken:
            mock_token_instance = MagicMock()
            mock_token_instance.token = "test_token_abc123"
            mock_token_instance.is_valid = True
            mock_token_instance.used = False
            mock_token_instance.chef = chef
            MockToken.objects.create.return_value = mock_token_instance

            token = service.generate_link_token(chef)

            # Verify create was called with correct parameters
            MockToken.objects.create.assert_called_once()
            call_kwargs = MockToken.objects.create.call_args[1]

            assert call_kwargs['chef'] == chef
            assert 'token' in call_kwargs
            assert len(call_kwargs['token']) > 20  # URL-safe tokens are at least 32 chars
            assert 'expires_at' in call_kwargs

            # Check expiry is approximately 10 minutes from now
            expected_expiry = timezone.now() + timedelta(minutes=10)
            time_diff = abs((call_kwargs['expires_at'] - expected_expiry).total_seconds())
            assert time_diff < 5  # Within 5 seconds

            # Return value should be the mock token
            assert token == mock_token_instance

    def test_generate_link_token_creates_unique_tokens(self):
        """Multiple token generations produce unique tokens."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()

        generated_tokens = []

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken:
            def capture_token(**kwargs):
                generated_tokens.append(kwargs['token'])
                mock = MagicMock()
                mock.token = kwargs['token']
                return mock

            MockToken.objects.create.side_effect = capture_token

            service.generate_link_token(chef)
            service.generate_link_token(chef)

        assert len(generated_tokens) == 2
        assert generated_tokens[0] != generated_tokens[1]

    def test_deep_link_format_is_correct(self):
        """Deep link follows Telegram format: https://t.me/BOT?start=TOKEN."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        token = "test_token_xyz123"

        deep_link = service.get_deep_link(token)

        # Check format
        assert deep_link.startswith("https://t.me/")
        assert "?start=" in deep_link
        assert token in deep_link
        # Should contain the bot username
        assert service.BOT_USERNAME in deep_link

    def test_qr_code_is_valid_png_data_url(self):
        """QR code returns valid base64 PNG data URL."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        token = "test_token_for_qr"

        data_url = service.get_qr_code_data_url(token)

        # Check data URL format
        assert data_url.startswith("data:image/png;base64,")

        # Extract and validate base64 data
        base64_data = data_url.split(",")[1]
        try:
            decoded = base64.b64decode(base64_data)
            # PNG files start with specific magic bytes
            assert decoded[:8] == b'\x89PNG\r\n\x1a\n'
        except Exception as e:
            pytest.fail(f"Invalid base64 data: {e}")

    def test_qr_code_contains_deep_link(self):
        """QR code encodes the correct deep link."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        token = "test_token_for_qr_decode"
        expected_deep_link = service.get_deep_link(token)

        data_url = service.get_qr_code_data_url(token)

        # Decode the QR code from the data URL
        base64_data = data_url.split(",")[1]
        image_data = base64.b64decode(base64_data)

        # Use pyzbar to decode QR code content
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode as qr_decode

            image = Image.open(BytesIO(image_data))
            decoded_objects = qr_decode(image)
            assert len(decoded_objects) == 1

            qr_content = decoded_objects[0].data.decode('utf-8')
            assert qr_content == expected_deep_link
        except ImportError:
            # If pyzbar isn't available, skip this detailed check
            pytest.skip("pyzbar not available for QR code decoding test")


# =============================================================================
# TELEGRAM LINKING FLOW TESTS
# =============================================================================


class TestTelegramLinkingFlow:
    """Tests for the Telegram account linking flow."""

    def test_valid_token_links_successfully(self):
        """Valid token creates ChefTelegramLink."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()
        chef.id = 1

        telegram_user_id = 123456789
        telegram_user_info = {'username': 'test_telegram_user', 'first_name': 'Test'}

        mock_token = MagicMock()
        mock_token.is_valid = True
        mock_token.chef = chef
        mock_token.used = False

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken, \
             patch('chefs.services.telegram_link_service.ChefTelegramLink') as MockLink, \
             patch('chefs.services.telegram_link_service.ChefTelegramSettings') as MockSettings:

            MockToken.objects.get.return_value = mock_token
            MockLink.objects.filter.return_value.first.return_value = None

            result = service.process_start_command(
                telegram_user_id=telegram_user_id,
                telegram_user=telegram_user_info,
                token="valid_test_token",
            )

            # Should succeed
            assert result is True

            # Link should be created
            MockLink.objects.create.assert_called_once()
            create_kwargs = MockLink.objects.create.call_args[1]
            assert create_kwargs['chef'] == chef
            assert create_kwargs['telegram_user_id'] == telegram_user_id
            assert create_kwargs['telegram_username'] == 'test_telegram_user'
            assert create_kwargs['telegram_first_name'] == 'Test'

            # Token should be marked as used
            assert mock_token.used is True
            mock_token.save.assert_called_once()

            # Settings should be created
            MockSettings.objects.get_or_create.assert_called_once_with(chef=chef)

    def test_expired_token_fails(self):
        """Expired token returns False and doesn't create link."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()

        mock_token = MagicMock()
        mock_token.is_valid = False  # Expired
        mock_token.used = False

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken, \
             patch('chefs.services.telegram_link_service.ChefTelegramLink') as MockLink:

            MockToken.objects.get.return_value = mock_token

            result = service.process_start_command(
                telegram_user_id=123456789,
                telegram_user={'username': 'test'},
                token="expired_token",
            )

            # Should fail
            assert result is False

            # No link should be created
            MockLink.objects.create.assert_not_called()

    def test_used_token_fails(self):
        """Already-used token returns False and doesn't create link."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()

        mock_token = MagicMock()
        mock_token.is_valid = False  # Used tokens are invalid
        mock_token.used = True

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken, \
             patch('chefs.services.telegram_link_service.ChefTelegramLink') as MockLink:

            MockToken.objects.get.return_value = mock_token

            result = service.process_start_command(
                telegram_user_id=123456789,
                telegram_user={'username': 'test'},
                token="used_token",
            )

            # Should fail
            assert result is False

            # No link should be created
            MockLink.objects.create.assert_not_called()

    def test_nonexistent_token_fails(self):
        """Non-existent token returns False."""
        from chefs.services.telegram_link_service import TelegramLinkService
        from chefs.models.telegram_integration import TelegramLinkToken

        service = TelegramLinkService()

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken:
            MockToken.DoesNotExist = TelegramLinkToken.DoesNotExist
            MockToken.objects.get.side_effect = TelegramLinkToken.DoesNotExist

            result = service.process_start_command(
                telegram_user_id=123456789,
                telegram_user={'username': 'test'},
                token="nonexistent_token",
            )

            # Should fail
            assert result is False

    def test_already_linked_telegram_user_fails(self):
        """Same Telegram user can't link to multiple chefs."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()

        telegram_user_id = 123456789
        chef1 = MagicMock()
        chef2 = MagicMock()

        mock_token = MagicMock()
        mock_token.is_valid = True
        mock_token.chef = chef2  # Token for chef2

        # Existing link to chef1
        existing_link = MagicMock()
        existing_link.chef = chef1
        existing_link.telegram_user_id = telegram_user_id
        existing_link.is_active = True

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken, \
             patch('chefs.services.telegram_link_service.ChefTelegramLink') as MockLink:

            MockToken.objects.get.return_value = mock_token
            MockLink.objects.filter.return_value.first.return_value = existing_link

            result = service.process_start_command(
                telegram_user_id=telegram_user_id,
                telegram_user={'username': 'test'},
                token="valid_token",
            )

            # Should fail
            assert result is False

            # No new link should be created
            MockLink.objects.create.assert_not_called()

    def test_linking_creates_default_settings(self):
        """ChefTelegramSettings created on successful link."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()

        mock_token = MagicMock()
        mock_token.is_valid = True
        mock_token.chef = chef

        with patch('chefs.services.telegram_link_service.TelegramLinkToken') as MockToken, \
             patch('chefs.services.telegram_link_service.ChefTelegramLink') as MockLink, \
             patch('chefs.services.telegram_link_service.ChefTelegramSettings') as MockSettings:

            MockToken.objects.get.return_value = mock_token
            MockLink.objects.filter.return_value.first.return_value = None

            result = service.process_start_command(
                telegram_user_id=123456789,
                telegram_user={'username': 'test'},
                token="valid_token",
            )

            assert result is True
            MockSettings.objects.get_or_create.assert_called_once_with(chef=chef)


# =============================================================================
# TELEGRAM UNLINK TESTS
# =============================================================================


class TestTelegramUnlink:
    """Tests for the Telegram unlink flow."""

    def test_unlink_sets_inactive(self):
        """Unlink sets is_active=False."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()

        mock_link = MagicMock()
        mock_link.is_active = True
        chef.telegram_link = mock_link

        result = service.unlink(chef)

        # Should succeed
        assert result is True

        # Link should be inactive
        assert mock_link.is_active is False
        mock_link.save.assert_called_once()

    def test_unlink_preserves_record(self):
        """Record still exists after unlink (no delete called)."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()

        mock_link = MagicMock()
        mock_link.is_active = True
        chef.telegram_link = mock_link

        service.unlink(chef)

        # Delete should NOT be called - we preserve the record
        mock_link.delete.assert_not_called()

    def test_unlink_nonexistent_returns_false(self):
        """Unlinking when not linked returns False."""
        from chefs.services.telegram_link_service import TelegramLinkService
        from chefs.models.telegram_integration import ChefTelegramLink

        service = TelegramLinkService()
        chef = MagicMock()

        # Accessing telegram_link raises DoesNotExist
        type(chef).telegram_link = PropertyMock(side_effect=ChefTelegramLink.DoesNotExist)

        result = service.unlink(chef)

        # Should return False
        assert result is False

    def test_unlink_already_inactive_returns_true(self):
        """Unlinking already-inactive link still works (idempotent)."""
        from chefs.services.telegram_link_service import TelegramLinkService

        service = TelegramLinkService()
        chef = MagicMock()

        mock_link = MagicMock()
        mock_link.is_active = False  # Already inactive
        chef.telegram_link = mock_link

        result = service.unlink(chef)

        # Should still succeed (idempotent)
        assert result is True
        mock_link.save.assert_called_once()
