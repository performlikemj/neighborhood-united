"""
=============================================================================
CELERY CONFIGURATION - DECOMMISSIONED
=============================================================================
Celery workers have been replaced with synchronous task execution via QStash.
Tasks are now executed directly when QStash triggers the webhook endpoints
defined in api/cron_triggers.py.

This file is kept for reference and backwards compatibility with any code
that imports from hood_united.celery. The Celery app is still configured
but no workers should be running.

Migration summary:
- QStash replaces Celery Beat for scheduling
- Tasks run synchronously in Django HTTP request context
- No Redis polling = massive reduction in Redis usage
=============================================================================
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.signals import task_postrun
from django.conf import settings
from celery.schedules import crontab
from dotenv import load_dotenv
load_dotenv("/etc/myapp/config.env")
# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')

app = Celery('hood_united')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# NOTE: Celery Beat and workers have been DECOMMISSIONED.
# These schedules are kept for documentation only - actual scheduling
# is now done via QStash (see api/cron_triggers.py for task mappings).
app.conf.beat_schedule = {
    # Meal/embedding tasks
    'update-embeddings-daily': {
        'task': 'meals.meal_embedding.update_embeddings',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'submit-weekly-meal-plan-batch': {
        'task': 'meals.tasks.submit_weekly_meal_plan_batch',
        'schedule': crontab(day_of_week='fri', hour=0, minute=5),  # Friday 00:05
    },
    'poll-incomplete-meal-plan-batches': {
        'task': 'meals.tasks.poll_incomplete_meal_plan_batches',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'cleanup-old-meal-plans-and-meals': {
        'task': 'meals.tasks.cleanup_old_meal_plans_and_meals',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    
    # Chef payment tasks
    'sync-all-chef-payments': {
        'task': 'meals.tasks.sync_all_chef_payments',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'process-chef-meal-price-adjustments': {
        'task': 'meals.tasks.process_chef_meal_price_adjustments',
        'schedule': crontab(day_of_week='monday', hour=3, minute=0),  # Monday 3 AM
    },
    'sync-service-tier-prices': {
        'task': 'chef_services.tasks.sync_pending_service_tiers',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    
    # Cleanup tasks
    'cleanup-expired-sessions': {
        'task': 'customer_dashboard.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}


@task_postrun.connect
def close_database_connections(**kwargs):
    """
    Close all database connections after each task to prevent stale connections.
    Critical for Azure PostgreSQL which closes idle connections after ~5 minutes.
    
    NOTE: With CELERY_TASK_ALWAYS_EAGER=True, tasks run in the same process
    as Django, so this may not be necessary. Kept for safety.
    """
    from django.db import connections
    for conn in connections.all():
        conn.close()


# NOTE: worker_ready signal handler removed - Celery workers are decommissioned.
# Beat monitoring is no longer needed since QStash handles scheduling.
