from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import ChatThread
from .tasks import generate_chat_title
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=ChatThread)
def name_chat_thread_on_creation_or_history_update(sender, instance, created, **kwargs):
    """
    Generates a title for the ChatThread based on the first user message
    after the thread is created.
    """
    # Check if the thread has a default title and has message history
    if instance.title in ["Chat with Assistant", "", None] and instance.openai_input_history:
        # Check if there's at least one user message in the history
        has_user_message = False
        if isinstance(instance.openai_input_history, list):
            for message in instance.openai_input_history:
                if isinstance(message, dict) and message.get('role') == 'user':
                    has_user_message = True
                    break
        
        if has_user_message:
            logger.info(f"Generating title for ChatThread {instance.id} with {len(instance.openai_input_history)} messages")
            generate_chat_title(instance.id)
        else:
            logger.debug(f"ChatThread {instance.id} has no user messages yet, skipping title generation")
