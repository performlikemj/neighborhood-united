import functools
import logging
import traceback
import requests
from django.conf import settings
from celery import shared_task
import os
logger = logging.getLogger(__name__)

def handle_task_failure(task_func):
    """
    Decorator to handle Celery task failures consistently.
    Sends traceback to N8N webhook and logs the error.
    Also handles Redis lock cleanup for meal plan generation tasks.
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
            
            # Special handling for meal plan generation tasks - clean up Redis locks
            if task_func.__name__ == 'create_meal_plan_for_user':
                try:
                    from utils.redis_client import delete
                    
                    # Extract user_id and start_of_week from kwargs to construct lock key
                    user_id = kwargs.get('user_id')
                    start_of_week = kwargs.get('start_of_week')
                    
                    if user_id and start_of_week:
                        lock_key = f"meal_plan_generation_lock_{user_id}_{start_of_week.strftime('%Y_%m_%d')}"
                        deleted = delete(lock_key)
                        if deleted:
                            logger.info(f"Cleaned up Redis lock {lock_key} due to task failure")
                        else:
                            logger.debug(f"Redis lock {lock_key} was not found or already expired during failure cleanup")
                    else:
                        logger.warning(f"Could not extract user_id or start_of_week from task args for lock cleanup")
                        
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up Redis lock during task failure: {str(cleanup_error)}")
            
            # Send traceback to N8N webhook if configured
            n8n_traceback_url = os.getenv('N8N_TRACEBACK_URL', '')
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