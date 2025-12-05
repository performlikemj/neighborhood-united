"""
Chef Dashboard API endpoints.

Provides the main dashboard summary endpoint for the chef CRM.
"""

import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chefs.models import Chef
from chefs.services import get_dashboard_summary
from .serializers import DashboardSummarySerializer

logger = logging.getLogger(__name__)


def _get_chef_or_403(request):
    """
    Get the Chef instance for the authenticated user.
    Returns (chef, None) on success, (None, Response) on failure.
    """
    try:
        chef = Chef.objects.get(user=request.user)
        return chef, None
    except Chef.DoesNotExist:
        return None, Response(
            {"error": "Not a chef. Only chefs can access the dashboard."},
            status=403
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    GET /api/chefs/me/dashboard/
    
    Returns aggregated dashboard statistics including:
    - Revenue (today, this week, this month)
    - Client counts (total, active, new this month)
    - Order stats (upcoming, pending, completed this month)
    - Top services by order count
    
    Response:
    ```json
    {
        "revenue": {"today": 150.00, "this_week": 890.00, "this_month": 3200.00},
        "clients": {"total": 24, "active": 18, "new_this_month": 3},
        "orders": {"upcoming": 5, "pending_confirmation": 2, "completed_this_month": 32},
        "top_services": [{"id": 1, "name": "Weekly Meal Prep", "order_count": 15}]
    }
    ```
    """
    chef, error_response = _get_chef_or_403(request)
    if error_response:
        return error_response
    
    try:
        summary_data = get_dashboard_summary(chef)
        serializer = DashboardSummarySerializer(summary_data)
        return Response(serializer.data)
    except Exception as e:
        logger.exception(f"Error fetching dashboard summary for chef {chef.id}: {e}")
        return Response(
            {"error": "Failed to fetch dashboard data. Please try again."},
            status=500
        )


