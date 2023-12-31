from django.db import models
from custom_auth.models import CustomUser
from meals.models import Dish
from django.utils import timezone

class GoalTracking(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='goal')  # One-to-One
    goal_name = models.CharField(max_length=255)
    goal_description = models.TextField(max_length=1000)  # New field

    def __str__(self):
        return f"{self.goal_name} - {self.user}"


class FoodPreferences(models.Model):
    DIETARY_CHOICES = [
    ('Vegan', 'Vegan'),
    ('Vegetarian', 'Vegetarian'),
    ('Pescatarian', 'Pescatarian'),
    ('Gluten-Free', 'Gluten-Free'),
    ('Keto', 'Keto'),
    ('Paleo', 'Paleo'),
    ('Halal', 'Halal'),
    ('Kosher', 'Kosher'),
    ('Low-Calorie', 'Low-Calorie'),
    ('Low-Sodium', 'Low-Sodium'),
    ('High-Protein', 'High-Protein'),
    ('Dairy-Free', 'Dairy-Free'),
    ('Nut-Free', 'Nut-Free'),
    ('Raw Food', 'Raw Food'),
    ('Whole 30', 'Whole 30'),
    ('Low-FODMAP', 'Low-FODMAP'),
    ('Diabetic-Friendly', 'Diabetic-Friendly'),
    # ... add more as needed
    ]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    dietary_preference = models.CharField(max_length=20, choices=DIETARY_CHOICES, default='None', null=True, blank=True)
    allergies = models.TextField(blank=True)

    def __str__(self):
        return f'Food Preferences for {self.user.username}'


class ChatThread(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_threads')
    title = models.CharField(max_length=255, default="Chat with Assistant")
    openai_thread_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Chat Thread for {self.user.username} - ID: {self.openai_thread_id}"
