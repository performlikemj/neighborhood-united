from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.signals import worker_ready, task_postrun
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

app.conf.beat_schedule = {
    'send-daily-meal-instructions-hourly': {
        'task': 'meals.meal_instructions.send_daily_meal_instructions',
        'schedule': crontab(minute=0),  # Runs every hour
    },
    'update-embeddings-daily': {
        'task': 'meals.meal_embedding.update_embeddings',
        'schedule': crontab(hour=0, minute=0),  # Runs every day at midnight
    },
    # Weekly Groq batch submission kicks off early Friday so results are
    # ready for Saturday publishing.
    'submit-weekly-meal-plan-batch': {
        'task': 'meals.tasks.submit_weekly_meal_plan_batch',
        'schedule': crontab(day_of_week='fri', hour=0, minute=5),
    },
    # Poll in-flight batches twice an hour to ingest completed results or
    # trigger synchronous fallback when needed.
    'poll-incomplete-meal-plan-batches': {
        'task': 'meals.tasks.poll_incomplete_meal_plan_batches',
        'schedule': crontab(minute='*/30'),
    },
    # Removed: meal plan reminders are no longer sent

    'sync-all-chef-payments': {
        'task': 'meals.tasks.sync_all_chef_payments',
        'schedule': crontab(hour=0, minute=0),  # Runs daily at midnight
    },
    'process-chef-meal-price-adjustments': {
        'task': 'meals.tasks.process_chef_meal_price_adjustments',
        'schedule': crontab(day_of_week='monday', hour=3, minute=0),  # Run every Monday at 3:00 AM
        'args': (),
    },
    'generate-daily-user-summaries': {
        'task': 'meals.tasks.generate_daily_user_summaries',
        'schedule': crontab(minute=0),  # Run hourly to catch users in all time zones
        'args': (),
    },
    'summarize-user-chat-sessions': {
        'task': 'customer_dashboard.tasks.summarize_user_chat_sessions',
        'schedule': crontab(minute=30),  # Run every hour at X:30 to check for users in different timezones
    },
    'create-weekly-chat-threads': {
        'task': 'meals.tasks.create_weekly_chat_threads',
        'schedule': crontab(day_of_week='monday', hour=0, minute=5),  # Run every Monday at 00:05
        'args': (),
    },
    'cleanup-expired-sessions': {
        'task': 'customer_dashboard.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
    },
    'cleanup-old-meal-plans-and-meals': {
        'task': 'meals.tasks.cleanup_old_meal_plans_and_meals',
        'schedule': crontab(hour=3, minute=0),  # Run daily at 3 AM
        'args': (),
    },
    # Heartbeat every minute to confirm Beat is running
    # 'celery-beat-heartbeat': {
    #     'task': 'meals.tasks.celery_beat_heartbeat',
    #     'schedule': crontab(),  # every minute
    # },
    'sync-service-tier-prices': {
        'task': 'chef_services.tasks.sync_pending_service_tiers',
        'schedule': crontab(minute='*/5'),  # every 5 minutes
    },
}


@task_postrun.connect
def close_database_connections(**kwargs):
    """
    Close all database connections after each task to prevent stale connections.
    Critical for Azure PostgreSQL which closes idle connections after ~5 minutes.
    """
    from django.db import connections
    for conn in connections.all():
        conn.close()


@worker_ready.connect
def _start_monitor_on_worker_ready(sender=None, **kwargs):
    """
    Start the beat monitor task once the worker is fully booted.
    Uses a short countdown to avoid thundering herd on multi-worker setups.
    """
    # Feature flag: gate the monitor wiring to reduce noise when disabled
    if os.getenv("CELERY_BEAT_MONITOR_ENABLED", "false").lower() != "true":
        return
    try:
        from meals.tasks import monitor_celery_beat
        # delay a few seconds to ensure caches and network are available
        monitor_celery_beat.apply_async(countdown=5)
    except Exception:
        # Avoid raising during startup; logging via Celery logger
        import logging
        logging.getLogger(__name__).exception("Failed to start monitor_celery_beat on worker_ready")
