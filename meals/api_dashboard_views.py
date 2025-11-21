from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.order_service import (
    _user_is_chef,
    get_chef_calendar_items,
    get_chef_dashboard_items,
    get_my_orders,
)
from meals.serializers import DashboardItemSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chef_dashboard(request):
    """Dashboard data for chef role combining meals and services."""

    if not _user_is_chef(request.user):
        return Response({"detail": "Chef access required."}, status=403)

    items = get_chef_dashboard_items(request.user)
    serializer = DashboardItemSerializer(items, many=True)
    return Response({"items": serializer.data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chef_calendar(request):
    """Calendar-style feed for chefs covering events and service orders."""

    if not _user_is_chef(request.user):
        return Response({"detail": "Chef access required."}, status=403)

    items = get_chef_calendar_items(request.user)
    serializer = DashboardItemSerializer(items, many=True)
    return Response({"items": serializer.data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orders(request):
    """Aggregate a user's orders across chef meals, services, and standard orders."""

    items = get_my_orders(request.user)
    serializer = DashboardItemSerializer(items, many=True)
    return Response({"items": serializer.data})

