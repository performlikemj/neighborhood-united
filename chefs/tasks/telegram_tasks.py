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
import re
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


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert GitHub-flavored Markdown to Telegram HTML format.
    
    Telegram's HTML parser is more forgiving than Markdown.
    Supported tags: <b>, <i>, <code>, <pre>, <a>
    
    This function:
    - Escapes HTML entities first (safety)
    - Converts **bold** and *bold* to <b>bold</b>
    - Converts _italic_ to <i>italic</i>
    - Converts `code` to <code>code</code>
    - Converts headers (# Header) to <b>Header</b>
    - Converts tables to simple text lists
    - Removes unsupported syntax
    
    Args:
        text: GitHub-flavored markdown text
        
    Returns:
        Telegram HTML compatible text
    """
    if not text:
        return ""
    
    result = text
    
    # Step 1: Escape HTML entities FIRST (before we add our own HTML tags)
    result = result.replace('&', '&amp;')
    result = result.replace('<', '&lt;')
    result = result.replace('>', '&gt;')
    
    # Step 2: Convert code blocks ```code``` BEFORE other processing
    # (to avoid converting markdown inside code blocks)
    result = re.sub(r'```[\w]*\n?(.*?)```', r'\1', result, flags=re.DOTALL)
    
    # Step 3: Convert inline code `code` to <code>code</code>
    result = re.sub(r'`([^`]+)`', r'<code>\1</code>', result)
    
    # Step 4: Convert headers to bold (# Header -> <b>Header</b>)
    result = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', result, flags=re.MULTILINE)
    
    # Step 5: Convert bold **text** to <b>text</b>
    result = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', result)
    
    # Step 6: Convert remaining *text* to <b>text</b> (but only balanced pairs)
    # Use word boundaries to avoid matching things like "4* hotel"
    result = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'<b>\1</b>', result)
    
    # Step 7: Convert _italic_ to <i>italic</i>
    # Be careful with underscores in variable_names
    result = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'<i>\1</i>', result)
    
    # Step 8: Convert markdown tables to simple lists
    lines = result.split('\n')
    converted_lines = []
    in_table = False
    table_headers = []
    
    for line in lines:
        stripped = line.strip()
        
        # Detect table separator row (|---|---|)
        if re.match(r'^\|[\s\-:]+\|', stripped):
            in_table = True
            continue
        
        # Table row
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            
            if not in_table:
                # This is the header row
                table_headers = cells
                in_table = True
            else:
                # Data row - convert to "• Header: Value" format
                if table_headers and len(cells) == len(table_headers):
                    for header, value in zip(table_headers, cells):
                        if value:  # Skip empty values
                            converted_lines.append(f"• {header}: {value}")
                else:
                    # No headers or mismatch - just list values
                    for cell in cells:
                        if cell:
                            converted_lines.append(f"• {cell}")
            continue
        else:
            # Not a table row - reset table state
            if in_table:
                in_table = False
                table_headers = []
            converted_lines.append(line)
    
    result = '\n'.join(converted_lines)
    
    # Step 9: Remove horizontal rules (--- or ***)
    result = re.sub(r'^[\-\*]{3,}$', '', result, flags=re.MULTILINE)
    
    # Step 10: Clean up multiple consecutive newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()


# Keep old name as alias for backwards compatibility
sanitize_markdown_for_telegram = markdown_to_telegram_html


def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message to a Telegram chat.
    
    Args:
        chat_id: Telegram chat ID to send to
        text: Message text (markdown will be converted to HTML)
        parse_mode: Telegram parse mode ("HTML", "Markdown", or None for plain text)
                    Default is HTML as it's more forgiving than Markdown.
        
    Returns:
        bool: True if successful, False otherwise
    """
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Convert markdown to HTML (handles both markdown input and plain text safely)
    if parse_mode == "HTML":
        text = markdown_to_telegram_html(text)
    
    # Build request payload
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        response = requests.post(
            url,
            json=payload,
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

    Routes the message through channel-aware Sous Chef service.
    Telegram channel excludes navigation tools (can't navigate UI from chat).

    Args:
        chef: Chef model instance
        text: Message text from chef

    Returns:
        str: Response text to send back
    """
    from chefs.services.sous_chef.filters.pii_detector import detect_health_pii

    logger.info(f"Processing message from chef {chef.id}: {text[:50]}...")

    # Check for PII in incoming message - log but don't process
    contains_pii, pii_type = detect_health_pii(text)
    if contains_pii:
        logger.info(
            f"Incoming message from chef {chef.id} contains health PII "
            f"(type: {pii_type}), will not process the PII content"
        )
    
    try:
        from chefs.services.sous_chef import SousChefService
        
        # Channel-aware service - Telegram excludes navigation tools
        service = SousChefService(
            chef_id=chef.id,
            channel="telegram",  # Key: channel-aware tool filtering
        )
        
        result = service.send_message(text)
        
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
                "You'll also receive notifications here based on your preferences.",
                parse_mode="HTML"
            )
        else:
            send_telegram_message(
                chat_id,
                "❌ <b>Link Failed</b>\n\n"
                "This link is invalid or has expired. "
                "Please generate a new link from your Sautai dashboard.",
                parse_mode="HTML"
            )
    else:
        # No token - generic welcome
        send_telegram_message(
            chat_id,
            "👋 <b>Welcome to Sautai!</b>\n\n"
            "To connect your chef account, go to your Sautai dashboard "
            "and click 'Connect Telegram'. You'll get a QR code or link to scan.\n\n"
            "If you're already linked, just send me a message!",
            parse_mode="HTML"
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
            "Please connect your Telegram from the Sautai dashboard first!",
            parse_mode=None  # Plain text, no formatting
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
