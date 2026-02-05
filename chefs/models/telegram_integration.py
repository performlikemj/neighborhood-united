# chefs/models/telegram_integration.py
"""
Telegram Integration Models.

This module provides:
- ChefTelegramLink: Links a chef account to their Telegram user
- TelegramLinkToken: One-time tokens for the linking flow
- ChefTelegramSettings: Notification preferences for Telegram

Design principles:
- Zero-friction linking via QR code/deep link
- Chef controls all notification settings
- No health data transmitted over Telegram
"""

from datetime import time as dt_time

from django.db import models
from django.utils import timezone


# ═══════════════════════════════════════════════════════════════════════════════
# CHEF TELEGRAM LINK (Account Linking)
# ═══════════════════════════════════════════════════════════════════════════════

class ChefTelegramLink(models.Model):
    """
    Links a chef account to their Telegram user.
    
    Each chef can have at most one active Telegram link.
    Each Telegram user can only be linked to one chef.
    """
    chef = models.OneToOneField(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='telegram_link'
    )
    telegram_user_id = models.BigIntegerField(
        unique=True,
        help_text="Telegram's unique user ID"
    )
    telegram_username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Telegram username (without @)"
    )
    telegram_first_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="User's first name on Telegram"
    )
    linked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the account was linked"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the link is currently active"
    )

    class Meta:
        app_label = 'chefs'
        verbose_name = "Chef Telegram Link"
        verbose_name_plural = "Chef Telegram Links"
        indexes = [
            models.Index(fields=['telegram_user_id']),
        ]

    def __str__(self):
        username = self.telegram_username or self.telegram_user_id
        return f"{self.chef.user.username} <-> @{username}"


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM LINK TOKEN (One-Time Linking Tokens)
# ═══════════════════════════════════════════════════════════════════════════════

class TelegramLinkToken(models.Model):
    """
    One-time token for linking a Telegram account.
    
    Tokens are generated when chef requests to link their account,
    embedded in a QR code / deep link, and consumed when user
    sends /start <token> to the bot.
    """
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='telegram_link_tokens',
        help_text="Chef who generated this token"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text="The one-time token value"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the token was created"
    )
    expires_at = models.DateTimeField(
        help_text="When the token expires"
    )
    used = models.BooleanField(
        default=False,
        help_text="Whether the token has been used"
    )

    class Meta:
        app_label = 'chefs'
        verbose_name = "Telegram Link Token"
        verbose_name_plural = "Telegram Link Tokens"
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        status = "used" if self.used else ("expired" if not self.is_valid else "valid")
        return f"Token for {self.chef.user.username} ({status})"

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (unused and not expired)."""
        return not self.used and timezone.now() < self.expires_at


# ═══════════════════════════════════════════════════════════════════════════════
# CHEF TELEGRAM SETTINGS (Notification Preferences)
# ═══════════════════════════════════════════════════════════════════════════════

class ChefTelegramSettings(models.Model):
    """
    Chef's notification preferences for Telegram.
    
    Controls what types of notifications are sent and when.
    """
    chef = models.OneToOneField(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='telegram_settings'
    )

    # Notification toggles
    notify_new_orders = models.BooleanField(
        default=True,
        help_text="Notify when a new order comes in"
    )
    notify_order_updates = models.BooleanField(
        default=True,
        help_text="Notify on order status changes"
    )
    notify_schedule_reminders = models.BooleanField(
        default=True,
        help_text="Send schedule reminders"
    )
    notify_customer_messages = models.BooleanField(
        default=False,
        help_text="Notify on direct customer messages"
    )

    # Quiet hours
    quiet_hours_start = models.TimeField(
        default=dt_time(22, 0),
        help_text="Start of quiet hours (no notifications)"
    )
    quiet_hours_end = models.TimeField(
        default=dt_time(8, 0),
        help_text="End of quiet hours"
    )
    quiet_hours_enabled = models.BooleanField(
        default=True,
        help_text="Enable quiet hours"
    )

    class Meta:
        app_label = 'chefs'
        verbose_name = "Chef Telegram Settings"
        verbose_name_plural = "Chef Telegram Settings"

    def __str__(self):
        return f"Telegram settings for {self.chef.user.username}"

    def is_quiet_hours(self) -> bool:
        """
        Check if current time is within quiet hours.
        
        Handles both same-day ranges (9am-5pm) and overnight ranges (10pm-8am).
        Returns False if quiet hours are disabled.
        """
        if not self.quiet_hours_enabled:
            return False

        now = timezone.localtime().time()
        start = self.quiet_hours_start
        end = self.quiet_hours_end

        if start <= end:
            # Same day range (e.g., 9am to 5pm)
            return start <= now <= end
        else:
            # Crosses midnight (e.g., 10pm to 8am)
            return now >= start or now <= end
