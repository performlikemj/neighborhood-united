"""
Telegram Celery Tasks - Phase 4.

Async processing of Telegram updates:
- Message routing to linked chefs
- /start command handling for account linking
- Sending responses back to Telegram

Design principles:
- No health data transmitted
- Graceful error handling
- Idempotent where possible
"""

import logging
from typing import Optional

import requests
from celery import shared_task
from django.conf import settings

from chefs.models.telegram_integration import (
    ChefTelegramLink,
    TelegramLinkToken,
    ChefTelegramSettings,
)
from chefs.services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)


# =============================================================================
# TELEGRAM API HELPERS
# =============================================================================


def send_telegram_message(chat_id: int, text: str) -> bool:
    """
    Send a message to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID to send to
        text: Message text
        
    Returns:
        bool: True if successful, False otherwise
    """
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
        return False


# =============================================================================
# MESSAGE PROCESSING
# =============================================================================


def process_chef_message(chef, text: str) -> str:
    """
    Process a message from a chef and generate a response.
    
    Routes the message through Sous Chef AI assistant in general mode
    (no specific family context).
    
    Args:
        chef: Chef model instance
        text: Message text from chef
        
    Returns:
        str: Response text to send back
    """
    logger.info(f"Processing message from chef {chef.id}: {text[:50]}...")
    
    try:
        from meals.sous_chef_assistant import SousChefAssistant
        
        # General mode - no family context for Telegram
        assistant = SousChefAssistant(
            chef_id=chef.id,
            family_id=None,
            family_type=None
        )
        
        result = assistant.send_message(text)
        
        if result.get("status") == "success":
            return result.get("message", "I processed your request but have nothing to say.")
        else:
            logger.error(f"Sous Chef error for chef {chef.id}: {result.get('message')}")
            return "Sorry, I ran into an issue. Please try again or check the dashboard."
            
    except Exception as e:
        logger.error(f"Failed to process message for chef {chef.id}: {e}")
        return "Sorry, something went wrong. Please try again later or use the dashboard."


def filter_sensitive_data(response: str) -> str:
    """
    Remove any customer health/dietary info from response.
    
    For MVP, we rely on the Sous Chef prompt to not include sensitive data.
    This is a safety net for future implementations.
    
    Args:
        response: Raw response text
        
    Returns:
        str: Filtered response text
    """
    # TODO: Implement pattern matching for sensitive data
    # For now, pass through as-is
    return response


# =============================================================================
# COMMAND HANDLERS
# =============================================================================


def handle_start_command(
    telegram_user_id: int,
    telegram_user: dict,
    token: Optional[str],
    chat_id: int,
) -> None:
    """
    Handle /start command from Telegram.
    
    If token is provided, attempt to link the account.
    Otherwise, send a welcome/info message.
    
    Args:
        telegram_user_id: Telegram's unique user ID
        telegram_user: Dict with user info (username, first_name, etc.)
        token: Optional linking token from /start <token>
        chat_id: Chat ID to send response to
    """
    if token:
        # Attempt to link account
        service = TelegramLinkService()
        success = service.process_start_command(
            telegram_user_id=telegram_user_id,
            telegram_user=telegram_user,
            token=token,
        )
        
        if success:
            first_name = telegram_user.get('first_name', 'Chef')
            send_telegram_message(
                chat_id,
                f"✅ <b>Welcome, {first_name}!</b>\n\n"
                "Your Telegram account is now linked to Sautai. "
                "I'm your Sous Chef assistant - ask me anything about your orders, "
                "schedule, or just say hi! 👋\n\n"
                "You'll also receive notifications here based on your preferences."
            )
        else:
            send_telegram_message(
                chat_id,
                "❌ <b>Link Failed</b>\n\n"
                "This link is invalid or has expired. "
                "Please generate a new link from your Sautai dashboard."
            )
    else:
        # No token - generic welcome
        send_telegram_message(
            chat_id,
            "👋 <b>Welcome to Sautai!</b>\n\n"
            "To connect your chef account, go to your Sautai dashboard "
            "and click 'Connect Telegram'. You'll get a QR code or link to scan.\n\n"
            "If you're already linked, just send me a message!"
        )


def handle_regular_message(
    telegram_user_id: int,
    chat_id: int,
    text: str,
) -> None:
    """
    Handle a regular message from a linked chef.
    
    Looks up the chef by their Telegram user ID and processes the message
    through the Sous Chef assistant.
    
    Args:
        telegram_user_id: Telegram's unique user ID
        chat_id: Chat ID to send response to
        text: Message text
    """
    # Find linked chef
    try:
        link = ChefTelegramLink.objects.get(
            telegram_user_id=telegram_user_id,
            is_active=True,
        )
    except ChefTelegramLink.DoesNotExist:
        send_telegram_message(
            chat_id,
            "🤔 I don't recognize this account.\n\n"
            "Please connect your Telegram from the Sautai dashboard first!"
        )
        return
    
    chef = link.chef
    
    # Process with Sous Chef
    response = process_chef_message(chef, text)
    
    # Filter sensitive data (safety net)
    safe_response = filter_sensitive_data(response)
    
    # Send response
    send_telegram_message(chat_id, safe_response)


# =============================================================================
# MAIN CELERY TASK
# =============================================================================


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_telegram_update(self, update: dict) -> None:
    """
    Process incoming Telegram update.
    
    This is the main entry point for all Telegram updates.
    Routes to appropriate handler based on update type.
    
    Args:
        update: Telegram Update object as dict
    """
    update_id = update.get('update_id', 'unknown')
    logger.info(f"Processing Telegram update {update_id}")
    
    # Handle message updates
    message = update.get('message', {})
    
    if not message:
        # Not a message update (could be callback_query, etc.)
        logger.debug(f"Non-message update {update_id}, skipping")
        return
    
    # Extract message details
    from_user = message.get('from', {})
    telegram_user_id = from_user.get('id')
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '')
    
    if not telegram_user_id or not chat_id:
        logger.warning(f"Update {update_id} missing user or chat ID")
        return
    
    logger.info(
        f"Message from Telegram user {telegram_user_id} in chat {chat_id}: "
        f"{text[:50] if text else '(no text)'}..."
    )
    
    # Handle /start command (with or without token)
    if text.startswith('/start'):
        parts = text.split(' ', 1)
        token = parts[1] if len(parts) > 1 else None
        handle_start_command(telegram_user_id, from_user, token, chat_id)
        return
    
    # Handle regular messages
    if text:
        handle_regular_message(telegram_user_id, chat_id, text)
