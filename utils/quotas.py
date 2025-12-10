"""
Quota management utilities for limiting API usage.
"""
import datetime
from django.utils import timezone
import redis
import pytz
from zoneinfo import ZoneInfo
from django.conf import settings
from custom_auth.models import CustomUser
import os
import logging
import traceback
import requests

logger = logging.getLogger(__name__)

def get_redis_connection():
    """Get a properly configured Redis connection with SSL support for Azure Redis."""
    redis_url = os.getenv('REDIS_URL', '') or os.getenv('CELERY_BROKER_URL', '')
    
    if not redis_url:
        logger.error("No Redis URL found in environment variables")
        return None
    
    try:
        # Try direct connection - URL now contains lowercase ssl_cert_reqs=none
        # that both Celery and redis-py accept
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30,
            retry_on_error=[redis.exceptions.ReadOnlyError, redis.exceptions.ConnectionError],
            socket_connect_timeout=10,
            socket_timeout=10,
            retry_on_timeout=True
        )
        
        # Test the connection
        client.ping()
        logger.info("Redis connection successful")
        return client
        
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        
        # Fallback: try basic connection without SSL options
        try:
            client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            client.ping()
            logger.warning("Redis connected with basic configuration (fallback)")
            return client
            
        except Exception as fallback_error:
            logger.error(f"Redis fallback connection failed: {fallback_error}")
            return None

# Lazy-load Redis connection to avoid import-time connection attempts
_redis_connection = None

def _get_redis():
    """Get or create the Redis connection lazily."""
    global _redis_connection
    if _redis_connection is None:
        _redis_connection = get_redis_connection()
    return _redis_connection

def _key(user_id: str, model: str) -> str:
    """
    Generate a Redis key for tracking quotas.
    The key includes the date to automatically reset quotas daily.
    """
    # For guests, use a stable ID-based key instead of session-based
    if isinstance(user_id, str) and (user_id.startswith('guest_') or user_id.startswith('guest:') or user_id == 'guest'):
        today = datetime.date.today().isoformat()  # server date
        return f"quota:{today}:{user_id}:{model}"  # guest-stable ID
        
    # Use user's local date if it's an authenticated user
    try:
        user = CustomUser.objects.get(id=int(user_id))
        user_timezone = ZoneInfo(user.timezone if user.timezone else 'UTC')
        from django.utils import timezone
        today = timezone.now().astimezone(user_timezone).date().isoformat()
    except (ValueError, CustomUser.DoesNotExist):
        # Fallback to server time if user not found
        today = datetime.date.today().isoformat()
    
    return f"quota:{today}:{user_id}:{model}"

def hit_quota(user_id: str, model: str, limit: int) -> bool:
    """
    Check and increment the quota for a user/model combination.
    
    Returns True if the user has ALREADY exhausted today's limit.
    """
    r = _get_redis()
    if not r:
        logger.warning("Redis connection not available, allowing request")
        return False
    
    k = _key(user_id, model)
    
    try:
        # Atomic increment - thread-safe and efficient
        n = r.incr(k)
        
        if n == 1:  # First hit today, set expiration to midnight in user's timezone
            try:
                # Consistent guest check: if it's a string AND starts with guest_ OR is 'guest'
                is_guest_user = isinstance(user_id, str) and (
                    user_id.startswith('guest_') or user_id.startswith('guest:') or user_id == 'guest'
                )
                
                if not is_guest_user:
                    # Get user's timezone
                    user = CustomUser.objects.get(id=int(user_id))
                    user_timezone = ZoneInfo(user.timezone if user.timezone else 'UTC')
                    
                    # Calculate seconds until midnight in user's timezone
                    now = timezone.now().astimezone(user_timezone)
                    midnight = datetime.datetime.combine(
                        now.date() + datetime.timedelta(days=1),
                        datetime.time.min
                    ).replace(tzinfo=user_timezone)
                    
                    seconds_till_midnight = int((midnight - now).total_seconds())
                else:
                    # For guests, use server time (timezone-aware)
                    # Compute seconds until next midnight in the server's current timezone
                    server_tz = timezone.get_current_timezone()
                    now_server = timezone.now().astimezone(server_tz)
                    midnight_server = (now_server + datetime.timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    seconds_till_midnight = int((midnight_server - now_server).total_seconds())
            except (ValueError, CustomUser.DoesNotExist):
                # Fallback to server time (timezone-aware)
                server_tz = timezone.get_current_timezone()
                now_server = timezone.now().astimezone(server_tz)
                midnight_server = (now_server + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                seconds_till_midnight = int((midnight_server - now_server).total_seconds())
            
            r.expire(k, seconds_till_midnight)
        
        quota_exceeded = n > limit
        if quota_exceeded:
            logger.info(f"QUOTA_EXCEEDED: {user_id} has used {n}/{limit} of {model}")
        
        return quota_exceeded
    
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.error(f"Redis connection error in quota check: {str(e)}")
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"hit_quota", "traceback": traceback.format_exc()})
        # If Redis is down, allow the request (fail open)
        return False
    except Exception as e:
        # n8n traceback
        n8n_traceback_url = os.getenv("N8N_TRACEBACK_URL")
        requests.post(n8n_traceback_url, json={"error": str(e), "source":"hit_quota", "traceback": traceback.format_exc()})
        logger.error(f"Unexpected error in quota check for user {user_id}, model {model}: {str(e)}")
        # For unexpected errors, also fail open
        return False

def hit_quota_request(request, model_complexity="medium", tokens_used=None, guest_id=None, is_chat=True):
    """Track quota usage for a user and determine if they've exceeded their limit."""
    user = request.user
    session_key = request.session.session_key
    
    # Get guest ID from request or use provided one
    request_guest_id = guest_id or request.session.get('guest_id')
    
    
    is_guest = not user.is_authenticated
    
    user_id = None
    if user.is_authenticated:
        user_id = str(user.id)
    elif is_guest and request_guest_id:
        # Use guest ID from session or parameter
        user_id = f"guest:{request_guest_id}"
    elif is_guest and session_key:
        # Fallback to session key if no guest ID is found
        user_id = f"guest:{session_key}"
    else:
        # Last resort, create a temporary ID
        user_id = "guest:unknown"
    
    # Determine model and limit based on complexity and user type
    if model_complexity == "high":
        model = "gpt4"
        limit = settings.GPT41_AUTH_LIMIT if user.is_authenticated else 0  # Guests can't use high complexity
    else:  # medium or low
        if is_guest:
            model = "gpt4_mini_guest"
            limit = settings.GPT41_MINI_GUEST_LIMIT
        else:
            model = "gpt4"  # Authenticated users get the better model regardless
            limit = settings.GPT41_AUTH_LIMIT
    
    # Check if quota is exceeded
    return hit_quota(user_id, model, limit) 
