# meals/signals.py
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from .models import Meal, MealPlan
import requests
from django.core.files.base import ContentFile
from openai import OpenAI
from django.conf import settings
from rest_framework.test import APIRequestFactory
from meals.tasks import generate_shopping_list

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
