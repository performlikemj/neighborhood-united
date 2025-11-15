"""
Centralized feature flag helpers for the meals app.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings

# Template keys that correspond to consumer meal plan or instruction emails.
MEAL_PLAN_TEMPLATE_KEYS = frozenset(
    {
        "shopping_list",
        "daily_prep_instructions",
        "bulk_prep_instructions",
    }
)


def meal_plan_notifications_enabled() -> bool:
    """
    Return True when consumer-facing meal plan emails are allowed to send.
    Defaults to True if the setting is absent so existing environments stay unchanged.
    """
    return getattr(settings, "MEAL_PLAN_EMAIL_NOTIFICATIONS_ENABLED", True)


def is_meal_plan_template(template_key: Optional[str]) -> bool:
    """
    Determine whether a structured email template represents a meal plan notification.
    """
    if not template_key:
        return False
    return str(template_key).strip().lower() in MEAL_PLAN_TEMPLATE_KEYS
