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
from dotenv import load_dotenv
load_dotenv('dev.env')
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'nbhdunited.azurewebsites.net', 'www.nbhdunited.com', 'nbhdunited.com', 'www.sautai.com', 'sautai.com', '169.254.131.6:8000', '169.254.131.3:8000', 'hoodunited.org']


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
    'pgvector',
    'shared',
    'gamification',
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
    os.getenv('STREAMLIT_URL'),  # Add your Streamlit app's origin here
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

# if DEBUG:
#     DATABASES = {
#         'default': {
#             'ENGINE': 'django.db.backends.sqlite3',
#             'NAME': BASE_DIR / 'db.sqlite3',
#         }
#     }
# else:
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('TEST_DB_NAME'),
            'USER': os.getenv('TEST_DB_USER'),
            'PASSWORD': os.getenv('TEST_DB_PASSWORD'),
            'HOST': os.getenv('TEST_DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
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
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
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

    AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME')  # your azure account name
    AZURE_ACCOUNT_KEY = os.getenv('AZURE_ACCOUNT_KEY')  # your azure account key
    AZURE_CONTAINER = os.getenv('AZURE_CONTAINER', 'media')  # the default container
    AZURE_CUSTOM_DOMAIN = f'{AZURE_ACCOUNT_NAME}.blob.core.windows.net'
    MEDIA_URL = f'https://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/'

# Custom user model
AUTH_USER_MODEL = 'custom_auth.CustomUser'

AUTHENTICATION_BACKENDS = [
    'custom_auth.backends.CaseInsensitiveAuthBackend', # Custom backend
    'django.contrib.auth.backends.ModelBackend',  # Default backend
]


# Login redirects
LOGIN_REDIRECT_URL = 'custom_auth:profile'
LOGIN_URL = 'custom_auth:login'


# OpenAI API keys
OPENAI_KEY = os.getenv('OPENAI_KEY')
SPOONACULAR_API_KEY = os.getenv('SPOONACULAR_API_KEY')


# OpenAI prompt
OPENAI_PROMPT = os.getenv('OPENAI_PROMPT')

# Stripe API keys
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')


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
            'level': 'INFO',  # Set to INFO for more concise output
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'DEBUG',  # Keep DEBUG level for detailed output in file
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django_debug.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',  # Set to INFO to reduce verbosity in console
            'propagate': True,
        },
        'customer_dashboard': {
            'handlers': ['console', 'file'],
            'level': 'INFO',  # Set to INFO to reduce verbosity in console
            'propagate': True,
        },
        'meals': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',  # Keep DEBUG level for detailed output in file
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

    # Clickjacking Protection
    X_FRAME_OPTIONS = 'DENY'

    # Other security settings
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True


    # Celery settings
    # Celery settings
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')