from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')

app = Celery('hood_united', broker=settings.CELERY_BROKER_URL)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


app.conf.beat_schedule = {
    'send-daily-meal-instructions-hourly': {
        'task': 'meals.tasks.send_daily_meal_instructions',
        'schedule': crontab(minute=0),  # Runs every hour
    },
    'update-embeddings-daily': {
        'task': 'meals.tasks.update_embeddings',
        'schedule': crontab(hour=0, minute=0),  # Runs every day at midnight
    },
    'create-meal-plan-every-sunday': {
        'task': 'meals.tasks.create_meal_plan_for_all_users',
        'schedule': crontab(hour=6, minute=0, day_of_week='sun'),  # Every Sunday at 6 AM
    },
}
