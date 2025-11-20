from django.db import models
from django.utils import timezone


class ServiceOfferingQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, is_deleted=False)

    def for_category(self, category):
        return self.filter(category=category, is_deleted=False)

    def with_tiers(self):
        return self.prefetch_related("tiers")


class ServiceOffering(models.Model):
    class Category(models.TextChoices):
        MEAL_PREP = "meal_prep", "Meal Prep"
        EVENTS = "events", "Events"
        CONSULTING = "consulting", "Consulting"
        SUBSCRIPTION = "subscription", "Subscription"

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.MEAL_PREP)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceOfferingQuerySet.as_manager()

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class ServiceTierQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, is_deleted=False)

    def ordered(self):
        return self.order_by("sort_order", "id")


class ServiceTier(models.Model):
    class BillingCycle(models.TextChoices):
        ONE_TIME = "one_time", "One-time"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        ANNUAL = "annual", "Annual"

    offering = models.ForeignKey(ServiceOffering, on_delete=models.CASCADE, related_name="tiers")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField()
    billing_cycle = models.CharField(max_length=16, choices=BillingCycle.choices, default=BillingCycle.ONE_TIME)
    min_commitment_weeks = models.PositiveIntegerField(default=0)
    max_clients = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceTierQuerySet.as_manager()

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name} ({self.offering.name})"
