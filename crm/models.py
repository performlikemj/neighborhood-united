from django.conf import settings
from django.db import models
from django.utils import timezone

# settings is required for AUTH_USER_MODEL references on foreign keys


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

    objects = LeadQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


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

        latest_interaction_at = (
            self.lead.interactions.visible()
            .order_by("-happened_at", "-id")
            .values_list("happened_at", flat=True)
            .first()
        )

        if self.lead.last_interaction_at != latest_interaction_at:
            self.lead.last_interaction_at = latest_interaction_at
            self.lead.save(update_fields=["last_interaction_at", "updated_at"])

    def __str__(self):
        return f"{self.get_interaction_type_display()} on {self.happened_at:%Y-%m-%d}"
