from django.apps import AppConfig


class ChefServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chef_services'
    verbose_name = 'Chef Services'
    
    def ready(self):
        # Import signals to register them
        from chef_services import signals  # noqa: F401
