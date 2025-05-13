from django.apps import AppConfig


class ChefsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chefs'


class YourAppConfig(AppConfig):
    name = 'chefs'

    def ready(self):
        import chefs.signals  # Replace with your actual app name