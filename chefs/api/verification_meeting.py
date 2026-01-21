"""
Chef Verification Meeting API Endpoints

Provides endpoints for:
- Chefs: View meeting requirements and their status
- Chefs: Mark meeting as scheduled (self-service after booking via Calendly)
- Admin: Configure Calendly settings
- Admin: Mark meetings as complete
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime

from chefs.models import Chef, PlatformCalendlyConfig, ChefVerificationMeeting
from custom_auth.models import UserRole


def _get_chef_or_403(request):
    """Helper to get chef for current user."""
    try:
        chef = Chef.objects.get(user=request.user)
    except Chef.DoesNotExist:
        return None, Response({'detail': 'Not a chef'}, status=status.HTTP_404_NOT_FOUND)

    try:
        user_role = UserRole.objects.get(user=request.user)
        if not user_role.is_chef or user_role.current_role != 'chef':
            return None, Response(
                {'detail': 'Switch to chef mode to access this feature'},
                status=status.HTTP_403_FORBIDDEN
            )
    except UserRole.DoesNotExist:
        return None, Response(
            {'detail': 'Switch to chef mode to access this feature'},
            status=status.HTTP_403_FORBIDDEN
        )

    return chef, None


# ============================================================================
# Public Endpoints
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def calendly_config_public(request):
    """
    GET /chefs/api/calendly-config/

    Public endpoint returning whether the Calendly feature is enabled.
    Does NOT expose the actual URL to unauthenticated users.
    """
    config = PlatformCalendlyConfig.get_config()

    if not config or not config.enabled:
        return Response({
            'enabled': False,
            'is_required': False,
        })

    return Response({
        'enabled': True,
        'meeting_title': config.meeting_title,
        'meeting_description': config.meeting_description,
        'is_required': config.is_required,
    })


# ============================================================================
# Chef Endpoints
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chef_meeting_status(request):
    """
    GET /chefs/api/me/verification-meeting/

    Returns the current chef's verification meeting status and config.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    config = PlatformCalendlyConfig.get_config()

    # Get or create meeting record
    meeting, _ = ChefVerificationMeeting.objects.get_or_create(chef=chef)

    return Response({
        'feature_enabled': bool(config and config.enabled),
        'is_required': bool(config and config.is_required),
        'calendly_url': config.calendly_url if config else None,
        'meeting_title': config.meeting_title if config else None,
        'meeting_description': config.meeting_description if config else None,
        'status': meeting.status,
        'scheduled_at': meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
        'completed_at': meeting.completed_at.isoformat() if meeting.completed_at else None,
        'is_complete': meeting.status == 'completed',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chef_mark_scheduled(request):
    """
    POST /chefs/api/me/verification-meeting/schedule/

    Chef marks their meeting as scheduled (after booking via Calendly).
    Optional: Include scheduled_at datetime in ISO format.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    meeting, _ = ChefVerificationMeeting.objects.get_or_create(chef=chef)

    # Parse optional scheduled_at datetime
    scheduled_at = request.data.get('scheduled_at')
    if scheduled_at:
        scheduled_at = parse_datetime(scheduled_at)

    meeting.mark_as_scheduled(scheduled_time=scheduled_at)

    return Response({
        'status': meeting.status,
        'scheduled_at': meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
        'message': 'Meeting marked as scheduled'
    })


# ============================================================================
# Admin Endpoints
# ============================================================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAdminUser])
def admin_calendly_config(request):
    """
    GET/PUT /chefs/api/admin/calendly-config/

    Admin endpoint to view/update Calendly configuration.
    """
    if request.method == 'GET':
        config = PlatformCalendlyConfig.get_config()
        if not config:
            return Response({
                'enabled': False,
                'calendly_url': '',
                'meeting_title': 'Chef Verification Call',
                'meeting_description': '',
                'is_required': True,
            })

        return Response({
            'enabled': config.enabled,
            'calendly_url': config.calendly_url,
            'meeting_title': config.meeting_title,
            'meeting_description': config.meeting_description,
            'is_required': config.is_required,
        })

    elif request.method == 'PUT':
        # Get or create config
        config = PlatformCalendlyConfig.get_config()
        if not config:
            config = PlatformCalendlyConfig(
                calendly_url=request.data.get('calendly_url', ''),
                meeting_title=request.data.get('meeting_title', 'Chef Verification Call'),
            )

        # Update fields
        if 'enabled' in request.data:
            config.enabled = request.data['enabled']
        if 'calendly_url' in request.data:
            config.calendly_url = request.data['calendly_url']
        if 'meeting_title' in request.data:
            config.meeting_title = request.data['meeting_title']
        if 'meeting_description' in request.data:
            config.meeting_description = request.data['meeting_description']
        if 'is_required' in request.data:
            config.is_required = request.data['is_required']

        config.save()

        return Response({
            'enabled': config.enabled,
            'calendly_url': config.calendly_url,
            'meeting_title': config.meeting_title,
            'meeting_description': config.meeting_description,
            'is_required': config.is_required,
        })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_mark_meeting_complete(request, chef_id):
    """
    POST /chefs/api/admin/chefs/<chef_id>/meeting/complete/

    Admin marks a chef's verification meeting as complete.
    """
    chef = get_object_or_404(Chef, id=chef_id)
    meeting, _ = ChefVerificationMeeting.objects.get_or_create(chef=chef)

    notes = request.data.get('notes', '')
    meeting.mark_as_completed(admin_user=request.user, notes=notes)

    return Response({
        'chef_id': chef.id,
        'chef_username': chef.user.username,
        'status': meeting.status,
        'completed_at': meeting.completed_at.isoformat(),
        'message': f'Meeting marked as complete for {chef.user.username}'
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_pending_meetings(request):
    """
    GET /chefs/api/admin/meetings/pending/

    List all chefs with pending verification meetings.
    """
    pending_meetings = ChefVerificationMeeting.objects.filter(
        status__in=['not_scheduled', 'scheduled']
    ).select_related('chef__user').order_by('-created_at')

    results = []
    for meeting in pending_meetings:
        results.append({
            'chef_id': meeting.chef.id,
            'chef_username': meeting.chef.user.username,
            'chef_email': meeting.chef.user.email,
            'status': meeting.status,
            'scheduled_at': meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
            'created_at': meeting.created_at.isoformat(),
        })

    return Response({
        'count': len(results),
        'meetings': results
    })
