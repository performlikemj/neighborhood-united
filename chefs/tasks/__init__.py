# chefs/tasks/__init__.py
"""
Celery tasks for the chefs app.

This package re-exports tasks from both:
- Legacy tasks (from chefs/tasks.py in parent directory)
- Telegram tasks
- Proactive engine tasks

This hybrid setup allows gradual migration of tasks to the package structure
while maintaining backward compatibility.
"""

import os
import importlib.util

# Load the old tasks.py file (in the parent directory, not in this package)
# This avoids Python's confusion between chefs/tasks.py and chefs/tasks/__init__.py
_tasks_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tasks.py')

if os.path.exists(_tasks_file):
    _spec = importlib.util.spec_from_file_location("chefs._tasks_legacy", _tasks_file)
    _legacy_module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_legacy_module)
    
    # Re-export legacy functions
    notify_waitlist_subscribers_for_chef = _legacy_module.notify_waitlist_subscribers_for_chef
    notify_area_waitlist_users = _legacy_module.notify_area_waitlist_users
else:
    # Fallback in case legacy file doesn't exist (shouldn't happen)
    def notify_waitlist_subscribers_for_chef(*args, **kwargs):
        raise NotImplementedError("Legacy tasks.py not found")
    def notify_area_waitlist_users(*args, **kwargs):
        raise NotImplementedError("Legacy tasks.py not found")

# Export telegram tasks
from .telegram_tasks import process_telegram_update

# Export proactive engine tasks
from .proactive_engine import (
    run_proactive_check,
    send_welcome_notification,
)

__all__ = [
    # Telegram
    'process_telegram_update',
    # Proactive engine
    'run_proactive_check',
    'send_welcome_notification',
    # Legacy
    'notify_waitlist_subscribers_for_chef',
    'notify_area_waitlist_users',
]
