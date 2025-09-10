from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class ChefServiceOffering(models.Model):
    SERVICE_TYPE_CHOICES = [
        ("home_chef", "Personal Home Chef"),
        ("weekly_prep", "Weekly Meal Prep"),
    ]

    chef = models.ForeignKey("chefs.Chef", on_delete=models.CASCADE, related_name="service_offerings")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    default_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    max_travel_miles = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["chef", "service_type", "active"]),
        ]
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.get_service_type_display()} (chef={self.chef_id}, id={self.id})"


class ChefServicePriceTier(models.Model):
    RECURRENCE_CHOICES = [
        ("week", "Per Week"),
    ]

    offering = models.ForeignKey(ChefServiceOffering, on_delete=models.CASCADE, related_name="tiers")
    household_min = models.PositiveIntegerField()
    household_max = models.PositiveIntegerField(null=True, blank=True, help_text="Null means no upper bound")

    currency = models.CharField(max_length=10, default="usd")
    stripe_price_id = models.CharField(max_length=200, blank=True, null=True, help_text="Provided by MCP server")

    is_recurring = models.BooleanField(default=False)
    recurrence_interval = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, null=True, blank=True)

    active = models.BooleanField(default=True)
    display_label = models.CharField(max_length=120, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["household_min", "household_max", "id"]
        indexes = [
            models.Index(fields=["offering", "active"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(household_min__gte=1),
                name="tier_household_min_gte_1",
            ),
            models.CheckConstraint(
                check=(models.Q(household_max__isnull=True) | models.Q(household_max__gte=models.F('household_min'))),
                name="tier_household_max_gte_min_or_null",
            ),
            models.CheckConstraint(
                check=(models.Q(is_recurring=False, recurrence_interval__isnull=True) | models.Q(is_recurring=True, recurrence_interval__isnull=False)),
                name="tier_recurring_interval_consistency",
            ),
        ]

    def __str__(self):
        label = self.display_label or f"{self.household_min}-{self.household_max or '∞'}"
        kind = "recurring" if self.is_recurring else "one-time"
        return f"Tier({label}, {kind}, offering={self.offering_id})"

    def clean(self):
        # Range validation
        if self.household_min == 0:
            raise ValidationError({"household_min": "Minimum household size must be at least 1."})
        if self.household_max is not None and self.household_max < self.household_min:
            raise ValidationError({"household_max": "Max must be greater than or equal to min."})

        # Recurrence validation
        if self.is_recurring and not self.recurrence_interval:
            raise ValidationError({"recurrence_interval": "Required when is_recurring is True."})
        if not self.is_recurring and self.recurrence_interval:
            raise ValidationError({"recurrence_interval": "Must be null for one-time tiers."})

        # Overlap validation: prevent overlapping ranges within the same offering for ACTIVE tiers only
        # Allow overlapping drafts/inactive tiers to exist simultaneously
        if self.active:
            # Treat None (no upper bound) as infinity
            this_min = self.household_min
            this_max = self.household_max or 10**9
            qs = ChefServicePriceTier.objects.filter(offering=self.offering, active=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            for other in qs:
                other_min = other.household_min
                other_max = other.household_max or 10**9
                if not (this_max < other_min or other_max < this_min):
                    # Overlap
                    raise ValidationError("Overlapping household size ranges are not allowed for the same offering.")


class ChefServiceOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("awaiting_payment", "Awaiting Payment"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
        ("completed", "Completed"),
    ]

    customer = models.ForeignKey("custom_auth.CustomUser", on_delete=models.PROTECT, related_name="service_orders")
    chef = models.ForeignKey("chefs.Chef", on_delete=models.PROTECT, related_name="service_orders")
    offering = models.ForeignKey(ChefServiceOffering, on_delete=models.PROTECT, related_name="orders")
    tier = models.ForeignKey(ChefServicePriceTier, on_delete=models.PROTECT, related_name="orders")
    household_size = models.PositiveIntegerField()

    service_date = models.DateField(null=True, blank=True)
    service_start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    address = models.ForeignKey("custom_auth.Address", on_delete=models.SET_NULL, null=True, blank=True)
    special_requests = models.TextField(blank=True)

    # Recurring preferences (e.g., preferred weekday/time) when subscription
    schedule_preferences = models.JSONField(null=True, blank=True)

    stripe_session_id = models.CharField(max_length=200, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=200, null=True, blank=True)
    is_subscription = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["chef", "status"]),
            models.Index(fields=["customer", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(household_size__gte=1),
                name="order_household_size_gte_1",
            ),
        ]

    def __str__(self):
        return f"ServiceOrder(id={self.id}, offering={self.offering_id}, tier={self.tier_id}, status={self.status})"

    def clean(self):
        errors = {}

        # Ensure tier belongs to offering and chef matches
        if self.tier and self.offering and self.tier.offering_id != self.offering_id:
            errors["tier"] = "Selected tier does not belong to the offering."
        if self.offering and self.chef and self.offering.chef_id != self.chef_id:
            errors["offering"] = "Offering does not belong to the selected chef."

        # Household size within tier range
        if self.tier and self.household_size:
            max_sz = self.tier.household_max or 10**9
            if not (self.tier.household_min <= self.household_size <= max_sz):
                errors["household_size"] = "Household size is not within the selected tier's bounds."

        # Schedule validation
        if self.offering:
            if self.offering.service_type == "home_chef":
                if not self.service_date or not self.service_start_time:
                    errors["service_date"] = "Service date and start time are required for home chef."
            elif self.offering.service_type == "weekly_prep":
                if self.tier and self.tier.is_recurring:
                    # For subscriptions, accept schedule_preferences or a date/time as a fallback
                    if not self.schedule_preferences and (not self.service_date or not self.service_start_time):
                        errors["schedule_preferences"] = "Provide schedule_preferences or a preferred date/time for recurring weekly prep."
                else:
                    # One-time weekly prep requires specific date/time
                    if not self.service_date or not self.service_start_time:
                        errors["service_date"] = "Service date and start time are required for one-time weekly prep."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Derive is_subscription from tier if present
        if self.tier_id:
            try:
                tier = self.tier if isinstance(self.tier, ChefServicePriceTier) else None
                if tier is None:
                    tier = ChefServicePriceTier.objects.only("is_recurring").get(id=self.tier_id)
                self.is_subscription = bool(tier.is_recurring)
            except ChefServicePriceTier.DoesNotExist:
                pass
        super().save(*args, **kwargs)
