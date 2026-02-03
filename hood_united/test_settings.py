# hood_united/test_settings.py
"""
Test-specific settings using SQLite for fast, isolated tests.
"""

import os

# Set required environment variables before importing settings
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')

from hood_united.settings import *  # noqa: F401, F403

# Override database to use SQLite in memory
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Use a simple cache backend for tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Telegram integration settings for tests
TELEGRAM_BOT_TOKEN = 'test-bot-token-12345'
TELEGRAM_BOT_USERNAME = 'TestSautaiBot'
TELEGRAM_WEBHOOK_SECRET = 'test-secret-token-12345'

# Disable SSL redirect for tests
SECURE_SSL_REDIRECT = False
DEBUG = True

# Disable migrations for tests (SQLite incompatibility with PostgreSQL-specific migrations)
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()
