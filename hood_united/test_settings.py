# hood_united/test_settings.py
"""
Test settings using SQLite for local testing without PostgreSQL.
"""
import os

# Set required env vars before importing settings
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('TEST_MODE', 'True')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('ALLOWED_HOSTS', '*')

from .settings import *  # noqa

# Override database to use SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_db',
        'USER': 'test_user',
        'PASSWORD': 'test_password',
        'HOST': '127.0.0.1',
        'PORT': '5433',
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Speed up password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster test setup (use --run-syncdb)
class DisableMigrations:
    def __contains__(self, item):
        return True
    def __getitem__(self, item):
        return None

# Uncomment to skip migrations entirely (faster but may miss migration bugs):
# MIGRATION_MODULES = DisableMigrations()
