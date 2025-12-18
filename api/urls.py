"""
API URL configuration.

Includes endpoints for:
- QStash cron triggers (replaces Celery Beat)
"""
from django.urls import path
from . import cron_triggers

urlpatterns = [
    # QStash cron trigger endpoints
    path('cron/trigger/<str:task_name>/', cron_triggers.trigger_task, name='qstash_trigger_task'),
    path('cron/trigger-debug/<str:task_name>/', cron_triggers.trigger_task_debug, name='qstash_trigger_task_debug'),
    path('cron/tasks/', cron_triggers.list_tasks, name='qstash_list_tasks'),
]

