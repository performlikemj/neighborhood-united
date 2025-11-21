"""Shared logic for service orders used by dashboard and calendar views."""

from datetime import datetime
from decimal import Decimal
from typing import List

from chef_services.models import ChefServiceOrder

from meals.order_service import DashboardItem, format_money


def get_service_orders_for_user(user) -> List[DashboardItem]:
    """Return DashboardItem entries for all service orders belonging to a user."""

    service_orders = (
        ChefServiceOrder.objects.filter(customer=user)
        .select_related("offering", "tier")
        .order_by("-created_at")
    )

    items: List[DashboardItem] = []
    for order in service_orders:
        scheduled_dt = None
        if order.service_date:
            scheduled_dt = datetime.combine(order.service_date, order.service_start_time or datetime.min.time())

        tier_price = getattr(order.tier, "price_cents", None)
        amount = Decimal(tier_price or 0) / Decimal(100)

        items.append(
            DashboardItem(
                title=order.offering.title,
                status=order.status,
                amount=format_money(amount),
                scheduled_at=scheduled_dt,
                metadata={"type": "service_order", "id": order.id},
            )
        )

    return items

