from django.core.management.base import BaseCommand
from meals.models import MealPlan
import uuid

class Command(BaseCommand):
    help = 'Fix duplicate or missing approval tokens'

    def handle(self, *args, **kwargs):
        meal_plans = MealPlan.objects.all()
        
        # Assign unique tokens where duplicates or missing values exist
        for meal_plan in meal_plans:
            if not meal_plan.approval_token:
                meal_plan.approval_token = uuid.uuid4()
            else:
                # Ensure token uniqueness
                while MealPlan.objects.filter(approval_token=meal_plan.approval_token).exclude(id=meal_plan.id).exists():
                    meal_plan.approval_token = uuid.uuid4()
            meal_plan.save()
        
        self.stdout.write(self.style.SUCCESS('Successfully updated approval tokens.'))
