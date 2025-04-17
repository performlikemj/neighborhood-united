# customer_dashboard > models.py
from django.db import models
from custom_auth.models import CustomUser
from meals.models import Dish
from django.utils import timezone
from .helper_functions import get_current_week
from meals.models import Meal  
import secrets
import string

class AssistantEmailToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    @classmethod
    def generate_token(cls, length=32):
        """Generate a secure random token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @classmethod
    def create_for_user(cls, user):
        """Create a new token for a user."""
        token = cls.generate_token()
        return cls.objects.create(user=user, token=token)
    
    @classmethod
    def validate_and_update_token(cls, token):
        """
        Validate a token and update its last_used_at timestamp.
        
        Returns:
            Tuple of (is_valid, user, token_obj)
        """
        try:
            token_obj = cls.objects.get(token=token, is_active=True)
            token_obj.last_used_at = timezone.now()
            token_obj.save(update_fields=['last_used_at'])
            return True, token_obj.user, token_obj
        except cls.DoesNotExist:
            return False, None, None


class GoalTracking(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='goal')  # One-to-One
    goal_name = models.CharField(max_length=255)
    goal_description = models.TextField(max_length=1000)  # New field

    def __str__(self):
        return f"{self.goal_name} - {self.user}"


class ChatThread(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_threads')
    title = models.CharField(max_length=255, default="Chat with Assistant")
    openai_thread_id = models.CharField(max_length=255, null=True, blank=True)
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