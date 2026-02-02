"""
Workspace API endpoints for Sous Chef configuration.

Allows chefs to customize their Sous Chef's personality (soul_prompt)
and business rules.
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef, ChefWorkspace

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """Get the Chef instance for the authenticated user."""
    try:
        chef = Chef.objects.select_related('user').get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access workspace settings."},
            status=403
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace_get(request):
    """
    GET /chefs/api/me/workspace/

    Fetch the chef's workspace configuration.
    Auto-creates with defaults if it doesn't exist.

    Response:
    {
        "soul_prompt": "...",
        "business_rules": "...",
        "enabled_tools": [...],
        "include_analytics": true,
        "include_seasonal": true,
        "auto_memory_save": true,
        "created_at": "...",
        "updated_at": "..."
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    workspace = ChefWorkspace.get_or_create_for_chef(chef)

    return Response({
        "soul_prompt": workspace.soul_prompt,
        "business_rules": workspace.business_rules,
        "enabled_tools": workspace.enabled_tools,
        "tool_preferences": workspace.tool_preferences,
        "include_analytics": workspace.include_analytics,
        "include_seasonal": workspace.include_seasonal,
        "auto_memory_save": workspace.auto_memory_save,
        "chef_nickname": workspace.chef_nickname,
        "chef_specialties": workspace.chef_specialties,
        "sous_chef_name": workspace.sous_chef_name,
        "created_at": workspace.created_at.isoformat(),
        "updated_at": workspace.updated_at.isoformat(),
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def workspace_update(request):
    """
    PATCH /chefs/api/me/workspace/update/

    Partial update of workspace configuration.
    Only provided fields are updated.

    Request Body (all fields optional):
    {
        "soul_prompt": "...",
        "business_rules": "...",
        "enabled_tools": [...],
        "include_analytics": true,
        "include_seasonal": true,
        "auto_memory_save": true
    }

    Response: Updated workspace fields
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    workspace = ChefWorkspace.get_or_create_for_chef(chef)

    # Allowed fields for update
    allowed_fields = [
        'soul_prompt',
        'business_rules',
        'enabled_tools',
        'tool_preferences',
        'include_analytics',
        'include_seasonal',
        'auto_memory_save',
        'chef_nickname',
        'chef_specialties',
        'sous_chef_name',
    ]

    updated_fields = []
    for field in allowed_fields:
        if field in request.data:
            value = request.data[field]
            setattr(workspace, field, value)
            updated_fields.append(field)

    if updated_fields:
        workspace.save(update_fields=updated_fields + ['updated_at'])
        logger.info(f"Chef {chef.id} updated workspace fields: {updated_fields}")

    return Response({
        "status": "success",
        "updated_fields": updated_fields,
        "soul_prompt": workspace.soul_prompt,
        "business_rules": workspace.business_rules,
        "enabled_tools": workspace.enabled_tools,
        "tool_preferences": workspace.tool_preferences,
        "include_analytics": workspace.include_analytics,
        "include_seasonal": workspace.include_seasonal,
        "auto_memory_save": workspace.auto_memory_save,
        "chef_nickname": workspace.chef_nickname,
        "chef_specialties": workspace.chef_specialties,
        "sous_chef_name": workspace.sous_chef_name,
        "updated_at": workspace.updated_at.isoformat(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def workspace_reset(request):
    """
    POST /chefs/api/me/workspace/reset/

    Reset workspace fields to their defaults.

    Request Body (optional):
    {
        "fields": ["soul_prompt", "business_rules"]  // Reset specific fields
    }

    If no fields specified, resets soul_prompt and business_rules only.

    Response: Reset workspace fields
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    workspace = ChefWorkspace.get_or_create_for_chef(chef)

    # Get fields to reset
    fields_to_reset = request.data.get('fields')
    if not fields_to_reset:
        # Default: reset personality and rules only
        fields_to_reset = ['soul_prompt', 'business_rules']

    # Map fields to their default values
    defaults = {
        'soul_prompt': ChefWorkspace.get_default_soul_prompt(),
        'business_rules': '',
        'enabled_tools': ChefWorkspace.get_default_tools(),
        'tool_preferences': {},
        'include_analytics': True,
        'include_seasonal': True,
        'auto_memory_save': True,
        'chef_nickname': '',
        'chef_specialties': [],
        'sous_chef_name': '',
    }

    reset_fields = []
    for field in fields_to_reset:
        if field in defaults:
            setattr(workspace, field, defaults[field])
            reset_fields.append(field)

    if reset_fields:
        workspace.save(update_fields=reset_fields + ['updated_at'])
        logger.info(f"Chef {chef.id} reset workspace fields: {reset_fields}")

    return Response({
        "status": "success",
        "reset_fields": reset_fields,
        "soul_prompt": workspace.soul_prompt,
        "business_rules": workspace.business_rules,
        "enabled_tools": workspace.enabled_tools,
        "tool_preferences": workspace.tool_preferences,
        "include_analytics": workspace.include_analytics,
        "include_seasonal": workspace.include_seasonal,
        "auto_memory_save": workspace.auto_memory_save,
        "chef_nickname": workspace.chef_nickname,
        "chef_specialties": workspace.chef_specialties,
        "sous_chef_name": workspace.sous_chef_name,
        "updated_at": workspace.updated_at.isoformat(),
    })
