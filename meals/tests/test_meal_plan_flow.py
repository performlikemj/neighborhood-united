from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import Meal, MealPlan, MealPlanMeal


def _monday_of_this_week() -> date:
    today = timezone.now().date()
    return today - timedelta(days=today.weekday())


def _stub_generate_and_create_meal(user,
                                   meal_plan,
                                   meal_type,
                                   existing_meal_names,
                                   existing_meal_embeddings,
                                   user_id,
                                   day_name,
                                   request_id=None,
                                   user_prompt=None,
                                   user_goal_description=None,
                                   **kwargs):
    """Lightweight stub that creates a simple Meal and attaches it to the plan."""
    name = f"{day_name} {meal_type}"
    meal = Meal.objects.create(name=name, meal_type=meal_type, creator=user)
    # attach to plan slot
    day_to_idx = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    meal_date = meal_plan.week_start_date + timedelta(days=day_to_idx[day_name])
    MealPlanMeal.objects.update_or_create(
        meal_plan=meal_plan,
        day=day_name,
        meal_type=meal_type,
        defaults={'meal': meal, 'meal_date': meal_date},
    )
    return {"status": "success", "meal": meal, "used_pantry_items": []}


class MealPlanFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="password123",
            email="test@example.com",
        )

    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_generate_meal_plan_is_auto_approved(self, _mock_gen):
        from meals.meal_plan_service import create_meal_plan_for_user

        monday = _monday_of_this_week()
        meal_plan = create_meal_plan_for_user(
            user=self.user,
            start_of_week=monday,
            end_of_week=monday + timedelta(days=6),
        )

        self.assertIsInstance(meal_plan, MealPlan)
        meal_plan.refresh_from_db()
        # Auto-approved on generation
        self.assertTrue(meal_plan.is_approved)
        self.assertFalse(meal_plan.has_changes)
        # And at least one slot was created
        self.assertTrue(MealPlanMeal.objects.filter(meal_plan=meal_plan).exists())

    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_edit_requires_manual_approval(self, _mock_gen):
        from meals.meal_plan_service import create_meal_plan_for_user
        from shared.utils import replace_meal_in_plan

        monday = _monday_of_this_week()
        meal_plan = create_meal_plan_for_user(
            user=self.user,
            start_of_week=monday,
            end_of_week=monday + timedelta(days=6),
        )

        # Ensure approved baseline
        meal_plan.refresh_from_db()
        self.assertTrue(meal_plan.is_approved)

        # Create an alternative meal and replace a slot
        alt_meal = Meal.objects.create(name="Alt Meal", meal_type="Dinner", creator=self.user)
        # Pick Monday Dinner for replacement
        request = SimpleNamespace(user=self.user, data={"user_id": self.user.id})
        res = replace_meal_in_plan(
            request,
            meal_plan_id=meal_plan.id,
            old_meal_id=MealPlanMeal.objects.filter(meal_plan=meal_plan, day="Monday", meal_type="Dinner").first().meal.id,
            new_meal_id=alt_meal.id,
            day="Monday",
            meal_type="Dinner",
        )
        self.assertEqual(res.get("status"), "success")

        meal_plan.refresh_from_db()
        self.assertFalse(meal_plan.is_approved)
        self.assertTrue(meal_plan.has_changes)

    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_api_approval_finalizes_changes(self, _mock_gen):
        from meals.meal_plan_service import create_meal_plan_for_user
        from rest_framework.test import APIClient

        monday = _monday_of_this_week()
        meal_plan = create_meal_plan_for_user(
            user=self.user,
            start_of_week=monday,
            end_of_week=monday + timedelta(days=6),
        )

        # Simulate a change
        meal_plan.is_approved = False
        meal_plan.has_changes = True
        meal_plan.save(update_fields=["is_approved", "has_changes"])

        client = APIClient()
        client.force_authenticate(user=self.user)
        url = reverse("meals:api_approve_meal_plan")
        resp = client.post(url, {"meal_plan_id": meal_plan.id, "meal_prep_preference": "daily"}, format="json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")

        meal_plan.refresh_from_db()
        self.assertTrue(meal_plan.is_approved)
        self.assertFalse(meal_plan.has_changes)
