"""
ASGI config for hood_united project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

# hood_united/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import hood_united.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')

# Import JWT middleware for WebSocket authentication
from messaging.middleware import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            hood_united.routing.websocket_urlpatterns
        )
    ),
})
