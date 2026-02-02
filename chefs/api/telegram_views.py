# chefs/api/telegram_views.py
"""
Telegram Integration API Endpoints.

Provides endpoints for:
- POST /chefs/api/telegram/generate-link/ - Generate QR code + deep link
- POST /chefs/api/telegram/unlink/ - Unlink Telegram account
- GET /chefs/api/telegram/status/ - Get link status and settings
- PATCH /chefs/api/telegram/settings/ - Update notification settings

All endpoints require an authenticated chef account.
"""

import json
import logging
from datetime import time as dt_time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from chefs.models import Chef
from chefs.models.telegram_integration import ChefTelegramLink, ChefTelegramSettings
from chefs.services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """
    Get the Chef instance for the authenticated user.
    Returns (chef, None) on success, (None, JsonResponse) on failure.
    """
    try:
        chef = Chef.objects.get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, JsonResponse(
            {"error": "Not a chef. Only chefs can access this endpoint."},
            status=403
        )


def _serialize_settings(settings):
    """Serialize ChefTelegramSettings to dict."""
    return {
        'notify_new_orders': settings.notify_new_orders,
        'notify_order_updates': settings.notify_order_updates,
        'notify_schedule_reminders': settings.notify_schedule_reminders,
        'notify_customer_messages': settings.notify_customer_messages,
        'quiet_hours_start': settings.quiet_hours_start.strftime('%H:%M'),
        'quiet_hours_end': settings.quiet_hours_end.strftime('%H:%M'),
        'quiet_hours_enabled': settings.quiet_hours_enabled,
    }


@csrf_exempt
@require_http_methods(["POST"])
def telegram_generate_link(request):
    """
    POST /chefs/api/telegram/generate-link/
    
    Generates a one-time link token for connecting Telegram.
    Returns QR code data URL and deep link.
    
    Response:
    {
        "deep_link": "https://t.me/SautaiChefBot?start=TOKEN",
        "qr_code": "data:image/png;base64,...",
        "expires_at": "2024-01-01T12:00:00Z"
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    try:
        service = TelegramLinkService()
        token = service.generate_link_token(chef)
        
        return JsonResponse({
            'deep_link': service.get_deep_link(token.token),
            'qr_code': service.get_qr_code_data_url(token.token),
            'expires_at': token.expires_at.isoformat(),
        })
    except Exception as e:
        logger.exception(f"Error generating Telegram link for chef {chef.id}: {e}")
        return JsonResponse(
            {"error": "Failed to generate link. Please try again."},
            status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def telegram_unlink(request):
    """
    POST /chefs/api/telegram/unlink/
    
    Unlinks the chef's Telegram account.
    Sets is_active=False on the ChefTelegramLink.
    
    Response:
    {
        "success": true
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    try:
        service = TelegramLinkService()
        success = service.unlink(chef)
        
        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse(
                {"error": "Telegram account not linked."},
                status=400
            )
    except Exception as e:
        logger.exception(f"Error unlinking Telegram for chef {chef.id}: {e}")
        return JsonResponse(
            {"error": "Failed to unlink. Please try again."},
            status=500
        )


@csrf_exempt
@require_http_methods(["GET"])
def telegram_status(request):
    """
    GET /chefs/api/telegram/status/
    
    Returns the current Telegram link status and settings.
    
    Response when linked:
    {
        "linked": true,
        "telegram_username": "username",
        "telegram_first_name": "Name",
        "linked_at": "2024-01-01T12:00:00Z",
        "settings": {
            "notify_new_orders": true,
            ...
        }
    }
    
    Response when not linked:
    {
        "linked": false
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    try:
        link = chef.telegram_link
        
        # Check if link is active
        if not link.is_active:
            return JsonResponse({'linked': False})
        
        # Get settings
        try:
            settings = chef.telegram_settings
            settings_data = _serialize_settings(settings)
        except ChefTelegramSettings.DoesNotExist:
            settings_data = None
        
        return JsonResponse({
            'linked': True,
            'telegram_username': link.telegram_username,
            'telegram_first_name': link.telegram_first_name,
            'linked_at': link.linked_at.isoformat(),
            'settings': settings_data,
        })
    except ChefTelegramLink.DoesNotExist:
        return JsonResponse({'linked': False})
    except Exception as e:
        logger.exception(f"Error fetching Telegram status for chef {chef.id}: {e}")
        return JsonResponse(
            {"error": "Failed to fetch status. Please try again."},
            status=500
        )


@csrf_exempt
@require_http_methods(["PATCH"])
def telegram_settings(request):
    """
    PATCH /chefs/api/telegram/settings/
    
    Updates Telegram notification settings.
    
    Request body (all fields optional):
    {
        "notify_new_orders": true,
        "notify_order_updates": true,
        "notify_schedule_reminders": true,
        "notify_customer_messages": false,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "quiet_hours_enabled": true
    }
    
    Response:
    {
        "settings": { ... }
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    # Parse JSON body
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "Invalid JSON body."},
            status=400
        )

    # Get settings object
    try:
        settings = ChefTelegramSettings.objects.get(chef=chef)
    except ChefTelegramSettings.DoesNotExist:
        return JsonResponse(
            {"error": "Telegram not linked. Link your account first."},
            status=404
        )

    # Update boolean settings
    boolean_fields = [
        'notify_new_orders',
        'notify_order_updates',
        'notify_schedule_reminders',
        'notify_customer_messages',
        'quiet_hours_enabled',
    ]
    
    for field in boolean_fields:
        if field in data:
            setattr(settings, field, bool(data[field]))

    # Update time fields
    if 'quiet_hours_start' in data:
        try:
            h, m = map(int, data['quiet_hours_start'].split(':'))
            settings.quiet_hours_start = dt_time(h, m)
        except (ValueError, AttributeError):
            pass  # Ignore invalid time format

    if 'quiet_hours_end' in data:
        try:
            h, m = map(int, data['quiet_hours_end'].split(':'))
            settings.quiet_hours_end = dt_time(h, m)
        except (ValueError, AttributeError):
            pass  # Ignore invalid time format

    # Save and return
    settings.save()
    
    return JsonResponse({
        'settings': _serialize_settings(settings)
    })
