from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from reviews.models import Review
from meals.models import Meal, MealPlan
from django.db import transaction

class Command(BaseCommand):
    help = "Migrate Review model from meal/meal_plan fields to content_type and object_id."

    @transaction.atomic
    def handle(self, *args, **options):
        """
        For each Review:
        - If `meal` is not None, set the content_object to that Meal.
        - Else if `meal_plan` is not None, set the content_object to that MealPlan.
        After completion, all reviews will have content_type/object_id filled in.
        """
        # Get ContentType for Meal and MealPlan
        meal_ct = ContentType.objects.get_for_model(Meal)
        mealplan_ct = ContentType.objects.get_for_model(MealPlan)

        reviews = Review.objects.all()
        updated_count = 0

        for review in reviews:
            # If this review is already migrated, skip
            # i.e., if content_type and object_id are already set.
            if review.content_type_id is not None and review.object_id is not None:
                continue

            if review.meal_id is not None:
                # Review was associated with a Meal
                review.content_type = meal_ct
                review.object_id = review.meal_id
            elif review.meal_plan_id is not None:
                # Review was associated with a MealPlan
                review.content_type = mealplan_ct
                review.object_id = review.meal_plan_id
            else:
                # Review not associated with any old fields?
                # Decide what to do: skip or log warning
                self.stdout.write(self.style.WARNING(f"Review {review.id} has no meal or meal_plan. Skipping."))
                continue

            review.save()
            updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} reviews."))
        self.stdout.write(self.style.SUCCESS("All reviews now have content_type and object_id set."))