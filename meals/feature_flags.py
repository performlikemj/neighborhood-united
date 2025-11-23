"""
Centralized feature flag helpers for the meals app.
"""
from __future__ import annotations

from typing import Optional

from functools import wraps
from django.conf import settings
from django.http import Http404

LEGACY_MEAL_PLAN = True

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
    if not getattr(settings, "LEGACY_MEAL_PLAN_ENABLED", True):
        return False
    return getattr(settings, "MEAL_PLAN_EMAIL_NOTIFICATIONS_ENABLED", True)


def legacy_meal_plan_enabled() -> bool:
    """Return the current on/off state for the legacy meal-plan stack."""

    return getattr(settings, "LEGACY_MEAL_PLAN_ENABLED", True)


def require_legacy_meal_plan_enabled(view_func):
    """Raise 404s for legacy entry points when the feature is disabled."""

    @wraps(view_func)
    def _wrapped_view(*args, **kwargs):
        if not legacy_meal_plan_enabled():
            raise Http404("Legacy meal plans are disabled.")
        return view_func(*args, **kwargs)

    return _wrapped_view


def is_meal_plan_template(template_key: Optional[str]) -> bool:
    """
    Determine whether a structured email template represents a meal plan notification.
    """
    if not template_key:
        return False
    return str(template_key).strip().lower() in MEAL_PLAN_TEMPLATE_KEYS
