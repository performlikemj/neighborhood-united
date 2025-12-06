import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone


# Reuse the same choices from CustomUser for consistency
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
    ('Diabetic-Friendly', 'Diabetic-Friendly'),
    ('Everything', 'Everything'),
]

ALLERGY_CHOICES = [
    ('Peanuts', 'Peanuts'),
    ('Tree nuts', 'Tree nuts'),
    ('Milk', 'Milk'),
    ('Egg', 'Egg'),
    ('Wheat', 'Wheat'),
    ('Soy', 'Soy'),
    ('Fish', 'Fish'),
    ('Shellfish', 'Shellfish'),
    ('Sesame', 'Sesame'),
    ('Gluten', 'Gluten'),
    ('None', 'None'),
]


class LeadQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)

    def open(self):
        model = self.model
        return self.filter(
            status__in=[model.Status.NEW, model.Status.CONTACTED, model.Status.QUALIFIED],
            is_deleted=False,
        )

    def by_owner(self, owner):
        return self.filter(owner=owner, is_deleted=False)


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    class Source(models.TextChoices):
        WEB = "web", "Web"
        REFERRAL = "referral", "Referral"
        OUTBOUND = "outbound", "Outbound"
        EVENT = "event", "Event"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_leads",
        null=True,
        blank=True,
    )
    offering = models.ForeignKey(
        "services.ServiceOffering",
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
    )
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    company = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WEB)
    budget_cents = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    is_priority = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Dietary tracking for the primary contact
    dietary_preferences = ArrayField(
        models.CharField(max_length=50, choices=DIETARY_CHOICES),
        default=list,
        blank=True,
        help_text="Dietary preferences for this contact"
    )
    allergies = ArrayField(
        models.CharField(max_length=50, choices=ALLERGY_CHOICES),
        default=list,
        blank=True,
        help_text="Food allergies for this contact"
    )
    custom_allergies = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Custom allergies not in the standard list"
    )
    
    # Household info
    household_size = models.PositiveIntegerField(
        default=1,
        help_text="Total number of people in this household"
    )
    
    # Email verification fields
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the contact's email has been verified"
    )
    email_verification_token = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Secure token for email verification"
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the verification email was last sent"
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the email was verified"
    )

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email_verification_token"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    def generate_verification_token(self):
        """Generate a secure verification token and set sent timestamp."""
        self.email_verification_token = secrets.token_urlsafe(48)
        self.email_verification_sent_at = timezone.now()
        self.save(update_fields=["email_verification_token", "email_verification_sent_at", "updated_at"])
        return self.email_verification_token

    def is_verification_token_valid(self):
        """Check if the verification token is still valid (72 hours)."""
        if not self.email_verification_token or not self.email_verification_sent_at:
            return False
        expiry_time = self.email_verification_sent_at + timedelta(hours=72)
        return timezone.now() < expiry_time

    def verify_email(self, token):
        """Verify the email with the provided token. Returns True if successful."""
        if not self.email_verification_token:
            return False
        if self.email_verification_token != token:
            return False
        if not self.is_verification_token_valid():
            return False
        
        self.email_verified = True
        self.email_verified_at = timezone.now()
        self.email_verification_token = None  # Invalidate token after use
        self.save(update_fields=["email_verified", "email_verified_at", "email_verification_token", "updated_at"])
        return True

    def reset_email_verification(self):
        """Reset email verification status (e.g., when email changes)."""
        self.email_verified = False
        self.email_verified_at = None
        self.email_verification_token = None
        self.email_verification_sent_at = None
        self.save(update_fields=[
            "email_verified", "email_verified_at", 
            "email_verification_token", "email_verification_sent_at", "updated_at"
        ])


class LeadInteractionQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(is_deleted=False)

    def of_type(self, interaction_type):
        return self.filter(interaction_type=interaction_type, is_deleted=False)


class LeadInteraction(models.Model):
    class InteractionType(models.TextChoices):
        NOTE = "note", "Note"
        EMAIL = "email", "Email"
        CALL = "call", "Call"
        MEETING = "meeting", "Meeting"
        DEMO = "demo", "Demo"
        MESSAGE = "message", "Message"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interactions")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_interactions",
    )
    interaction_type = models.CharField(
        max_length=20, choices=InteractionType.choices, default=InteractionType.NOTE
    )
    summary = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    happened_at = models.DateTimeField(default=timezone.now)
    next_steps = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LeadInteractionQuerySet.as_manager()

    class Meta:
        ordering = ["-happened_at", "-id"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.is_deleted:
            self.lead.last_interaction_at = self.happened_at
            self.lead.save(update_fields=["last_interaction_at", "updated_at"])

    def __str__(self):
        return f"{self.get_interaction_type_display()} on {self.happened_at:%Y-%m-%d}"


class LeadHouseholdMember(models.Model):
    """
    Household members for off-platform contacts (Leads).
    Similar to HouseholdMember but for manually tracked clients.
    """
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="household_members"
    )
    name = models.CharField(max_length=100)
    relationship = models.CharField(
        max_length=50,
        blank=True,
        help_text="Relationship to primary contact (spouse, child, parent, etc.)"
    )
    age = models.PositiveIntegerField(blank=True, null=True)
    dietary_preferences = ArrayField(
        models.CharField(max_length=50, choices=DIETARY_CHOICES),
        default=list,
        blank=True,
    )
    allergies = ArrayField(
        models.CharField(max_length=50, choices=ALLERGY_CHOICES),
        default=list,
        blank=True,
    )
    custom_allergies = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.lead})"
