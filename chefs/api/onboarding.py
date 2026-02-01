"""
Onboarding API endpoints for Sous Chef setup flow.

Tracks the chef's journey through the onboarding wizard
and milestones.
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef, ChefOnboardingState

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """Get the Chef instance for the authenticated user."""
    try:
        chef = Chef.objects.select_related('user').get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access onboarding."},
            status=403
        )


def _serialize_onboarding_state(state: ChefOnboardingState) -> dict:
    """Serialize onboarding state for API response."""
    return {
        # Welcome & Setup
        "welcomed": state.welcomed,
        "welcomed_at": state.welcomed_at.isoformat() if state.welcomed_at else None,
        "setup_started": state.setup_started,
        "setup_started_at": state.setup_started_at.isoformat() if state.setup_started_at else None,
        "setup_completed": state.setup_completed,
        "setup_completed_at": state.setup_completed_at.isoformat() if state.setup_completed_at else None,
        "setup_skipped": state.setup_skipped,
        "setup_skipped_at": state.setup_skipped_at.isoformat() if state.setup_skipped_at else None,

        # Personality
        "personality_set": state.personality_set,
        "personality_choice": state.personality_choice,

        # Milestones
        "first_dish_added": state.first_dish_added,
        "first_dish_added_at": state.first_dish_added_at.isoformat() if state.first_dish_added_at else None,
        "first_client_added": state.first_client_added,
        "first_client_added_at": state.first_client_added_at.isoformat() if state.first_client_added_at else None,
        "first_conversation": state.first_conversation,
        "first_conversation_at": state.first_conversation_at.isoformat() if state.first_conversation_at else None,
        "first_memory_saved": state.first_memory_saved,
        "first_memory_saved_at": state.first_memory_saved_at.isoformat() if state.first_memory_saved_at else None,
        "first_order_completed": state.first_order_completed,
        "first_order_completed_at": state.first_order_completed_at.isoformat() if state.first_order_completed_at else None,
        "proactive_enabled": state.proactive_enabled,
        "proactive_enabled_at": state.proactive_enabled_at.isoformat() if state.proactive_enabled_at else None,

        # Tips
        "tips_shown": state.tips_shown,
        "tips_dismissed": state.tips_dismissed,

        # Timestamps
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def onboarding_get(request):
    """
    GET /chefs/api/me/onboarding/

    Get the chef's onboarding state.
    Auto-creates if it doesn't exist.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    state = ChefOnboardingState.get_or_create_for_chef(chef)

    return Response({
        "status": "success",
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_welcomed(request):
    """
    POST /chefs/api/me/onboarding/welcomed/

    Mark that the chef has seen the welcome modal.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    state = ChefOnboardingState.get_or_create_for_chef(chef)
    state.mark_welcomed()

    logger.info(f"Chef {chef.id} marked as welcomed")

    return Response({
        "status": "success",
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_start(request):
    """
    POST /chefs/api/me/onboarding/start/

    Mark that the chef has started the setup wizard.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    state = ChefOnboardingState.get_or_create_for_chef(chef)

    # Also mark welcomed if not already
    if not state.welcomed:
        state.mark_welcomed()

    state.mark_setup_started()

    logger.info(f"Chef {chef.id} started onboarding setup")

    return Response({
        "status": "success",
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_complete(request):
    """
    POST /chefs/api/me/onboarding/complete/

    Mark that the chef has completed the setup wizard.

    Optional request body:
    {
        "personality_choice": "friendly"  // Record final personality selection
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    state = ChefOnboardingState.get_or_create_for_chef(chef)

    # Optionally record personality choice
    personality = request.data.get('personality_choice')
    if personality:
        state.personality_set = True
        state.personality_choice = personality
        state.save(update_fields=['personality_set', 'personality_choice', 'updated_at'])

    state.mark_setup_completed()

    logger.info(f"Chef {chef.id} completed onboarding setup")

    return Response({
        "status": "success",
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_skip(request):
    """
    POST /chefs/api/me/onboarding/skip/

    Mark that the chef has skipped the setup wizard.
    They can still access features but won't see the wizard again.
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    state = ChefOnboardingState.get_or_create_for_chef(chef)

    # Mark welcomed if not already
    if not state.welcomed:
        state.mark_welcomed()

    state.mark_setup_skipped()

    logger.info(f"Chef {chef.id} skipped onboarding setup")

    return Response({
        "status": "success",
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_milestone(request):
    """
    POST /chefs/api/me/onboarding/milestone/

    Record a milestone achievement.

    Request body:
    {
        "milestone": "first_dish"  // Required
    }

    Valid milestones:
    - first_dish
    - first_client
    - first_conversation
    - first_memory
    - first_order
    - proactive_enabled
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    milestone = request.data.get('milestone')
    if not milestone:
        return Response(
            {"error": "Missing required field: milestone"},
            status=400
        )

    valid_milestones = [
        'first_dish', 'first_client', 'first_conversation',
        'first_memory', 'first_order', 'proactive_enabled'
    ]

    if milestone not in valid_milestones:
        return Response(
            {"error": f"Invalid milestone. Valid options: {valid_milestones}"},
            status=400
        )

    state = ChefOnboardingState.get_or_create_for_chef(chef)
    was_recorded = state.record_milestone(milestone)

    if was_recorded:
        logger.info(f"Chef {chef.id} achieved milestone: {milestone}")

    return Response({
        "status": "success",
        "milestone": milestone,
        "newly_recorded": was_recorded,
        "onboarding": _serialize_onboarding_state(state),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_tip_show(request):
    """
    POST /chefs/api/me/onboarding/tip/show/

    Record that a tip was shown to the chef.

    Request body:
    {
        "tip_id": "add_first_dish"  // Required
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    tip_id = request.data.get('tip_id')
    if not tip_id:
        return Response(
            {"error": "Missing required field: tip_id"},
            status=400
        )

    state = ChefOnboardingState.get_or_create_for_chef(chef)
    state.show_tip(tip_id)

    return Response({
        "status": "success",
        "tip_id": tip_id,
        "tips_shown": state.tips_shown,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_tip_dismiss(request):
    """
    POST /chefs/api/me/onboarding/tip/dismiss/

    Permanently dismiss a tip (won't show again).

    Request body:
    {
        "tip_id": "add_first_dish"  // Required
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    tip_id = request.data.get('tip_id')
    if not tip_id:
        return Response(
            {"error": "Missing required field: tip_id"},
            status=400
        )

    state = ChefOnboardingState.get_or_create_for_chef(chef)
    state.dismiss_tip(tip_id)

    logger.info(f"Chef {chef.id} dismissed tip: {tip_id}")

    return Response({
        "status": "success",
        "tip_id": tip_id,
        "tips_dismissed": state.tips_dismissed,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_personality(request):
    """
    POST /chefs/api/me/onboarding/personality/

    Set the chef's communication style preference.
    This updates both the onboarding state and the workspace soul_prompt.

    Request body:
    {
        "personality": "friendly"  // Required: professional, friendly, or efficient
    }
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response

    personality = request.data.get('personality')
    if not personality:
        return Response(
            {"error": "Missing required field: personality"},
            status=400
        )

    valid_personalities = ['professional', 'friendly', 'efficient']
    if personality not in valid_personalities:
        return Response(
            {"error": f"Invalid personality. Valid options: {valid_personalities}"},
            status=400
        )

    # Update onboarding state
    state = ChefOnboardingState.get_or_create_for_chef(chef)
    state.personality_set = True
    state.personality_choice = personality
    state.save(update_fields=['personality_set', 'personality_choice', 'updated_at'])

    # Update workspace soul_prompt
    from chefs.models import ChefWorkspace

    personality_prompts = {
        'professional': """Communicate in a professional, clear manner.
Be respectful and formal. Focus on facts and actionable information.
Keep responses concise and well-organized.
When suggesting dishes, lead with the practical benefits.""",

        'friendly': """Be warm, friendly, and encouraging.
Use casual language and occasional emojis.
Celebrate wins and offer genuine support.
Remember personal details and bring them up naturally.
Share enthusiasm about cooking and food.""",

        'efficient': """Be extremely concise.
Bullet points over paragraphs.
No pleasantries or filler.
Just the essential information.
Lead with actionable items.""",
    }

    workspace = ChefWorkspace.get_or_create_for_chef(chef)
    workspace.soul_prompt = personality_prompts[personality]
    workspace.save(update_fields=['soul_prompt', 'updated_at'])

    logger.info(f"Chef {chef.id} set personality to: {personality}")

    return Response({
        "status": "success",
        "personality": personality,
        "onboarding": _serialize_onboarding_state(state),
    })
