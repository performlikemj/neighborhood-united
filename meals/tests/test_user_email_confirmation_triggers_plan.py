from unittest.mock import patch
from django.test import TestCase
from django.db import transaction
from django.utils import timezone

from custom_auth.models import CustomUser
from meals.models import Meal, MealPlan, MealPlanMeal
from datetime import datetime, date, timedelta, timezone as py_tz


class UserEmailConfirmationSignalTests(TestCase):
    def test_no_plan_on_create_when_unconfirmed(self):
        with patch('meals.signals.create_meal_plan_for_new_user.delay') as mock_delay:
            CustomUser.objects.create_user(username='u1', password='x', email='u1@example.com', email_confirmed=False)
            self.assertFalse(mock_delay.called)


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
    """Create a simple Meal and attach it to the plan (lightweight stub)."""
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


class AutoWeekCreationSpecificDateTests(TestCase):
    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_auto_plan_for_week_2025_09_15_enabled(self, _mock_gen):
        """
        Freeze time to Saturday 2025-09-13 and run the weekly auto-creation.
        Verify a plan is created for week starting Monday 2025-09-15 when auto-plans are enabled.
        """
        u = CustomUser.objects.create_user(
            username='user_enabled',
            password='x',
            email='user_enabled@example.com',
            email_confirmed=True,
            auto_meal_plans_enabled=True,
        )
        u.timezone = 'UTC'
        u.save(update_fields=["timezone"])

        target_monday = date(2025, 9, 15)
        target_sunday = date(2025, 9, 21)

        from meals.meal_plan_service import create_meal_plan_for_all_users

        # Freeze now to Saturday 2025-09-13 12:00 UTC
        frozen_now = datetime(2025, 9, 13, 12, 0, 0, tzinfo=py_tz.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            create_meal_plan_for_all_users()

        exists = MealPlan.objects.filter(
            user_id=u.id,
            week_start_date=target_monday,
            week_end_date=target_sunday,
        ).exists()
        self.assertTrue(exists, "Expected an auto-created meal plan when enabled")

    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_no_auto_plan_for_week_2025_09_15_when_disabled(self, _mock_gen):
        """
        Same date freeze as above but with auto-plans disabled; no plan should be created.
        """
        u = CustomUser.objects.create_user(
            username='user_disabled',
            password='x',
            email='user_disabled@example.com',
            email_confirmed=True,
            auto_meal_plans_enabled=False,
        )
        u.timezone = 'UTC'
        u.save(update_fields=["timezone"])

        target_monday = date(2025, 9, 15)
        target_sunday = date(2025, 9, 21)

        from meals.meal_plan_service import create_meal_plan_for_all_users

        frozen_now = datetime(2025, 9, 13, 12, 0, 0, tzinfo=py_tz.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            create_meal_plan_for_all_users()

        exists = MealPlan.objects.filter(
            user_id=u.id,
            week_start_date=target_monday,
            week_end_date=target_sunday,
        ).exists()
        self.assertFalse(exists, "Did not expect an auto-created meal plan when disabled")


class ManualCreationIgnoresAutoFlagTests(TestCase):
    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_manual_creation_when_auto_disabled_creates_plan(self, _mock_gen):
        from meals.meal_plan_service import create_meal_plan_for_user
        u = CustomUser.objects.create_user(
            username='manual_disabled',
            password='x',
            email='manual_disabled@example.com',
            email_confirmed=True,
            auto_meal_plans_enabled=False,
        )

        monday = timezone.now().date()
        monday = monday - timedelta(days=monday.weekday())
        plan = create_meal_plan_for_user(
            user=u,
            start_of_week=monday,
            end_of_week=monday + timedelta(days=6),
        )
        self.assertIsNotNone(plan)
        self.assertTrue(MealPlan.objects.filter(user=u, week_start_date=monday).exists())

    @patch("meals.signals.generate_shopping_list.delay", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.analyze_and_replace_meals", lambda *args, **kwargs: None)
    @patch("meals.meal_plan_service.generate_and_create_meal", side_effect=_stub_generate_and_create_meal)
    def test_manual_creation_when_auto_enabled_creates_plan(self, _mock_gen):
        from meals.meal_plan_service import create_meal_plan_for_user
        u = CustomUser.objects.create_user(
            username='manual_enabled',
            password='x',
            email='manual_enabled@example.com',
            email_confirmed=True,
            auto_meal_plans_enabled=True,
        )

        monday = timezone.now().date()
        monday = monday - timedelta(days=monday.weekday())
        plan = create_meal_plan_for_user(
            user=u,
            start_of_week=monday,
            end_of_week=monday + timedelta(days=6),
        )
        self.assertIsNotNone(plan)
        self.assertTrue(MealPlan.objects.filter(user=u, week_start_date=monday).exists())

    def test_plan_queued_on_confirm_transition(self):
        user = CustomUser.objects.create_user(username='u2', password='x', email='u2@example.com', email_confirmed=False)
        with patch('meals.signals.create_meal_plan_for_new_user.delay') as mock_delay:
            user.email_confirmed = True
            # Ensure on_commit callbacks execute inside the test
            with self.captureOnCommitCallbacks(execute=True):
                user.save()
            self.assertTrue(mock_delay.called)

    def test_no_duplicate_queue_if_already_confirmed(self):
        user = CustomUser.objects.create_user(username='u3', password='x', email='u3@example.com', email_confirmed=False)
        with patch('meals.signals.create_meal_plan_for_new_user.delay') as mock_delay:
            user.email_confirmed = True
            with self.captureOnCommitCallbacks(execute=True):
                user.save()
            self.assertEqual(mock_delay.call_count, 1)
            # Save again with True -> True should not queue again
            user.email_confirmed = True
            with self.captureOnCommitCallbacks(execute=True):
                user.save()
            self.assertEqual(mock_delay.call_count, 1)

    def test_no_plan_on_create_when_confirmed_but_auto_disabled(self):
        with patch('meals.signals.create_meal_plan_for_new_user.delay') as mock_delay:
            CustomUser.objects.create_user(
                username='u4', password='x', email='u4@example.com',
                email_confirmed=True,
                auto_meal_plans_enabled=False,
            )
            self.assertFalse(mock_delay.called)

    def test_no_plan_on_confirm_transition_when_auto_disabled(self):
        user = CustomUser.objects.create_user(
            username='u5', password='x', email='u5@example.com',
            email_confirmed=False,
            auto_meal_plans_enabled=False,
        )
        with patch('meals.signals.create_meal_plan_for_new_user.delay') as mock_delay:
            user.email_confirmed = True
            with self.captureOnCommitCallbacks(execute=True):
                user.save()
            self.assertFalse(mock_delay.called)
