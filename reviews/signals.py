from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Review
from shared.utils import generate_review_summary

@receiver(post_save, sender=Review)
def update_review_summary(sender, instance, **kwargs):
    # Determine which object is reviewed
    if instance.meal is not None:
        target_id = instance.meal.id
        target_type = 'meal'
    elif instance.meal_plan is not None:
        target_id = instance.meal_plan.id
        target_type = 'meal_plan'
    else:
        # If neither meal nor meal_plan is set, no summary can be generated
        return

    # Call generate_review_summary with the appropriate arguments
    generate_review_summary(target_id, target_type)