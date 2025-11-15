import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import MealPlan
from meals.services import meal_plan_batch_service


@pytest.mark.django_db
def test_finalize_meal_plan_triggers_batch_email_only_once():
    user = CustomUser.objects.create_user(
        username="groq-user",
        email="groq-user@example.com",
        password="test-pass-123",
        email_confirmed=True,
    )
    today = timezone.now().date()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    meal_plan = MealPlan.objects.create(
        user=user,
        week_start_date=week_start,
        week_end_date=week_end,
        is_approved=False,
        has_changes=True,
    )

    with patch("meals.meal_plan_service.analyze_and_replace_meals"), patch(
        "meals.signals.generate_shopping_list"
    ) as generate_shopping_list:
        # First Groq finalization should trigger the shopping list email
        meal_plan_batch_service._finalize_meal_plan(
            user=user,
            meal_plan=meal_plan,
            request_id="batch-test-1",
        )
        assert generate_shopping_list.delay.call_count == 1

        meal_plan.refresh_from_db()
        # Simulate new Groq run by marking the plan as changed again
        meal_plan.is_approved = False
        meal_plan.has_changes = True
        meal_plan.save(update_fields=["is_approved", "has_changes"])

        meal_plan_batch_service._finalize_meal_plan(
            user=user,
            meal_plan=meal_plan,
            request_id="batch-test-2",
        )
        # Shopping list email should still have been triggered only once
        assert generate_shopping_list.delay.call_count == 1

        meal_plan.refresh_from_db()
        assert meal_plan.groq_auto_approved_at is not None
