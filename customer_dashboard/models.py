# customer_dashboard > models.py
from django.db import models
from custom_auth.models import CustomUser
from meals.models import Dish
from django.utils import timezone
from .helper_functions import get_current_week
from meals.models import Meal  
import secrets
import string
import uuid
from datetime import timedelta
from django_countries.fields import CountryField
from django.contrib.auth import get_user_model
from datetime import date
from django.conf import settings

User = get_user_model()

class EmailAggregationSession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_aggregation_sessions')
    session_identifier = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    
    # Metadata from the first email that started this session
    recipient_email = models.EmailField(help_text="The original sender's email to reply to.")
    user_email_token = models.CharField(max_length=255, help_text="The user's token from mj+<token>@sautai.com")
    original_subject = models.CharField(max_length=1024, blank=True, null=True)
    in_reply_to_header = models.TextField(null=True, blank=True)
    email_thread_id = models.CharField(max_length=255, null=True, blank=True, help_text="e.g., Gmail's thread ID")
    openai_thread_context_id_initial = models.CharField(max_length=255, null=True, blank=True, help_text="OpenAI thread ID if passed with the first email")

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, db_index=True, help_text="Set to False after Celery task processes it.")
    # We can add a scheduled_processing_time if we want to track when Celery task is due

    def __str__(self):
        return f"Aggregation for {self.user.username} ({self.session_identifier}) created at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class AggregatedMessageContent(models.Model):
    session = models.ForeignKey(EmailAggregationSession, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    # Add any other per-message specific metadata if needed, though most should be on the session

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message for session {self.session.session_identifier} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
class AssistantEmailToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_auth_tokens')
    # auth_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    auth_token = models.UUIDField(default=uuid.uuid4, max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token {self.auth_token} for {self.user.username}"

class UserEmailSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=settings.EMAIL_SESSION_EXPIRY_HOURS if hasattr(settings, 'EMAIL_SESSION_EXPIRY_HOURS') else 24) # Default to 24 hours
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Email session for {self.user.username} - Expires at {self.expires_at.strftime('%Y-%m-%d %H:%M')}"

class GoalTracking(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='goal')  # One-to-One
    goal_name = models.CharField(max_length=255)
    goal_description = models.TextField(max_length=1000)  # New field

    def __str__(self):
        return f"{self.goal_name} - {self.user}"


class ChatThread(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_threads')
    title = models.CharField(max_length=255, default="Chat with Assistant")
    openai_thread_id = models.JSONField(default=list, blank=True)
    latest_response_id = models.CharField(max_length=255, null=True, blank=True)
    openai_input_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    announcement_shown = models.DateField(null=True, blank=True)  # Track if weekly announcement was shown

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


class UserDailySummary(models.Model):
    PENDING = 'pending'
    COMPLETED = 'completed'
    ERROR = 'error'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (ERROR, 'Error'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='daily_summaries')
    summary_date = models.DateField(default=timezone.localdate)  # today for the user
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    summary = models.TextField(blank=True)
    data_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of latest data bundle
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # New fields for SSE and follow-ups
    ticket = models.CharField(max_length=36, blank=True, null=True, db_index=True)  # For SSE tracking
    recommend_prompt = models.JSONField(blank=True, null=True)  # Store follow-up suggestions
    
    class Meta:
        unique_together = ('user', 'summary_date')
        ordering = ['-summary_date']
    
    def __str__(self):
        return f"Daily summary for {self.user.username} on {self.summary_date}"


class ToolCall(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tool_calls')
    function_name = models.CharField(max_length=255)
    arguments = models.JSONField(default=dict)
    response = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Tool Call: {self.function_name} by {self.user.username} at {self.created_at}"

# Admin weekly announcements
class WeeklyAnnouncement(models.Model):
    week_start = models.DateField(
        help_text="The Monday that starts this announcement week. If you select another day, it will be adjusted to the previous Monday."
    )                    # Monday ISO start
    country = CountryField(
        blank=True, 
        null=True,
        help_text="Leave blank for a global announcement that shows to all users regardless of region. Global announcements will be shown together with region-specific announcements."
    )      # Target locale
    content = models.TextField(
        help_text="The announcement text that will be shown to users via MJ, the meal planning assistant."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        null=True, 
        on_delete=models.SET_NULL,
        limit_choices_to={'is_staff': True},  # Only allow staff/admin users
        help_text="The admin who created this announcement."
    )

    class Meta:
        # one message per week *per country*; null = "global"
        unique_together = ("week_start", "country")
        ordering = ["-week_start", "country"]
        verbose_name = "Weekly Announcement"
        verbose_name_plural = "Weekly Announcements"

    def clean(self):
        # Ensure week_start is a Monday
        if self.week_start and self.week_start.weekday() != 0:  # 0 = Monday
            from datetime import timedelta
            days_since_monday = self.week_start.weekday()
            self.week_start = self.week_start - timedelta(days=days_since_monday)

    def __str__(self):
        where = self.country.code if self.country else "GLOBAL"
        return f"{self.week_start} · {where} · {self.content[:40]}…"
        
    @classmethod
    def get_week_start(cls, target_date=None):
        """Get the Monday date of the week containing the target_date"""
        if target_date is None:
            target_date = timezone.localdate()
        
        # Get ISO calendar info (year, week number, weekday)
        iso_year, iso_week, _ = target_date.isocalendar()
        
        # Create date for Monday of that week
        return date.fromisocalendar(iso_year, iso_week, 1)
    
    @classmethod
    def create_for_week(cls, content, country=None, target_date=None, created_by=None):
        """
        Create an announcement for the week containing target_date.
        If target_date is None, uses current date.
        """
        week_start = cls.get_week_start(target_date)
        
        announcement = cls(
            week_start=week_start,
            country=country,
            content=content,
            created_by=created_by
        )
        announcement.save()
        return announcement
    
    @classmethod
    def create_for_next_week(cls, content, country=None, created_by=None):
        """Create an announcement for next week"""
        today = timezone.localdate()
        next_week = today + timezone.timedelta(days=7)
        return cls.create_for_week(content, country, next_week, created_by)

class ChatSessionSummary(models.Model):
    """
    Stores daily summaries of a user's MealPlanningAssistant chat sessions.
    """
    PENDING = 'pending'
    COMPLETED = 'completed'
    ERROR = 'error'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (ERROR, 'Error'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='chat_session_summaries')
    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='summaries')
    summary_date = models.DateField(default=timezone.localdate)
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    last_message_processed = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'thread', 'summary_date')
        ordering = ['-summary_date']
        verbose_name = 'Chat Session Summary'
        verbose_name_plural = 'Chat Session Summaries'
    
    def __str__(self):
        return f"Chat summary for {self.user.username} on {self.summary_date}"

class UserChatSummary(models.Model):
    """
    Consolidated summary of all chat sessions for a user.
    """
    PENDING = 'pending'
    COMPLETED = 'completed'
    ERROR = 'error'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (ERROR, 'Error'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='chat_summary')
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    last_summary_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Chat Summary'
        verbose_name_plural = 'User Chat Summaries'
    
    def __str__(self):
        return f"Consolidated chat summary for {self.user.username}"

class PreAuthenticationMessage(models.Model):
    # Link to the specific auth token that was generated for this message
    # When this token is used or expires and is cleaned up, this message can be handled.
    auth_token = models.OneToOneField(
        AssistantEmailToken,
        on_delete=models.CASCADE, # If the token is deleted, this pending message is also deleted.
        related_name='pending_message_for_token'
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='pre_auth_pending_messages'
    )
    content = models.TextField()
    original_subject = models.CharField(max_length=1024, null=True, blank=True)
    
    # Metadata needed to start an EmailAggregationSession if auth is successful
    # These would be copied from the initial email.
    sender_email = models.EmailField() # The user's actual email address
    in_reply_to_header = models.TextField(null=True, blank=True)
    email_thread_id = models.CharField(max_length=255, null=True, blank=True)
    openai_thread_context_id = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pending message for user {self.user.username} (Token: {self.auth_token.auth_token}) at {self.created_at.strftime('%Y-%m-%d %H:%M')}"