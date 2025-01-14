# meals/tests/tests.py

from django.test import TestCase
from freezegun import freeze_time
from datetime import datetime, timedelta
from django.utils import timezone
from customer_dashboard.models import GoalTracking
from meals.models import PantryItem, CustomUser, MealPlan, MealPlanMeal
from meals.meal_generation import (
    generate_and_create_meal,
    get_expiring_pantry_items
)

class PantryManagementTests(TestCase):

    def setUp(self):
        # Create a test user
        self.user = CustomUser.objects.create(username="testuser", email="test@example.com")

        # Create a goal for the user
        self.goal = GoalTracking.objects.create(
            user=self.user,
            goal_description="Lose Weight",  # or any dummy text
            goal_name="Weight Loss",
        )
        self.user.goal = self.goal
        self.user.save()

    @freeze_time("2024-01-01")  # Starting point for the entire test
    def test_generate_meals_across_weeks_with_expiring_items(self):
        """
        Refactored: We use multiple freeze_time contexts so that items 
        expire between the first set of meal generations and the second set.
        """

        # (A) CREATE PANTRY ITEMS
        # "Coconut Milk" expires soon: Jan 3 => valid on Jan 1, expired by Jan 5
        PantryItem.objects.create(
            user=self.user,
            item_name="Coconut Milk",
            expiration_date=datetime(2024, 1, 3).date(),
            quantity=1
        )
        # "Kinako Powder" expires Jan 10 => valid past Jan 5
        PantryItem.objects.create(
            user=self.user,
            item_name="Kinako Powder",
            expiration_date=datetime(2024, 1, 10).date(),
            quantity=5
        )
        # "Canned Beans" expired Dec 31 => already expired on Jan 1
        PantryItem.objects.create(
            user=self.user,
            item_name="Canned Beans",
            expiration_date=datetime(2023, 12, 31).date(),
            quantity=2
        )

        # (B) WEEK 1 MEAL PLAN (frozen at 2024-01-01)
        # Coconut Milk is still valid (expires Jan 3).
        today = timezone.now().date()  # => 2024-01-01
        start_of_week_1 = today
        end_of_week_1 = start_of_week_1 + timedelta(days=6)

        meal_plan_week_1 = MealPlan.objects.create(
            user=self.user,
            week_start_date=start_of_week_1,
            week_end_date=end_of_week_1
        )

        # Generate 1 meal per day for 7 days
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day_name in day_names:
            resp = generate_and_create_meal(
                user=self.user,
                meal_plan=meal_plan_week_1,
                meal_type="Lunch",
                existing_meal_names=set(),
                existing_meal_embeddings=[],
                user_id=self.user.id,
                day_name=day_name,
                max_attempts=3
            )
            print(f"[Week1][{day_name}] => {resp}")

        # After generating meals in the first week, ensure they exist
        first_week_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan_week_1)
        self.assertTrue(first_week_meals.exists(), "No meals were generated for the first week!")

        # Check that "Canned Beans" was not used if your code excludes it 
        # (since it's already expired on Jan 1). This can be a text-based search 
        # in the meal descriptions or a deeper check if your code logs that item usage.

        # (C) WEEK 2 MEAL PLAN - ADVANCE TIME to 2024-01-05
        with freeze_time("2024-01-05"):
            # Now Coconut Milk is expired (expired Jan 3).
            # Kinako Powder is still valid (expires Jan 10).

            start_of_week_2 = datetime(2024, 1, 5).date()
            end_of_week_2 = start_of_week_2 + timedelta(days=6)

            meal_plan_week_2 = MealPlan.objects.create(
                user=self.user,
                week_start_date=start_of_week_2,
                week_end_date=end_of_week_2
            )

            # Generate for the second week
            for day_name in day_names:
                resp = generate_and_create_meal(
                    user=self.user,
                    meal_plan=meal_plan_week_2,
                    meal_type="Lunch",
                    existing_meal_names=set(),
                    existing_meal_embeddings=[],
                    user_id=self.user.id,
                    day_name=day_name,
                    max_attempts=3
                )
                print(f"[Week2][{day_name}] => {resp}")

            # Check that second week's meals exist
            second_week_meals = MealPlanMeal.objects.filter(meal_plan=meal_plan_week_2)
            self.assertTrue(second_week_meals.exists(), "No meals generated for the second week!")
            
            # Now "Coconut Milk" should be skipped if your code calls get_expiring_pantry_items() 
            # and sees it's expired on Jan 5. 
            # "Kinako Powder" can appear.

        # Confirm overall meal creation
        all_plan_meals = MealPlanMeal.objects.filter(meal_plan__in=[meal_plan_week_1, meal_plan_week_2])
        self.assertTrue(all_plan_meals.exists(), "No meals were generated across the two weeks!")
        
        # Additional checks:
        #  - Confirm "Coconut Milk" usage in week1's meal descriptions 
        #  - Confirm it does NOT appear in week2's meal descriptions
        #  - "Canned Beans" never used in either week
        #  - "Kinako Powder" can appear in both weeks if your logic uses it

        print("[TEST] Completed meal generation across multiple weeks with time actually advancing.")