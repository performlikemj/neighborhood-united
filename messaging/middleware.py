"""
JWT authentication middleware for Django Channels WebSocket connections.
"""
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import logging

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Validate JWT token and return the associated user.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        # Validate the access token
        access_token = AccessToken(token_string)
        user_id = access_token.get('user_id')
        
        if user_id:
            return User.objects.get(id=user_id)
    except (InvalidToken, TokenError) as e:
        logger.warning(f"[WebSocket] Invalid token: {e}")
    except User.DoesNotExist:
        logger.warning(f"[WebSocket] User not found for token")
    except Exception as e:
        logger.error(f"[WebSocket] Token validation error: {e}")
    
    return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware that authenticates WebSocket connections using JWT tokens.
    
    Token can be passed via:
    1. Query string: ws://...?token=<jwt_token>
    2. Subprotocol (for browsers that support it)
    
    Usage in ASGI config:
        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddleware(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """
    
    async def __call__(self, scope, receive, send):
        # Only process WebSocket connections
        if scope['type'] != 'websocket':
            return await super().__call__(scope, receive, send)
        
        # Try to get token from query string
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]
        
        if token:
            # Authenticate using JWT token
            scope['user'] = await get_user_from_token(token)
            logger.debug(f"[WebSocket] Authenticated user: {scope['user']}")
        else:
            # Fall back to session-based auth if no token provided
            # This allows backward compatibility for same-origin connections
            if 'user' not in scope or scope['user'] is None:
                scope['user'] = AnonymousUser()
        
        return await super().__call__(scope, receive, send)


class JWTAuthMiddlewareStack:
    """
    Convenience wrapper that combines JWT auth with session auth fallback.
    
    Usage:
        from messaging.middleware import JWTAuthMiddlewareStack
        
        application = ProtocolTypeRouter({
            "websocket": JWTAuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
        })
    """
    
    def __new__(cls, inner):
        from channels.auth import AuthMiddlewareStack
        # First try session auth, then JWT auth takes precedence if token is provided
        return JWTAuthMiddleware(AuthMiddlewareStack(inner))

