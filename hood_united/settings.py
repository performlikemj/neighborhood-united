"""
Django settings for hood_united project.

Generated by 'django-admin startproject' using Django 4.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
import os
from datetime import timedelta

import json

# Load configuration from config.json
with open('/etc/config.json') as config_file:
    config = json.load(config_file)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config['SECRET_KEY']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '4.242.33.69', 'www.nbhdunited.com', 'nbhdunited.com', 'www.sautai.com', 'sautai.com', 'neighborhoodunited.org', 'hoodunited.org']


# Application definition

INSTALLED_APPS = [
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'chefs',
    'meals',
    'events',
    'reviews',
    'custom_auth',
    'qa_app',
    'django_countries',
    'chef_admin',
    'customer_dashboard',
    'local_chefs',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'stripe',
    'storages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware', # CORS middleware
]

CORS_ALLOWED_ORIGINS = [
    config['STREAMLIT_URL'],  # Add your Streamlit app's origin here
    # "https://example.com",  # Add other origins as needed
]

ROOT_URLCONF = 'hood_united.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'custom_auth.context_processors.role_context_processor',
            ],
        },
    },
]

# WSGI_APPLICATION = 'hood_united.wsgi.application'
# Change from WSGI to ASGI
ASGI_APPLICATION = 'hood_united.asgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

if DEBUG == 'True':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config['DB_NAME'],
            'USER': config['DB_USER'],
            'PASSWORD': config['DB_PASSWORD'],
            'HOST': config['DB_HOST'],
            'PORT': config['DB_PORT'],
        }
    }

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Rest framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

SIMPLE_JWT = {
    'ALGORITHM': 'HS256',
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    # ... other settings
}


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static/')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files
if DEBUG:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
else:
    # Blob Storage
    DEFAULT_FILE_STORAGE = 'storages.backends.azure_storage.AzureStorage'

    AZURE_ACCOUNT_NAME = config['AZURE_ACCOUNT_NAME']  # your azure account name
    AZURE_ACCOUNT_KEY = config['AZURE_ACCOUNT_KEY']  # your azure account key
    AZURE_CONTAINER = config['AZURE_CONTAINER']  # the default container
    AZURE_CUSTOM_DOMAIN = f'{AZURE_ACCOUNT_NAME}.blob.core.windows.net'
    MEDIA_URL = f'https://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/'

# Custom user model
AUTH_USER_MODEL = 'custom_auth.CustomUser'

AUTHENTICATION_BACKENDS = [
    'custom_auth.backends.CaseInsensitiveAuthBackend',  # Replace with the actual path
]


# Login redirects
LOGIN_REDIRECT_URL = 'custom_auth:profile'
LOGIN_URL = 'custom_auth:login'


# OpenAI API keys
# OpenAI API keys
OPENAI_KEY = config['OPENAI_KEY']
SPOONACULAR_API_KEY = config['SPOONACULAR_API_KEY']

# OpenAI prompt
OPENAI_PROMPT = config['OPENAI_PROMPT']

# Stripe API keys
STRIPE_PUBLIC_KEY = config['STRIPE_PUBLIC_KEY']
STRIPE_SECRET_KEY = config['STRIPE_SECRET_KEY']


# Email settings
EMAIL_HOST = config['EMAIL_HOST']
EMAIL_PORT = config['EMAIL_PORT']
EMAIL_USE_TLS = config['EMAIL_USE_TLS']
EMAIL_HOST_USER = config['EMAIL_HOST_USER']
EMAIL_HOST_PASSWORD = config['EMAIL_HOST_PASSWORD']
DEFAULT_FROM_EMAIL = config['DEFAULT_FROM_EMAIL']

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'WARNING',  # Adjusted level
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',  # Adjusted level
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django_warnings.log'),  # Updated filename
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',  # Adjusted level
            'propagate': True,
        },
        'customer_dashboard': {  
            'handlers': ['console', 'file'],
            'level': 'WARNING',  # Adjusted level
            'propagate': True,
        },
    },
}
if DEBUG == False:
# Cookie settings
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = [
        'https://sautai.azurewebsites.net',
        'https://www.sautai.com',
        'https://sautai.com',
        'https://*.127.0.0.1'
    ]

    # HSTS
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    # SSL
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Clickjacking Protection
    X_FRAME_OPTIONS = 'DENY'

    # Other security settings
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Celery settings
    CELERY_BROKER_URL = config['CELERY_BROKER_URL']
    CELERY_RESULT_BACKEND = config['CELERY_RESULT_BACKEND']