# chefs/services/telegram_link_service.py
"""
Telegram Link Service.

This service handles:
- Generating one-time link tokens for QR codes / deep links
- Processing /start commands to complete account linking
- Unlinking Telegram accounts

Design principles:
- Zero-friction linking via QR code or deep link
- Each chef can have one active Telegram link
- Each Telegram user can only link to one chef
"""

import base64
import secrets
from datetime import timedelta
from io import BytesIO

import qrcode
from django.conf import settings
from django.utils import timezone

from chefs.models.telegram_integration import (
    ChefTelegramLink,
    TelegramLinkToken,
    ChefTelegramSettings,
)


class TelegramLinkService:
    """Service for managing Telegram account linking."""

    # Bot username - can be overridden in Django settings
    BOT_USERNAME = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'SautaiChefBot')
    
    # Token expiration time in minutes
    TOKEN_EXPIRY_MINUTES = 10

    def generate_link_token(self, chef) -> TelegramLinkToken:
        """
        Generate a one-time linking token.
        
        Creates a cryptographically secure token that expires in 10 minutes.
        The token is embedded in the deep link / QR code for the chef to scan.
        
        Args:
            chef: The Chef instance to create a token for
            
        Returns:
            TelegramLinkToken: The newly created token
        """
        token_value = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=self.TOKEN_EXPIRY_MINUTES)
        
        return TelegramLinkToken.objects.create(
            chef=chef,
            token=token_value,
            expires_at=expires_at,
        )

    def get_deep_link(self, token: str) -> str:
        """
        Generate Telegram deep link.
        
        Creates a link in the format: https://t.me/BotUsername?start=TOKEN
        When clicked, opens Telegram and sends /start TOKEN to the bot.
        
        Args:
            token: The one-time token string
            
        Returns:
            str: The deep link URL
        """
        return f"https://t.me/{self.BOT_USERNAME}?start={token}"

    def get_qr_code_data_url(self, token: str) -> str:
        """
        Generate QR code as base64 data URL.
        
        Creates a QR code containing the deep link, encoded as a base64
        PNG data URL for direct embedding in HTML.
        
        Args:
            token: The one-time token string
            
        Returns:
            str: Data URL in format "data:image/png;base64,..."
        """
        deep_link = self.get_deep_link(token)
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(deep_link)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode as base64
        b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{b64_data}"

    def process_start_command(
        self,
        telegram_user_id: int,
        telegram_user: dict,
        token: str,
    ) -> bool:
        """
        Process /start command with token from Telegram.
        
        Validates the token, checks for existing links, and creates
        a new ChefTelegramLink if everything is valid.
        
        Args:
            telegram_user_id: Telegram's unique user ID
            telegram_user: Dict with 'username' and 'first_name' from Telegram
            token: The token string from /start command
            
        Returns:
            bool: True if linked successfully, False otherwise
        """
        # Find the token
        try:
            link_token = TelegramLinkToken.objects.get(token=token)
        except TelegramLinkToken.DoesNotExist:
            return False
        
        # Check if token is valid (not used and not expired)
        if not link_token.is_valid:
            return False
        
        # Check if this Telegram user is already linked to any chef
        existing_link = ChefTelegramLink.objects.filter(
            telegram_user_id=telegram_user_id,
            is_active=True,
        ).first()
        
        if existing_link:
            return False  # Already linked to another chef
        
        # Create the link
        ChefTelegramLink.objects.create(
            chef=link_token.chef,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_user.get('username'),
            telegram_first_name=telegram_user.get('first_name'),
        )
        
        # Mark token as used
        link_token.used = True
        link_token.save()
        
        # Create default settings for the chef (if they don't exist)
        ChefTelegramSettings.objects.get_or_create(chef=link_token.chef)
        
        return True

    def unlink(self, chef) -> bool:
        """
        Unlink chef's Telegram account.
        
        Sets is_active=False on the ChefTelegramLink, preserving the record
        for audit purposes. This is a soft-delete approach.
        
        Args:
            chef: The Chef instance to unlink
            
        Returns:
            bool: True if successfully unlinked, False if no link existed
        """
        try:
            link = chef.telegram_link
            link.is_active = False
            link.save()
            return True
        except ChefTelegramLink.DoesNotExist:
            return False
