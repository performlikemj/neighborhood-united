from __future__ import absolute_import, unicode_literals

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

# Make celery app available as both 'celery_app' and 'celery'
# so that both -A hood_united and -A hood_united.celery_app work
celery = celery_app

__all__ = ('celery_app', 'celery')