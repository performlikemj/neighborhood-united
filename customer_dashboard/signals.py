# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import GoalTracking, UserHealthMetrics, CalorieIntake
from .views import generate_user_summary

@receiver(post_save, sender=GoalTracking)
@receiver(post_delete, sender=GoalTracking)
@receiver(post_save, sender=UserHealthMetrics)
@receiver(post_delete, sender=UserHealthMetrics)
@receiver(post_save, sender=CalorieIntake)
@receiver(post_delete, sender=CalorieIntake)
def handle_model_update(sender, instance, **kwargs):
    if hasattr(instance, 'user_id'):
        user_id = instance.user_id
    elif hasattr(instance, 'user'):
        user_id = instance.user.id
    else:
        return  # Exit if no user is associated with the instance
    
    (generate_user_summary(user_id))
