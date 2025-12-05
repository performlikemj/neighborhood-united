# Chef services module - business logic for chef CRM functionality
from .client_insights import (
    get_dashboard_summary,
    get_client_stats,
    get_client_list_with_stats,
    get_revenue_breakdown,
    get_upcoming_orders,
)

__all__ = [
    'get_dashboard_summary',
    'get_client_stats',
    'get_client_list_with_stats',
    'get_revenue_breakdown',
    'get_upcoming_orders',
]


