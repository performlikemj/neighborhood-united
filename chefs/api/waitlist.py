from django.utils import timezone
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef, ChefWaitlistConfig, ChefWaitlistSubscription
from meals.models import ChefMealEvent, STATUS_OPEN, STATUS_SCHEDULED
from crm.models import Lead, LeadInteraction
from crm.service import create_or_update_lead_for_user


@api_view(['GET'])
@permission_classes([AllowAny])
def waitlist_config(request):
    """Return whether the chef waitlist feature is enabled."""
    cfg = ChefWaitlistConfig.get_config()
    enabled = True if cfg is None else bool(getattr(cfg, 'enabled', True))
    return Response({'enabled': enabled})


def _count_upcoming_events(chef_id):
    now = timezone.now()
    return ChefMealEvent.objects.filter(
        chef_id=chef_id,
        status__in=[STATUS_SCHEDULED, STATUS_OPEN],
        order_cutoff_time__gt=now,
        orders_count__lt=F('max_orders')
    ).count()


@api_view(['GET'])
@permission_classes([AllowAny])
def waitlist_status(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)

    enabled = True
    upcoming = _count_upcoming_events(chef.id)

    subscribed = False
    can_subscribe = False
    if getattr(request, 'user', None) and request.user.is_authenticated:
        subscribed = ChefWaitlistSubscription.objects.filter(user=request.user, chef=chef, active=True).exists()
        can_subscribe = enabled and not subscribed and (chef.is_on_break or upcoming == 0)

    return Response({
        'enabled': enabled,
        'subscribed': subscribed,
        'can_subscribe': can_subscribe,
        'chef_is_on_break': chef.is_on_break,
        'upcoming_events_count': upcoming,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def waitlist_subscribe(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)

    ChefWaitlistSubscription.objects.get_or_create(
        user=request.user,
        chef=chef,
        active=True,
        defaults={},
    )

    create_or_update_lead_for_user(
        user=request.user,
        chef_user=chef.user,
        source=Lead.Source.WEB,
        summary="Joined chef waitlist",
        details=f"User subscribed to {chef.user.get_full_name() or chef.user.username} waitlist",
        interaction_type=LeadInteraction.InteractionType.MESSAGE,
    )
    return Response({'status': 'ok', 'subscribed': True})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def waitlist_unsubscribe(request, chef_id):
    chef = get_object_or_404(Chef, id=chef_id)
    updated = ChefWaitlistSubscription.objects.filter(user=request.user, chef=chef, active=True).update(active=False)
    if updated == 0:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
