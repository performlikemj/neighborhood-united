# customer_dashboard > models.py
from django.db import models
from custom_auth.models import CustomUser
from meals.models import Dish
from django.utils import timezone
from meals.models import Meal  
import secrets
import string
import uuid
from datetime import timedelta
from django_countries.fields import CountryField
from django.contrib.auth import get_user_model
from datetime import date
from django.conf import settings
from pgvector.django import VectorField

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


class SousChefThread(models.Model):
    """
    Per-family conversation thread for chef's Sous Chef assistant.
    
    Each thread represents an ongoing conversation between a chef and the 
    Sous Chef AI assistant about a specific family (either a platform customer
    or an off-platform CRM lead).
    """
    chef = models.ForeignKey(
        'chefs.Chef', 
        on_delete=models.CASCADE, 
        related_name='sous_chef_threads'
    )
    # Either a platform customer OR a CRM lead (mutually exclusive)
    customer = models.ForeignKey(
        'custom_auth.CustomUser', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='sous_chef_threads',
        help_text="Platform customer this conversation is about"
    )
    lead = models.ForeignKey(
        'crm.Lead', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='sous_chef_threads',
        help_text="CRM lead this conversation is about"
    )
    title = models.CharField(max_length=255, default="Sous Chef Conversation")
    latest_response_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="OpenAI response ID for continuation"
    )
    openai_input_history = models.JSONField(
        default=list, 
        blank=True,
        help_text="Conversation history for OpenAI context"
    )
    # AI-generated summary of older conversation for context preservation
    conversation_summary = models.TextField(
        blank=True, 
        default='',
        help_text="AI-generated summary of truncated conversation history"
    )
    summary_generated_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the conversation summary was last generated"
    )
    messages_summarized_count = models.IntegerField(
        default=0,
        help_text="Number of messages that have been summarized"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['chef', 'customer']),
            models.Index(fields=['chef', 'lead']),
            models.Index(fields=['chef', 'is_active']),
        ]

    def __str__(self):
        family_name = "Unknown"
        if self.customer:
            family_name = f"{self.customer.first_name} {self.customer.last_name}".strip() or self.customer.username
        elif self.lead:
            family_name = f"{self.lead.first_name} {self.lead.last_name}".strip()
        return f"Sous Chef Thread: Chef {self.chef_id} → {family_name}"

    @property
    def family_type(self):
        """Return whether this thread is for a 'customer' or 'lead'."""
        if self.customer_id:
            return 'customer'
        elif self.lead_id:
            return 'lead'
        return None

    @property
    def family_id(self):
        """Return the ID of the associated family."""
        return self.customer_id or self.lead_id

    @property
    def family_name(self):
        """Return a display name for the family."""
        if self.customer:
            full = f"{self.customer.first_name} {self.customer.last_name}".strip()
            return full if full else self.customer.username
        elif self.lead:
            return f"{self.lead.first_name} {self.lead.last_name}".strip()
        return "Unknown Family"


class SousChefMessage(models.Model):
    """
    Individual message within a Sous Chef conversation thread.
    
    Stores both chef messages and assistant responses for history/audit.
    """
    ROLE_CHOICES = [
        ('chef', 'Chef'),
        ('assistant', 'Assistant'),
    ]

    thread = models.ForeignKey(
        SousChefThread, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Metadata for tool calls
    tool_calls = models.JSONField(
        default=list, 
        blank=True,
        help_text="Tool calls made during this response"
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.role}: {preview}"


class FamilyInsight(models.Model):
    """
    Persistent learnings about a family extracted from Sous Chef conversations.
    
    These insights survive conversation resets and are injected into new conversations
    to maintain long-term context about a family's preferences and needs.
    """
    INSIGHT_TYPES = [
        ('preference', 'Preference'),      # "Kids prefer milder spice"
        ('tip', 'Useful Tip'),             # "Double portions on Mondays"
        ('avoid', 'Things to Avoid'),      # "Don't suggest fish on Fridays"
        ('success', 'What Worked Well'),   # "Thai curry was a big hit"
    ]
    
    chef = models.ForeignKey(
        'chefs.Chef', 
        on_delete=models.CASCADE,
        related_name='family_insights'
    )
    # Either a platform customer OR a CRM lead (mutually exclusive)
    customer = models.ForeignKey(
        'custom_auth.CustomUser', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='chef_insights',
        help_text="Platform customer this insight is about"
    )
    lead = models.ForeignKey(
        'crm.Lead', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='chef_insights',
        help_text="CRM lead this insight is about"
    )
    
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    content = models.TextField(
        max_length=500,
        help_text="The insight content (max 500 chars)"
    )
    source_thread = models.ForeignKey(
        SousChefThread, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        related_name='insights',
        help_text="The conversation thread where this insight was discovered"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive insights won't be shown in context"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chef', 'customer']),
            models.Index(fields=['chef', 'lead']),
            models.Index(fields=['chef', 'is_active']),
        ]

    def __str__(self):
        family = "Unknown"
        if self.customer:
            family = f"{self.customer.first_name} {self.customer.last_name}".strip() or self.customer.username
        elif self.lead:
            family = f"{self.lead.first_name} {self.lead.last_name}".strip()
        return f"[{self.insight_type}] {family}: {self.content[:50]}..."

    @property
    def family_type(self):
        """Return whether this insight is for a 'customer' or 'lead'."""
        if self.customer_id:
            return 'customer'
        elif self.lead_id:
            return 'lead'
        return None

    @property
    def family_id(self):
        """Return the ID of the associated family."""
        return self.customer_id or self.lead_id


# ═══════════════════════════════════════════════════════════════════════════════
# CHEF MEMORY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ChefMemory(models.Model):
    """
    Long-term memory storage for Sous Chef assistant, similar to MEMORY.md.
    
    Stores patterns, preferences, lessons, and todos that the Sous Chef learns
    over time and should remember across conversations. These memories are
    automatically injected into the system prompt for relevant conversations.
    
    Examples:
    - pattern: "Monday prep sessions work best with 2-hour blocks"
    - preference: "Chef prefers metric measurements"
    - lesson: "Batch cooking rice saves significant time"
    - todo: "Research gluten-free pasta options for the Chen family"
    """
    MEMORY_TYPES = [
        ('pattern', 'Pattern'),          # Recurring patterns in chef's work
        ('preference', 'Preference'),    # Chef's personal preferences
        ('lesson', 'Lesson Learned'),    # Things learned from experience
        ('todo', 'To-Do/Reminder'),      # Things to remember to do
    ]
    
    IMPORTANCE_CHOICES = [
        (1, 'Low'),
        (2, 'Moderate'),
        (3, 'Normal'),
        (4, 'High'),
        (5, 'Critical'),
    ]
    
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='memories'
    )
    memory_type = models.CharField(
        max_length=20,
        choices=MEMORY_TYPES,
        help_text="Category of this memory"
    )
    content = models.TextField(
        max_length=1000,
        help_text="The memory content (max 1000 chars)"
    )
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata: family_id, source (conversation, observation), tags, etc."
    )
    importance = models.IntegerField(
        choices=IMPORTANCE_CHOICES,
        default=3,
        help_text="How important is this memory? Higher = more likely to be recalled"
    )
    
    # Optional: link to specific family if memory is family-specific
    customer = models.ForeignKey(
        'custom_auth.CustomUser',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chef_memories',
        help_text="If this memory is about a specific platform customer"
    )
    lead = models.ForeignKey(
        'crm.Lead',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='chef_memories',
        help_text="If this memory is about a specific CRM lead"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_accessed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this memory was last used in a conversation"
    )
    access_count = models.IntegerField(
        default=0,
        help_text="How many times this memory has been recalled"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Soft delete - inactive memories won't be recalled"
    )

    # Vector embedding for semantic search
    embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Embedding vector for semantic/hybrid search"
    )

    class Meta:
        ordering = ['-importance', '-updated_at']
        indexes = [
            models.Index(fields=['chef', 'memory_type', 'is_active']),
            models.Index(fields=['chef', 'importance', 'is_active']),
            models.Index(fields=['chef', 'customer']),
            models.Index(fields=['chef', 'lead']),
        ]
        verbose_name = 'Chef Memory'
        verbose_name_plural = 'Chef Memories'
    
    def __str__(self):
        type_label = dict(self.MEMORY_TYPES).get(self.memory_type, self.memory_type)
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"[{type_label}] {preview}"
    
    def mark_accessed(self):
        """Update access tracking when memory is used."""
        self.last_accessed_at = timezone.now()
        self.access_count += 1
        self.save(update_fields=['last_accessed_at', 'access_count'])
    
    @property
    def family_context(self):
        """Return family info if this memory is family-specific."""
        if self.customer:
            return {
                'type': 'customer',
                'id': self.customer_id,
                'name': f"{self.customer.first_name} {self.customer.last_name}".strip() or self.customer.username
            }
        elif self.lead:
            return {
                'type': 'lead',
                'id': self.lead_id,
                'name': f"{self.lead.first_name} {self.lead.last_name}".strip()
            }
        return None
    
    @classmethod
    def get_relevant_for_chef(cls, chef, limit=10, memory_types=None, include_family=None):
        """
        Get the most relevant memories for a chef, optionally filtered.
        
        Args:
            chef: Chef instance
            limit: Max memories to return
            memory_types: List of types to include, or None for all
            include_family: Optional (type, id) tuple to include family-specific memories
        """
        queryset = cls.objects.filter(chef=chef, is_active=True)
        
        if memory_types:
            queryset = queryset.filter(memory_type__in=memory_types)
        
        # Prioritize: importance, then recency, then access frequency
        queryset = queryset.order_by('-importance', '-updated_at', '-access_count')
        
        return list(queryset[:limit])
    
    @classmethod
    def get_relevant_for_family(cls, chef, customer=None, lead=None, limit=5):
        """Get memories specific to a family."""
        from django.db.models import Q
        
        queryset = cls.objects.filter(chef=chef, is_active=True)
        
        if customer:
            queryset = queryset.filter(customer=customer)
        elif lead:
            queryset = queryset.filter(lead=lead)
        else:
            return []
        
        return list(queryset.order_by('-importance', '-updated_at')[:limit])


# ═══════════════════════════════════════════════════════════════════════════════
# PROACTIVE INSIGHTS SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ChefProactiveInsight(models.Model):
    """
    AI-generated proactive recommendations for chefs.
    
    Generated by a daily Celery task that analyzes chef's data and creates
    actionable insights. These appear as notifications in the chef's dashboard.
    
    Insight types:
    - followup_needed: Families who haven't ordered recently
    - batch_opportunity: Common ingredients across upcoming orders
    - seasonal_suggestion: Seasonal menu ideas matching family preferences
    - client_win: Positive feedback to celebrate
    - scheduling_tip: Busy periods or prep optimization tips
    """
    INSIGHT_TYPES = [
        ('followup_needed', 'Follow-up Needed'),
        ('batch_opportunity', 'Batch Cooking Opportunity'),
        ('seasonal_suggestion', 'Seasonal Suggestion'),
        ('client_win', 'Client Win'),
        ('scheduling_tip', 'Scheduling Tip'),
    ]
    
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='proactive_insights'
    )
    insight_type = models.CharField(
        max_length=30,
        choices=INSIGHT_TYPES
    )
    title = models.CharField(
        max_length=200,
        help_text="Short headline for the insight"
    )
    content = models.TextField(
        help_text="Detailed recommendation and context"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Optional: link to specific family
    customer = models.ForeignKey(
        'custom_auth.CustomUser',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chef_proactive_insights',
        help_text="Platform customer this insight is about"
    )
    lead = models.ForeignKey(
        'crm.Lead',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chef_proactive_insights',
        help_text="CRM lead this insight is about"
    )
    
    # Action tracking
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    actioned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the chef took action on this insight"
    )
    action_taken = models.CharField(
        max_length=100,
        blank=True,
        help_text="What action was taken (if any)"
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this insight is no longer relevant"
    )
    
    # Metadata for action suggestions
    action_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data needed to take action (e.g., family_id, suggested message)"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chef', 'is_read', 'is_dismissed']),
            models.Index(fields=['chef', 'insight_type', 'is_dismissed']),
            models.Index(fields=['chef', 'priority', 'is_dismissed']),
            models.Index(fields=['chef', 'expires_at']),
        ]
        verbose_name = 'Chef Proactive Insight'
        verbose_name_plural = 'Chef Proactive Insights'
    
    def __str__(self):
        return f"[{self.get_insight_type_display()}] {self.title}"
    
    def mark_read(self):
        """Mark the insight as read."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def dismiss(self):
        """Dismiss the insight."""
        self.is_dismissed = True
        self.save(update_fields=['is_dismissed'])
    
    def mark_actioned(self, action_taken=''):
        """Mark that action was taken on this insight."""
        self.actioned_at = timezone.now()
        self.action_taken = action_taken
        self.is_read = True
        self.save(update_fields=['actioned_at', 'action_taken', 'is_read'])
    
    @property
    def is_expired(self):
        """Check if this insight has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def family_name(self):
        """Return the family name if this insight is family-specific."""
        if self.customer:
            return f"{self.customer.first_name} {self.customer.last_name}".strip() or self.customer.username
        elif self.lead:
            return f"{self.lead.first_name} {self.lead.last_name}".strip()
        return None
    
    @classmethod
    def get_unread_for_chef(cls, chef, limit=10):
        """Get unread, non-dismissed, non-expired insights for a chef."""
        from django.db.models import Q
        
        now = timezone.now()
        queryset = cls.objects.filter(
            chef=chef,
            is_read=False,
            is_dismissed=False
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        
        # Order by priority, then recency
        priority_order = models.Case(
            models.When(priority='high', then=1),
            models.When(priority='medium', then=2),
            models.When(priority='low', then=3),
            output_field=models.IntegerField(),
        )
        
        return list(queryset.annotate(
            priority_rank=priority_order
        ).order_by('priority_rank', '-created_at')[:limit])
    
    @classmethod
    def get_count_for_chef(cls, chef):
        """Get count of unread, active insights."""
        from django.db.models import Q
        
        now = timezone.now()
        return cls.objects.filter(
            chef=chef,
            is_read=False,
            is_dismissed=False
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).count()