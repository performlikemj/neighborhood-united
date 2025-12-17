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


# Regex patterns for Azure internal IPs
INTERNAL_IP_PATTERNS = [
    re.compile(rb'^10\.'),        # 10.x.x.x - Azure internal network
    re.compile(rb'^100\.'),       # 100.x.x.x - Carrier Grade NAT (health probes)
    re.compile(rb'^172\.(1[6-9]|2[0-9]|3[0-1])\.'),  # 172.16-31.x.x - Private range
    re.compile(rb'^192\.168\.'),  # 192.168.x.x - Private range
    re.compile(rb'^127\.'),       # 127.x.x.x - Localhost
]


def is_internal_ip(host_bytes: bytes) -> bool:
    """Check if the host is an internal Azure IP."""
    # Remove port if present
    host_ip = host_bytes.split(b':')[0] if b':' in host_bytes else host_bytes
    return any(pattern.match(host_ip) for pattern in INTERNAL_IP_PATTERNS)


class AzureHostRewriteMiddleware:
    """
    ASGI middleware that rewrites the Host header for internal Azure IPs.
    
    This runs BEFORE Django creates the HttpRequest, so it modifies the raw
    ASGI scope headers. This ensures ALLOWED_HOSTS validation sees 'localhost'
    instead of the internal IP.
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            # Get current headers
            headers = dict(scope.get('headers', []))
            host = headers.get(b'host', b'')
            
            # If it's an internal IP, rewrite the Host header
            if is_internal_ip(host):
                # Create new headers list with modified host
                new_headers = []
                for name, value in scope.get('headers', []):
                    if name == b'host':
                        new_headers.append((b'host', b'localhost'))
                        # Also add X-Forwarded-Host with original value
                        new_headers.append((b'x-forwarded-host', b'localhost'))
                        new_headers.append((b'x-original-host', host))
                    else:
                        new_headers.append((name, value))
                
                # Update scope with new headers
                scope = dict(scope)
                scope['headers'] = new_headers
        
        return await self.app(scope, receive, send)


# Wrap Django's ASGI app with our host rewrite middleware
django_asgi_app = AzureHostRewriteMiddleware(get_asgi_application())

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            hood_united.routing.websocket_urlpatterns
        )
    ),
})
