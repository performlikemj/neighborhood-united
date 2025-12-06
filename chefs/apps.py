from django.apps import AppConfig


class ChefsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chefs'

    def ready(self):
        import chefs.signals  # noqa: F401
        # Import resource_planning models so Django discovers them for migrations
        import chefs.resource_planning.models  # noqa: F401