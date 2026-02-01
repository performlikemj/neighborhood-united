"""
Proactive Settings API endpoints.

Allows chefs to configure their notification preferences
for the proactive engine (birthdays, follow-ups, etc).
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef, ChefProactiveSettings, ChefOnboardingState

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """Get the Chef instance for the authenticated user."""
    try:
        chef = Chef.objects.select_related('user').get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access proactive settings."},
            status=403
        )


def _serialize_proactive_settings(settings: ChefProactiveSettings) -> dict:
    """Serialize proactive settings for API response."""
    return {
        # Master switch
        "enabled": settings.enabled,

        # Feature toggles
        "notify_birthdays": settings.notify_birthdays,
        "notify_anniversaries": settings.notify_anniversaries,
        "notify_followups": settings.notify_followups,
        "notify_todos": settings.notify_todos,
        "notify_seasonal": settings.notify_seasonal,
        "notify_milestones": settings.notify_milestones,

        # Lead days
        "birthday_lead_days": settings.birthday_lead_days,
        "anniversary_lead_days": settings.anniversary_lead_days,
        "followup_threshold_days": settings.followup_threshold_days,

        # Frequency
        "notification_frequency": settings.notification_frequency,

        # Channels
        "channel_in_app": settings.channel_in_app,
        "channel_email": settings.channel_email,
        "channel_push": settings.channel_push,

        # Quiet hours
        "quiet_hours_enabled": settings.quiet_hours_enabled,
        "quiet_hours_start": settings.quiet_hours_start.strftime('%H:%M') if settings.quiet_hours_start else None,
        "quiet_hours_end": settings.quiet_hours_end.strftime('%H:%M') if settings.quiet_hours_end else None,
        "quiet_hours_timezone": settings.quiet_hours_timezone,

        # Timestamps
        "created_at": settings.created_at.isoformat(),
        "updated_at": settings.updated_at.isoformat(),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def proactive_get(request):
    """
    GET /chefs/api/me/proactive/

    Get the chef's proactive notification settings.
    Auto-creates with defaults if it doesn't exist.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    settings = ChefProactiveSettings.get_or_create_for_chef(chef)

    return Response({
        "status": "success",
        "settings": _serialize_proactive_settings(settings),
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def proactive_update(request):
    """
    PUT/PATCH /chefs/api/me/proactive/

    Update proactive notification settings.

    Request body (all fields optional for PATCH):
    {
        "enabled": true,
        "notify_birthdays": true,
        "notify_anniversaries": true,
        "notify_followups": true,
        "notify_todos": true,
        "notify_seasonal": true,
        "notify_milestones": true,
        "birthday_lead_days": 7,
        "anniversary_lead_days": 7,
        "followup_threshold_days": 30,
        "notification_frequency": "daily",
        "channel_in_app": true,
        "channel_email": false,
        "channel_push": false,
        "quiet_hours_enabled": false,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "quiet_hours_timezone": "America/New_York"
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    settings = ChefProactiveSettings.get_or_create_for_chef(chef)

    # Track if this is first time enabling
    was_disabled = not settings.enabled

    # Allowed fields for update
    boolean_fields = [
        'enabled',
        'notify_birthdays',
        'notify_anniversaries',
        'notify_followups',
        'notify_todos',
        'notify_seasonal',
        'notify_milestones',
        'channel_in_app',
        'channel_email',
        'channel_push',
        'quiet_hours_enabled',
    ]

    integer_fields = [
        'birthday_lead_days',
        'anniversary_lead_days',
        'followup_threshold_days',
    ]

    string_fields = [
        'notification_frequency',
        'quiet_hours_timezone',
    ]

    time_fields = [
        'quiet_hours_start',
        'quiet_hours_end',
    ]

    updated_fields = []

    # Update boolean fields
    for field in boolean_fields:
        if field in request.data:
            setattr(settings, field, bool(request.data[field]))
            updated_fields.append(field)

    # Update integer fields
    for field in integer_fields:
        if field in request.data:
            try:
                setattr(settings, field, int(request.data[field]))
                updated_fields.append(field)
            except (ValueError, TypeError):
                return Response(
                    {"error": f"Invalid value for {field}: must be an integer"},
                    status=400
                )

    # Update string fields
    for field in string_fields:
        if field in request.data:
            value = request.data[field]
            if field == 'notification_frequency':
                valid = [c[0] for c in ChefProactiveSettings.FREQUENCY_CHOICES]
                if value not in valid:
                    return Response(
                        {"error": f"Invalid frequency. Valid options: {valid}"},
                        status=400
                    )
            setattr(settings, field, value)
            updated_fields.append(field)

    # Update time fields
    from datetime import time as dt_time
    for field in time_fields:
        if field in request.data:
            value = request.data[field]
            if value:
                try:
                    # Parse "HH:MM" format
                    parts = value.split(':')
                    parsed_time = dt_time(int(parts[0]), int(parts[1]))
                    setattr(settings, field, parsed_time)
                except (ValueError, IndexError):
                    return Response(
                        {"error": f"Invalid time format for {field}. Use HH:MM format."},
                        status=400
                    )
            else:
                setattr(settings, field, None)
            updated_fields.append(field)

    if updated_fields:
        settings.save(update_fields=updated_fields + ['updated_at'])
        logger.info(f"Chef {chef.id} updated proactive settings: {updated_fields}")

        # Track milestone if enabling for first time
        if was_disabled and settings.enabled and 'enabled' in updated_fields:
            state = ChefOnboardingState.get_or_create_for_chef(chef)
            state.record_milestone('proactive_enabled')

    return Response({
        "status": "success",
        "updated_fields": updated_fields,
        "settings": _serialize_proactive_settings(settings),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proactive_disable(request):
    """
    POST /chefs/api/me/proactive/disable/

    Quick disable - turns off the master switch.
    All other settings are preserved.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    settings = ChefProactiveSettings.get_or_create_for_chef(chef)

    if settings.enabled:
        settings.enabled = False
        settings.save(update_fields=['enabled', 'updated_at'])
        logger.info(f"Chef {chef.id} disabled proactive notifications")

    return Response({
        "status": "success",
        "message": "Proactive notifications disabled",
        "settings": _serialize_proactive_settings(settings),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proactive_enable(request):
    """
    POST /chefs/api/me/proactive/enable/

    Quick enable - turns on the master switch.
    All other settings remain as configured.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    settings = ChefProactiveSettings.get_or_create_for_chef(chef)

    was_disabled = not settings.enabled

    if not settings.enabled:
        settings.enabled = True
        settings.save(update_fields=['enabled', 'updated_at'])
        logger.info(f"Chef {chef.id} enabled proactive notifications")

        # Track milestone if first time enabling
        if was_disabled:
            state = ChefOnboardingState.get_or_create_for_chef(chef)
            state.record_milestone('proactive_enabled')

    return Response({
        "status": "success",
        "message": "Proactive notifications enabled",
        "settings": _serialize_proactive_settings(settings),
    })
