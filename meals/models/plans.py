# meals/models/plans.py
"""
Meal planning models: MealPlan, MealPlanInstruction, MealPlanMeal, ShoppingList,
Instruction, MealPlanThread, PantryItem, MealPlanMealPantryUsage, and batch processing models.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from django.db.models import Avg
from pydantic import ValidationError

import uuid
import traceback
import logging
from typing import Optional

from custom_auth.models import CustomUser

logger = logging.getLogger(__name__)


class MealPlan(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    meal = models.ManyToManyField('Meal', through='MealPlanMeal')
    reviews = GenericRelation('reviews.Review', related_query_name='mealplan_reviews')
    created_date = models.DateTimeField(auto_now_add=True)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    is_approved = models.BooleanField(default=False)  # Track if the meal plan is approved
    has_changes = models.BooleanField(default=False)  # Track if there are changes to the plan
    approval_token = models.UUIDField(default=uuid.uuid4, unique=True)   
    approval_email_sent = models.BooleanField(default=False)
    instacart_url = models.URLField(max_length=1000, blank=True, null=True, help_text="URL to the Instacart shopping list for this meal plan")
    groq_auto_approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the first auto-approval triggered by Groq batch processing.",
    )
    order = models.OneToOneField(
        'Order',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='associated_meal_plan'
    )

    MEAL_PREP_CHOICES = [
        ('daily', 'Daily Meal Instructions'),
        ('one_day_prep', 'One-Day Meal Prep'),
    ]
    meal_prep_preference = models.CharField(
        max_length=15,
        choices=MEAL_PREP_CHOICES,
        default='daily',
        help_text='User preference for this week.',
    )

    class Meta:
        unique_together = ('user', 'week_start_date', 'week_end_date')

    def clean(self):
        # Custom validation to ensure start_date is before end_date
        if self.week_start_date and self.week_end_date:
            if self.week_start_date >= self.week_end_date:
                raise ValidationError(('The start date must be before the end date.'))

        # Call the parent class's clean method
        super().clean()

    def __str__(self):
        return f"{self.user.username}'s MealPlan for {self.week_start_date} to {self.week_end_date}"

    def save(self, *args, **kwargs):
        was_approved = self.is_approved  # Track approval state before saving

        super().save(*args, **kwargs)  # Save normally

    def average_meal_rating(self):
        """
        Calculate the average rating of all meals in this meal plan using optimized database aggregation.
        FIXED: Previous implementation caused N+1 queries and memory exhaustion.
        """
        # Use database-level aggregation to avoid N+1 query problem
        avg_rating = self.meal.filter(
            reviews__isnull=False
        ).aggregate(
            avg_rating=Avg('reviews__rating')
        )['avg_rating']
        
        return avg_rating
        

class MealPlanInstruction(models.Model):
    meal_plan = models.ForeignKey('MealPlan', on_delete=models.CASCADE)
    instruction_text = models.TextField()
    date = models.DateField()
    is_bulk_prep = models.BooleanField(default=False)

    def __str__(self):
        return f"Instruction for {self.meal_plan.user.username} on {self.date}"
    

class MealPlanMeal(models.Model):
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    MEAL_TYPE_CHOICES = [
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner'),
    ]

    meal = models.ForeignKey('Meal', on_delete=models.CASCADE)
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    meal_date = models.DateField(null=True, blank=True)
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    meal_type = models.CharField(max_length=10, choices=MEAL_TYPE_CHOICES, default='Dinner')
    already_paid = models.BooleanField(default=False, help_text="Flag indicating this meal was paid for in a previous order")

    class Meta:
        # Ensure a meal is unique per day within a specific meal plan, and meal type
        unique_together = ('meal_plan', 'day', 'meal_type')

    def __str__(self):
        meal_name = self.meal.name if self.meal else 'Unknown Meal'
        return f"{meal_name} on {self.day} ({self.meal_type}) for {self.meal_plan}"

    def save(self, *args, **kwargs):
        # Call super().save() before making changes to update meal plan
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # If this is a new MealPlanMeal or an update, we should update the MealPlan
        if is_new or self.meal_plan.has_changes:
            # Mark plan changed and require re‑approval after edits
            self.meal_plan.is_approved = False
            self.meal_plan.has_changes = True
            self.meal_plan.save()

    def delete(self, *args, **kwargs):
        try:
            # Add logging to trace what's happening
            logger.info(f"Attempting to delete MealPlanMeal for {self.meal_plan} on {self.day} ({self.meal_type}).")

            # Access and save the meal_plan before deletion
            meal_plan = self.meal_plan

            # Perform the deletion
            super().delete(*args, **kwargs)
            logger.info(f"Successfully deleted MealPlanMeal for {self.meal_plan} on {self.day} ({self.meal_type}).")

            # Update meal plan status and save changes
            meal_plan.is_approved = False
            meal_plan.has_changes = True
            meal_plan.save()
            logger.info(f"Updated MealPlan {meal_plan} after deleting associated MealPlanMeal.")

        except Exception as e:
            # Log the error with a detailed traceback
            logger.error(f"Error occurred while deleting MealPlanMeal: {e}")
            logger.error(traceback.format_exc())  # This will add the full traceback to the logs
            raise


class ShoppingList(models.Model):
    meal_plan = models.OneToOneField(MealPlan, on_delete=models.CASCADE, related_name='shopping_list')
    items = models.JSONField()  # Store the shopping list items as a JSON object
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Shopping List for {self.meal_plan}'

    def update_items(self, items):
        """Update the shopping list items."""
        self.items = items
        self.save()


class Instruction(models.Model):
    meal_plan_meal = models.OneToOneField(MealPlanMeal, on_delete=models.CASCADE, related_name='instructions', null=True, blank=True)
    content = models.JSONField()  # Store the instructions as a JSON object
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Instructions for {self.meal_plan_meal}'

    def update_content(self, content):
        """Update the instruction content."""
        self.content = content
        self.save()


class MealPlanThread(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    thread_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"MealPlanThread for {self.user.username} with thread_id {self.thread_id}"


class PantryItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Canned', 'Canned'),
        ('Dry', 'Dry Goods'),
    ]

    UNIT_CHOICES = [
        ('oz', 'Ounces'),
        ('lb', 'Pounds'),
        ('g', 'Grams'),
        ('kg', 'Kilograms'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='pantry_items')
    item_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(default=0)  
    marked_as_used = models.BooleanField(default=False)
    tags = models.ManyToManyField('meals.Tag', blank=True)
    expiration_date = models.DateField(blank=True, null=True)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES, default='Canned')
    notes = models.TextField(blank=True, null=True)
    weight_per_unit = models.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="How many ounces or grams per can/bag? (e.g. 14.5 for a 14.5 oz can.)"
    )
    weight_unit = models.CharField(
        max_length=5,
        choices=UNIT_CHOICES,
        blank=True, 
        null=True,
        help_text="The unit for weight_per_unit, e.g. 'oz', 'lb', 'g', etc."
    )

    class Meta:
        indexes = [
            models.Index(fields=['expiration_date']),
        ]
        unique_together = ('user', 'item_name', 'expiration_date')

    def is_expiring_soon(self):
        if self.expiration_date:
            days_until_expiration = (self.expiration_date - timezone.now().date()).days
            return days_until_expiration <= 7  # Consider items expiring within 7 days
        return False  # If no expiration date, assume it's not expiring soon

    def is_expired(self):
        if self.expiration_date:
            return self.expiration_date < timezone.now().date()
        return False  # If no expiration date, assume it's not expired
    
    def available_quantity(self) -> int:
        return self.quantity - self.used_count
    
    def is_fully_used(self) -> bool:
        return self.available_quantity <= 0
    
    def __str__(self):
        return f"{self.item_name} (total={self.quantity}, used={self.used_count})"
    

class MealPlanMealPantryUsage(models.Model):
    """
    Captures how much of a given pantry item is used by a particular MealPlanMeal.
    """
    meal_plan_meal = models.ForeignKey('MealPlanMeal', on_delete=models.CASCADE, related_name='pantry_usage')
    pantry_item = models.ForeignKey('PantryItem', on_delete=models.CASCADE)
    quantity_used = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    usage_unit = models.CharField(
        max_length=5,
        choices=PantryItem.UNIT_CHOICES,
        blank=True, 
        null=True,
        help_text="Unit for quantity_used, e.g. 'oz', 'g', etc."
    )

    def __str__(self):
        return f"{self.meal_plan_meal} uses {self.quantity_used} {self.usage_unit} of {self.pantry_item.item_name}"


class MealPlanBatchJob(models.Model):
    """Tracks Groq batch submissions for weekly meal plan generation."""

    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    week_start_date = models.DateField()
    week_end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    completion_window = models.CharField(max_length=8, default="24h")
    batch_id = models.CharField(max_length=100, blank=True, null=True)
    input_file_id = models.CharField(max_length=100, blank=True, null=True)
    output_file_id = models.CharField(max_length=100, blank=True, null=True)
    error_file_id = models.CharField(max_length=100, blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start_date", "-created_at"]

    def __str__(self):
        return f"MealPlanBatchJob({self.week_start_date}–{self.week_end_date}, status={self.status})"

    def register_members(self, entries):
        """Create or update request rows for the provided user/custom_id tuples."""
        for user_id, custom_id in entries:
            MealPlanBatchRequest.objects.update_or_create(
                job=self,
                user_id=user_id,
                defaults={
                    "custom_id": custom_id,
                    "status": MealPlanBatchRequest.STATUS_PENDING,
                    "response_payload": None,
                    "error": "",
                },
            )

    def mark_request_completed(self, *, custom_id: str, response_payload: Optional[dict] = None):
        request = self.requests.get(custom_id=custom_id)
        request.status = MealPlanBatchRequest.STATUS_COMPLETED
        request.response_payload = response_payload or {}
        request.completed_at = timezone.now()
        request.save(update_fields=["status", "response_payload", "completed_at"])

    def mark_request_failed(self, *, custom_id: str, error_message: str):
        request = self.requests.get(custom_id=custom_id)
        request.status = MealPlanBatchRequest.STATUS_FAILED
        request.error = error_message
        request.completed_at = timezone.now()
        request.save(update_fields=["status", "error", "completed_at"])

    def mark_failed(self, reason: str):
        self.status = self.STATUS_FAILED
        self.failure_reason = reason
        self.save(update_fields=["status", "failure_reason", "updated_at"])

    def mark_expired(self, reason: Optional[str] = None):
        self.status = self.STATUS_EXPIRED
        if reason:
            self.failure_reason = reason
        self.save(update_fields=["status", "failure_reason", "updated_at"])

    def pending_user_ids(self):
        return list(
            self.requests.filter(status=MealPlanBatchRequest.STATUS_PENDING).values_list("user_id", flat=True)
        )

    def users_requiring_fallback(self):
        if self.status in {self.STATUS_FAILED, self.STATUS_EXPIRED}:
            return list(self.requests.values_list("user_id", flat=True))
        return list(
            self.requests.exclude(status=MealPlanBatchRequest.STATUS_COMPLETED).values_list("user_id", flat=True)
        )


class MealPlanBatchRequest(models.Model):
    """Represents an individual request inside a Groq batch job."""

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_FALLBACK = "fallback_scheduled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_FALLBACK, "Fallback Scheduled"),
    ]

    job = models.ForeignKey(MealPlanBatchJob, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey('custom_auth.CustomUser', on_delete=models.CASCADE)
    custom_id = models.CharField(max_length=150, unique=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_PENDING)
    response_payload = models.JSONField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("job", "user")

    def __str__(self):
        return f"BatchRequest(user={self.user_id}, status={self.status})"


class SamplePlanPreview(models.Model):
    """Cached sample meal plan preview for users without chef access.
    
    This stores a one-time generated sample meal plan that shows users
    what their personalized meal plan could look like once a chef is available.
    The plan is read-only and cannot be regenerated.
    
    Structure of plan_data:
    {
        "meals": [
            {
                "day": "Monday",
                "meal_type": "Breakfast",
                "meal_name": "Greek Yogurt Parfait",
                "meal_description": "Creamy Greek yogurt layered with...",
                "servings": 2
            },
            ...
        ],
        "generated_for": {
            "dietary_preferences": ["Vegetarian"],
            "allergies": ["Peanuts"],
            "household_size": 2
        },
        "week_summary": "Your personalized week includes..."
    }
    """
    user = models.OneToOneField(
        'custom_auth.CustomUser',
        on_delete=models.CASCADE,
        related_name='sample_plan_preview'
    )
    plan_data = models.JSONField(
        help_text="JSON structure containing the sample meal plan preview"
    )
    preferences_snapshot = models.JSONField(
        blank=True,
        null=True,
        help_text="Snapshot of user preferences when plan was generated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Sample Plan Preview'
        verbose_name_plural = 'Sample Plan Previews'

    def __str__(self):
        return f"SamplePlanPreview(user={self.user_id}, created={self.created_at})"
