from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

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
    'create-meal-plan-every-hour': {
        'task': 'meals.meal_plan_service.create_meal_plan_for_all_users',
        'schedule': crontab(minute=0),  # Runs every hour
    },
    'send-meal-plan-reminders': {
        'task': 'meals.email_service.send_meal_plan_reminder_email',
        'schedule': crontab(hour=10, minute=0)  # Runs daily at 10 AM
    },
}
