from django.conf import settings


def legacy_meal_plan_flags(request):
    """Expose legacy meal-plan feature flags to all templates."""

    return {
        "legacy_meal_plan_enabled": getattr(settings, "LEGACY_MEAL_PLAN_ENABLED", True),
    }

