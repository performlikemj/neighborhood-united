from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Chef
from openai import OpenAI
import requests
from django.core.files.base import ContentFile
from django.utils import timezone
from meals.models import ChefMealEvent, STATUS_SCHEDULED, STATUS_OPEN

from .tasks import notify_waitlist_subscribers_for_chef

@receiver(post_save, sender=Chef)
def create_chef_image(sender, instance, created, **kwargs):
    if created and not instance.profile_pic:
        # Logic to call DALL-E API and save the image
        image_url = generate_chef_image()  # Function to call DALL-E API
        response = requests.get(image_url)
        if response.status_code == 200:
            image_name = f'{instance.user.username}_chef_placeholder.png'
            instance.profile_pic.save(image_name, ContentFile(response.content), save=True)

def generate_chef_image():
    OPENAI_API_KEY = settings.OPENAI_KEY
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = "A gender-neutral chef in a professional kitchen with their back to the camera as if they're preparing a dish."
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    return image_url


@receiver(post_save, sender=ChefMealEvent)
def on_meal_event_saved(sender, instance: ChefMealEvent, created, **kwargs):
    """When a chef creates or updates an orderable event, notify waitlist subscribers once.

    This is a simplified trigger: if an event is orderable (scheduled/open, before cutoff,
    and not at max capacity), fire a background task that emails all active subscribers
    and deactivates their subscriptions to avoid duplicate sends.
    """
    try:
        now = timezone.now()
        if instance.status in [STATUS_SCHEDULED, STATUS_OPEN] and instance.order_cutoff_time and instance.order_cutoff_time > now:
            if instance.max_orders is None or instance.orders_count < instance.max_orders:
                notify_waitlist_subscribers_for_chef.delay(instance.chef_id)
    except Exception:
        # Never raise in signal handler
        return
