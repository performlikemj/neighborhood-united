# meals/signals.py
from django.db.models.signals import post_save, m2m_changed, post_delete, pre_save
from django.dispatch import receiver
from .models import Meal, MealPlan
from django.db import transaction
from customer_dashboard.models import GoalTracking, UserHealthMetrics, CalorieIntake
from custom_auth.models import CustomUser
from django.db import transaction
import requests
from django.core.files.base import ContentFile
from openai import OpenAI
from django.conf import settings
from rest_framework.test import APIRequestFactory
from meals.email_service import generate_shopping_list, generate_user_summary, generate_emergency_supply_list
from meals.meal_instructions import generate_bulk_prep_instructions
from meals.meal_plan_service import create_meal_plan_for_new_user
from meals.pantry_management import assign_pantry_tags

def trigger_assign_pantry_tags(sender, instance, created, **kwargs):
    if created:
        assign_pantry_tags.delay(instance.id)

@receiver(m2m_changed, sender=MealPlan.meal.through)
def mealplan_meal_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.has_changes = True
        instance.is_approved = False  # Reset approval when changes are detected
        instance.save()

@receiver(pre_save, sender=MealPlan)
def pre_save_mealplan(sender, instance, **kwargs):
    if instance.pk:
        previous = MealPlan.objects.get(pk=instance.pk)
        instance._previous_is_approved = previous.is_approved
        instance._previous_has_changes = previous.has_changes
    else:
        instance._previous_is_approved = None
        instance._previous_has_changes = None

@receiver(post_save, sender=MealPlan)
def send_meal_plan_email(sender, instance, **kwargs):
    user = instance.user
    if not user.email_meal_plan_saved:
        return

    # Check if approval status changed from unapproved to approved and has_changes from True to False
    if (
        instance.is_approved and not instance.has_changes and
        (instance._previous_is_approved != instance.is_approved or
         instance._previous_has_changes != instance.has_changes)
    ):
        generate_shopping_list.delay(instance.id)
        if instance.meal_prep_preference == 'one_day_prep':
            generate_bulk_prep_instructions.delay(instance.id)

@receiver(post_save, sender=GoalTracking)
@receiver(post_save, sender=UserHealthMetrics)
@receiver(post_save, sender=CalorieIntake)
def handle_model_update(sender, instance, **kwargs):
    # Check if the signal is post_save and whether the instance was just created
    created = kwargs.get('created', False)

    if created and hasattr(instance, 'email_confirmed') and instance.email_confirmed:  
        if hasattr(instance, 'user_id'):
            user_id = instance.user_id
        elif hasattr(instance, 'user'):
            user_id = instance.user.id
        else:
            return  # Exit if no user is associated with the instance

        print(f"Detected change for user with ID: {user_id}")
        # Use transaction.on_commit to ensure this runs after the transaction has committed
        def trigger_summary_generation():
            generate_user_summary.delay(user_id)  # Queue the task to generate the summary

        transaction.on_commit(trigger_summary_generation)
    elif not created:
        # Handle the case for post_delete or updates
        if hasattr(instance, 'user_id'):
            user_id = instance.user_id
        elif hasattr(instance, 'user'):
            user_id = instance.user.id
        else:
            return  # Exit if no user is associated with the instance

        print(f"Detected deletion or update for user with ID: {user_id}")
        # You can trigger the task here if necessary
        transaction.on_commit(lambda: generate_user_summary.delay(user_id))

@receiver(post_save, sender=CustomUser)
def create_meal_plan_on_user_registration(sender, instance, created, **kwargs):
    if created and instance.email_confirmed:
        # Define a callback function to trigger after the transaction commits
        def trigger_meal_plan_creation():
            create_meal_plan_for_new_user.delay(instance.id)  # Queue the task to create a meal plan

        transaction.on_commit(trigger_meal_plan_creation)
