from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import GoalTracking, UserHealthMetrics, CalorieIntake
from meals.tasks import generate_user_summary  # Import the Celery task

