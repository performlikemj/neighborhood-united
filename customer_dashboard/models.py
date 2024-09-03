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

class UserMessage(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_messages')
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages', null=True)  # Add null=True
    message = models.TextField()
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    # Define portion size choices
    PORTION_SIZES = (
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='calorie_intake')
    meal_name = models.TextField(null=True, blank=True)  # Store the name of the meal
    meal_description = models.TextField(null=True, blank=True)  # Store a description of the meal
    portion_size = models.CharField(max_length=100, choices=PORTION_SIZES, default='M')
    date_recorded = models.DateField(default=timezone.now)

    def __str__(self):
        return f"Calorie Intake for {self.user.username} on {self.date_recorded}"


class UserSummary(models.Model):
    PENDING = 'pending'
    COMPLETED = 'completed'
    ERROR = 'error'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (ERROR, 'Error'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='summary')
    summary = models.TextField(default="No summary available")  # Store the GPT-generated summary here
    updated_at = models.DateTimeField(auto_now=True)  # Automatically update timestamp on save
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    def __str__(self):
        return f"Summary for {self.user.username}"


class ToolCall(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tool_calls')
    function_name = models.CharField(max_length=255)
    arguments = models.JSONField(default=dict)
    response = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Tool Call: {self.function_name} by {self.user.username} at {self.created_at}"