# meals/models/utility.py
"""
Utility models: DietaryPreference, CustomDietaryPreference, MealCompatibility, 
MealAllergenSafety, SystemUpdate, and related utility models.
"""

from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.contrib.postgres.fields import ArrayField
from pydantic import ValidationError

from custom_auth.models import CustomUser


def clean_preference_name(value):
    if any(char in value for char in '{}[]"\''):
        raise ValidationError('Preference name cannot contain brackets or quotes')
    return value


class DietaryPreference(models.Model):
    name = models.CharField(
        max_length=100, 
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[^{}\[\]"\']*$',
                message="Name cannot contain brackets or quotes",
                code="invalid_name"
            ),
            clean_preference_name
        ]
    )

    def __str__(self):
        return self.name


class CustomDietaryPreference(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    allowed = models.JSONField(default=list, blank=True)
    excluded = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class SystemUpdate(models.Model):
    subject = models.CharField(max_length=200)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey('custom_auth.CustomUser', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-sent_at']


class MealCompatibility(models.Model):
    """
    Stores the compatibility analysis results between a meal and a dietary preference.
    This caches the results of analyze_meal_compatibility to avoid redundant API calls.
    """
    meal = models.ForeignKey('Meal', on_delete=models.CASCADE, related_name='compatibility_analyses')
    preference_name = models.CharField(max_length=100)
    is_compatible = models.BooleanField(default=False)
    confidence = models.FloatField(default=0.0)
    reasoning = models.TextField(blank=True)
    analyzed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('meal', 'preference_name')
        indexes = [
            models.Index(fields=['meal', 'preference_name']),
        ]
    
    def __str__(self):
        compatibility = "Compatible" if self.is_compatible else "Not compatible"
        return f"{self.meal.name} - {self.preference_name}: {compatibility} ({self.confidence:.2f})"


class MealAllergenSafety(models.Model):
    """
    Tracks whether a meal is safe for a user with allergies.
    This is a caching layer to avoid repeated API calls.
    """
    meal = models.ForeignKey('Meal', on_delete=models.CASCADE, related_name='allergen_safety_checks')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_safe = models.BooleanField(default=False)
    flagged_ingredients = ArrayField(models.CharField(max_length=100), blank=True, default=list)
    reasoning = models.TextField(blank=True)
    last_checked = models.DateTimeField(auto_now=True)
    substitutions = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = ('meal', 'user')
        verbose_name_plural = 'Meal allergen safety checks'

    def __str__(self):
        return f"Allergen check: {self.meal.name} for {self.user.username} - {'Safe' if self.is_safe else 'Unsafe'}"
