# meals/signals.py
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver
from django.urls import reverse
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
from meals.tasks import generate_shopping_list, create_meal_plan_for_new_user, generate_user_summary

@receiver(m2m_changed, sender=MealPlan.meal.through)
def mealplan_meal_changed(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.has_changes = True
        instance.is_approved = False  # Reset approval when changes are detected
        instance.save()

@receiver(post_save, sender=MealPlan)
def send_meal_plan_email(sender, instance, created, **kwargs):
    user = instance.user
    if not user.email_meal_plan_saved:
        return  # Skip sending the email if the user has opted out

    # Only trigger the shopping list generation if the meal plan is approved
    if instance.is_approved:
        generate_shopping_list.delay(instance.id)

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

        # Use transaction.on_commit to ensure this runs after the transaction has committed
        transaction.on_commit(trigger_meal_plan_creation)

# @receiver(post_save, sender=Meal)
# def create_meal_image(sender, instance, created, **kwargs):
#     if created and not instance.image:
#         # Generate image using DALL-E 3
#         client = OpenAI(api_key=settings.OPENAI_KEY)
#         prompt = f"A delicious meal: {instance.name}. {instance.description}"
#         response = client.images.generate(
#             model="dall-e-3",
#             prompt=prompt,
#             size="1024x1024",
#             quality="standard",
#             n=1,
#         )
#         image_url = response.data[0].url

#         # Download the image
#         response = requests.get(image_url)
#         if response.status_code == 200:
#             image_name = f'{instance.name}_meal_image.png'
#             instance.image.save(image_name, ContentFile(response.content), save=True)
