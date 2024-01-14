from django.db import models
from custom_auth.models import CustomUser
from meals.models import Dish
from django.utils import timezone
from .helper_functions import get_current_week
from meals.models import Meal  # Import the Meal model


class GoalTracking(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='goal')  # One-to-One
    goal_name = models.CharField(max_length=255)
    goal_description = models.TextField(max_length=1000)  # New field

    def __str__(self):
        return f"{self.goal_name} - {self.user}"


class ChatThread(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_threads')
    title = models.CharField(max_length=255, default="Chat with Assistant")
    openai_thread_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Chat Thread for {self.user.username} - ID: {self.openai_thread_id}"


class UserHealthMetrics(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='health_metrics')
    date_recorded = models.DateField(default=timezone.now)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # in kilograms
    bmi = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)  # Body Mass Index
    mood = models.CharField(max_length=50, null=True, blank=True)  # Mood description
    energy_level = models.IntegerField(null=True, blank=True)  # Scale (e.g., 1-10)

    def is_current_week(self):
        start_week, end_week = get_current_week()
        return start_week <= self.date_recorded <= end_week

    def __str__(self):
        return f"Health Metrics for {self.user.username} - Date: {self.date_recorded}"



class CalorieIntake(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='calorie_intake')
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='calorie_intake')  # Use a ForeignKey to the Meal model
    portion_size = models.CharField(max_length=100)  # Define max_length based on your expected input size
    date_recorded = models.DateField(default=timezone.now)

    def __str__(self):
        return f"Calorie Intake for {self.user.username} - Meal ID: {self.meal.id}, Date: {self.date_recorded}"