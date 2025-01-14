# meals/management/commands/migrate_meal_dates.py

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from meals.models import MealPlanMeal

DAY_OFFSET = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
    'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
}

class Command(BaseCommand):
    help = "Migrate day-based MealPlanMeals to new meal_date field."

    def handle(self, *args, **options):
        with transaction.atomic():
            mpm_list = MealPlanMeal.objects.select_related('meal_plan').all()
            updated_count = 0
            for mpm in mpm_list:
                if not mpm.meal_date and hasattr(mpm, 'day') and mpm.meal_plan:
                    day_offset = DAY_OFFSET.get(mpm.day)
                    if day_offset is not None:
                        meal_date = mpm.meal_plan.week_start_date + timedelta(days=day_offset)
                        mpm.meal_date = meal_date
                        mpm.save()
                        updated_count += 1
            self.stdout.write(self.style.SUCCESS(f"Updated {updated_count} MealPlanMeal records."))