"""
Celery task utilities for consistent error handling and task management.

TODO: Migrate to utils.error_reporting.report_error() for centralized error tracking.
      When Sentry is integrated, errors will automatically be captured there.
      See utils/error_reporting.py for Sentry integration guide.
"""
import functools
import logging
import traceback

logger = logging.getLogger(__name__)


def handle_task_failure(task_func):
    """
    Decorator to handle Celery task failures consistently.
    Logs the error and handles Redis lock cleanup for meal plan generation tasks.
    
    Note: n8n webhook error reporting has been removed. Errors are now logged
    via Python's logging system. For production error tracking, integrate Sentry.
    See utils/error_reporting.py for integration guide.
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
            
            # TODO: Use utils.error_reporting.report_error() for centralized error tracking
            # Example:
            # from utils.error_reporting import report_error
            # report_error(e, f"celery_task_{task_func.__name__}", {'traceback': tb})
            
            # Re-raise the exception to let Celery handle the task failure
            raise
    
    return wrapper 