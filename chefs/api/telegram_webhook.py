"""
Telegram Webhook Endpoint - Phase 4.

Receives updates from Telegram via webhook and queues them for processing.

Security:
- Validates X-Telegram-Bot-Api-Secret-Token header on every request
- Returns 403 for invalid/missing tokens
- Returns 400 for malformed JSON

Design:
- Fast acknowledgment (200 OK) after queueing
- Async processing via Celery task
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def validate_telegram_request(request) -> bool:
    """
    Validate that the request came from Telegram.
    
    Telegram sends the secret token in the X-Telegram-Bot-Api-Secret-Token header
    when configured via setWebhook with secret_token parameter.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        bool: True if valid, False otherwise
    """
    expected_token = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', None)
    
    if not expected_token:
        logger.error("TELEGRAM_WEBHOOK_SECRET not configured")
        return False
    
    received_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    
    if not received_token:
        logger.warning("Telegram webhook request missing secret token")
        return False
    
    return received_token == expected_token


@csrf_exempt
@require_POST
def telegram_webhook(request):
    """
    Receive updates from Telegram.
    
    This endpoint is called by Telegram whenever there's an update
    (new message, callback query, etc.)
    
    Flow:
    1. Validate secret token header
    2. Parse JSON body
    3. Queue update for async processing
    4. Return 200 OK immediately
    
    Returns:
        200: Update accepted (even if processing fails - we don't want retries)
        400: Invalid JSON
        403: Invalid/missing secret token
    """
    # Security: Validate the secret token
    if not validate_telegram_request(request):
        return HttpResponse(status=403)
    
    # Parse JSON body
    try:
        update = json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Invalid JSON in Telegram webhook: {e}")
        return HttpResponse(status=400)
    
    # Log the update for debugging (careful with PII in production)
    update_id = update.get('update_id', 'unknown')
    logger.info(f"Received Telegram update {update_id}")
    
    # Queue for async processing
    # Import here to avoid circular imports and allow mocking in tests
    from chefs.tasks.telegram_tasks import process_telegram_update
    
    # Check if we're in eager mode (tests) or should use delay
    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        # In test mode, run synchronously
        process_telegram_update(update)
    else:
        # In production, queue the task
        process_telegram_update.delay(update)
    
    # Fast ack - Telegram expects 200 within a few seconds
    return HttpResponse(status=200)
