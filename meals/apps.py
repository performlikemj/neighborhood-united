from django.apps import AppConfig


class MealsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meals'

    def ready(self):
        # Import signals
        import meals.signals



