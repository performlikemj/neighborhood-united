"""
ASGI config for hood_united project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

# hood_united/asgi.py
import os
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hood_united.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import hood_united.routing

# Import JWT middleware for WebSocket authentication
from messaging.middleware import JWTAuthMiddlewareStack


# Regex patterns for Azure internal IPs (100.x.x.x range used by CGNAT/health probes)
INTERNAL_IP_PATTERN = re.compile(rb'^(10\.|100\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|127\.)')


class AzureHostRewriteMiddleware:
    """
    ASGI middleware that rewrites Host header for Azure internal IPs.
    This MUST wrap the entire ProtocolTypeRouter to intercept requests
    before Django processes them.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope.get('headers', []))
            host = headers.get(b'host', b'')
            
            # Extract IP (remove port if present)
            host_ip = host.split(b':')[0] if b':' in host else host
            
            # If it's an internal IP, rewrite Host header to localhost
            if INTERNAL_IP_PATTERN.match(host_ip):
                new_headers = [
                    (b'host', b'localhost') if name == b'host' else (name, value)
                    for name, value in scope.get('headers', [])
                ]
                scope = dict(scope)
                scope['headers'] = new_headers
        
        return await self.app(scope, receive, send)


# Build the base application
_base_app = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            hood_united.routing.websocket_urlpatterns
        )
    ),
})

# Wrap with host rewrite middleware - this MUST be the outermost layer
application = AzureHostRewriteMiddleware(_base_app)
