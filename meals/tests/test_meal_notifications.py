from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.meal_assistant_implementation import MealPlanningAssistant
from meals.models import MealPlan
from meals.signals import send_meal_plan_email


@pytest.mark.django_db
def test_send_meal_plan_email_skips_when_notifications_disabled(settings):
    settings.MEAL_PLAN_EMAIL_NOTIFICATIONS_ENABLED = False

    user = CustomUser.objects.create_user(
        username="mealtester",
        password="password123",
        email="mealtester@example.com",
    )
    user.email_confirmed = True
    user.save(update_fields=["email_confirmed"])

    start_date = timezone.now().date()
    meal_plan = MealPlan.objects.create(
        user=user,
        week_start_date=start_date,
        week_end_date=start_date + timedelta(days=6),
        is_approved=True,
        has_changes=False,
        meal_prep_preference="one_day_prep",
    )
    meal_plan._previous_is_approved = False
    meal_plan._previous_has_changes = True

    with (
        patch("meals.signals.generate_shopping_list") as mock_shopping,
        patch("meals.signals.generate_bulk_prep_instructions") as mock_bulk,
    ):
        send_meal_plan_email(MealPlan, meal_plan)

    mock_shopping.assert_not_called()
    mock_bulk.assert_not_called()


@pytest.mark.django_db
def test_meal_plan_templates_skip_assistant_send_when_disabled(settings):
    settings.MEAL_PLAN_EMAIL_NOTIFICATIONS_ENABLED = False
    settings.TEST_MODE = False

    user = CustomUser.objects.create_user(
        username="notificationtester",
        password="password123",
        email="notificationtester@example.com",
    )
    user.email_confirmed = True
    user.save(update_fields=["email_confirmed"])

    with patch.object(
        MealPlanningAssistant,
        "process_and_reply_to_email",
        return_value={"status": "success"},
    ) as mock_process:
        result = MealPlanningAssistant.send_notification_via_assistant(
            user_id=user.id,
            message_content="Here is your shopping list.",
            subject="Shopping List",
            template_key="shopping_list",
            template_context={"main_text": "Sample"},
        )

    assert result["status"] == "skipped"
    assert result["reason"] == "meal_plan_notifications_disabled"
    mock_process.assert_not_called()
