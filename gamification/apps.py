from django.apps import AppConfig
from django.conf import settings


class GamificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gamification'
    
    def ready(self):
        # Conditionally enable gamification signal handlers
        if getattr(settings, 'GAMIFICATION_ENABLED', False):
            import gamification.signals
