import functools
import logging
import traceback
import requests
from django.conf import settings
from celery import shared_task

logger = logging.getLogger(__name__)

def handle_task_failure(task_func):
    """
    Decorator to handle Celery task failures consistently.
    Sends traceback to N8N webhook and logs the error.
    """
    @functools.wraps(task_func)
    def wrapper(*args, **kwargs):
        try:
            return task_func(*args, **kwargs)
        except Exception as e:
            # Get the full traceback
            tb = traceback.format_exc()
            
            # Log the error with traceback
            logger.error(f"Task {task_func.__name__} failed: {str(e)}\nTraceback:\n{tb}")
            
            # Send traceback to N8N webhook if configured
            n8n_traceback_url = getattr(settings, 'N8N_TRACEBACK_URL', None)
            if n8n_traceback_url:
                try:
                    requests.post(n8n_traceback_url, json={
                        "error": str(e),
                        "source": f"celery_task_{task_func.__name__}",
                        "traceback": tb
                    })
                except Exception as webhook_error:
                    logger.error(f"Failed to send error to N8N webhook: {str(webhook_error)}")
            
            # Re-raise the exception to let Celery handle the task failure
            raise
    
    return wrapper 