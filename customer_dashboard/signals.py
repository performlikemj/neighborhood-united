from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import GoalTracking, UserHealthMetrics, CalorieIntake



