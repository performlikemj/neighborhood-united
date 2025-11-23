from __future__ import annotations

"""Shared helpers for aggregating chef meal and service order data."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, List, Optional

from django.db.models import Prefetch
from django.utils import timezone

from chef_services.models import ChefServiceOrder
from chefs.models import Chef
from meals.models import ChefMealEvent, ChefMealOrder, Order, OrderMeal


def format_money(amount: Optional[Decimal | float | int | str]) -> str:
    """Return a consistently formatted money string with two decimals."""

    if amount is None:
        return "0.00"

    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    return f"{amount.quantize(Decimal('0.01'))}"


def _user_is_chef(user) -> bool:
    """Check chef role using request.user.is_chef when available."""

    if getattr(user, "is_chef", False):
        return True

    user_role = getattr(user, "userrole", None)
    return bool(getattr(user_role, "is_chef", False))


@dataclass
class DashboardItem:
    title: str
    status: str
    amount: str
    scheduled_at: Optional[datetime]
    metadata: dict


def _serialize_chef_event(event: ChefMealEvent) -> DashboardItem:
    event_dt = event.get_event_datetime()
    return DashboardItem(
        title=f"{event.meal.name} (Chef Meal)",
        status=event.status,
        amount=format_money(event.current_price),
        scheduled_at=event_dt,
        metadata={"type": "chef_meal_event", "id": event.id},
    )


def _serialize_service_order(order: ChefServiceOrder) -> DashboardItem:
    scheduled_dt = None
    if order.service_date:
        scheduled_dt = datetime.combine(order.service_date, order.service_start_time or datetime.min.time())

    tier_price = getattr(order.tier, "price_cents", None)
    amount = Decimal(tier_price or 0) / Decimal(100)

    return DashboardItem(
        title=order.offering.title,
        status=order.status,
        amount=format_money(amount),
        scheduled_at=scheduled_dt,
        metadata={"type": "service_order", "id": order.id},
    )


def _serialize_customer_order(order: Order, user) -> DashboardItem:
    total = order.total_price()
    return DashboardItem(
        title=f"Order #{order.id}",
        status=order.status,
        amount=format_money(total),
        scheduled_at=order.order_date,
        metadata={"type": "standard_order", "id": order.id, "customer_id": user.id},
    )


def get_chef_dashboard_items(user) -> List[DashboardItem]:
    """Aggregate chef-facing items across meal events and service orders."""

    if not _user_is_chef(user):
        return []

    chef: Chef = Chef.objects.filter(user=user).first()
    if not chef:
        return []

    now = timezone.now().date()

    events = (
        ChefMealEvent.objects.filter(chef=chef, event_date__gte=now)
        .select_related("meal", "chef")
        .order_by("event_date", "event_time")
    )

    service_orders = (
        ChefServiceOrder.objects.filter(chef=chef)
        .select_related("offering", "tier")
        .order_by("-created_at")
    )

    items: List[DashboardItem] = []
    items.extend(_serialize_chef_event(event) for event in events)
    items.extend(_serialize_service_order(order) for order in service_orders)

    return items


def get_chef_calendar_items(user) -> List[DashboardItem]:
    """Return calendar-friendly items for chefs across services and events."""

    return get_chef_dashboard_items(user)


def _prefetch_order_meals(orders: Iterable[Order]) -> Iterable[Order]:
    return orders.prefetch_related(
        Prefetch(
            "ordermeal_set",
            queryset=OrderMeal.objects.select_related("meal", "chef_meal_event", "chef_meal_event__meal"),
        )
    )


def get_my_orders(user) -> List[DashboardItem]:
    """Return customer view of their chef meal, service, and standard orders."""

    chef_meal_orders = (
        ChefMealOrder.objects.filter(customer=user)
        .select_related("meal_event", "meal_event__meal")
        .order_by("-created_at")
    )

    service_orders = (
        ChefServiceOrder.objects.filter(customer=user)
        .select_related("offering", "tier")
        .order_by("-created_at")
    )

    standard_orders = _prefetch_order_meals(
        Order.objects.filter(customer=user).order_by("-order_date")
    )

    items: List[DashboardItem] = []
    for chef_order in chef_meal_orders:
        scheduled_dt = chef_order.meal_event.get_event_datetime() if chef_order.meal_event else chef_order.created_at
        total_paid = (chef_order.price_paid or chef_order.unit_price or Decimal("0")) * (chef_order.quantity or 1)
        items.append(
            DashboardItem(
                title=f"{chef_order.meal_event.meal.name} (Chef Meal)",
                status=chef_order.status,
                amount=format_money(total_paid),
                scheduled_at=scheduled_dt,
                metadata={"type": "chef_meal_order", "id": chef_order.id},
            )
        )

    items.extend(_serialize_service_order(order) for order in service_orders)
    items.extend(_serialize_customer_order(order, user) for order in standard_orders)

    return items


def ensure_chef_meal_order(
    *,
    order: Order,
    event: ChefMealEvent,
    customer,
    quantity: int,
    unit_price: Optional[Decimal] = None,
) -> ChefMealOrder:
    """Centralized helper to create or update a ChefMealOrder for an Order/Event pair."""

    defaults = {
        "customer": customer,
        "quantity": quantity,
        "unit_price": unit_price or event.current_price,
        "price_paid": unit_price or event.current_price,
    }

    chef_meal_order, _ = ChefMealOrder.objects.update_or_create(
        order=order, meal_event=event, defaults=defaults
    )

    return chef_meal_order

