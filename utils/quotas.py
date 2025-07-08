"""
Quota management utilities for limiting API usage.
"""
import datetime
import redis
import pytz
from django.conf import settings
from custom_auth.models import CustomUser
import os
import logging
import ssl

logger = logging.getLogger(__name__)

# Initialize Redis connection with proper SSL handling
def get_redis_connection():
    """Get a properly configured Redis connection with SSL support."""
    redis_url = os.getenv('REDIS_URL', '')
    
    if not redis_url:
        logger.error("REDIS_URL environment variable not set")
        return None
    
    try:
        # Parse the Redis URL and create connection with SSL verification
        return redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30,
            retry_on_error=[redis.exceptions.ReadOnlyError, redis.exceptions.ConnectionError],
            ssl_cert_reqs="required",  # Use string instead of ssl.CERT_REQUIRED for newer redis-py versions
            ssl_check_hostname=False,  # Azure Redis doesn't need hostname verification
        )
    except Exception as e:
        logger.error(f"Failed to create Redis connection: {str(e)}")
        return None

# Initialize Redis connection
r = get_redis_connection()

def _key(user_id: str, model: str) -> str:
    """
    Generate a Redis key for tracking quotas.
    The key includes the date to automatically reset quotas daily.
    """
    # For guests, use a stable ID-based key instead of session-based
    if isinstance(user_id, str) and (user_id.startswith('guest_') or user_id == 'guest'):
        today = datetime.date.today().isoformat()  # server date
        return f"quota:{today}:{user_id}:{model}"  # guest-stable ID
        
    # Use user's local date if it's an authenticated user
    try:
        user = CustomUser.objects.get(id=int(user_id))
        user_timezone = pytz.timezone(user.timezone if user.timezone else 'UTC')
        today = datetime.datetime.now(user_timezone).date().isoformat()
    except (ValueError, CustomUser.DoesNotExist):
        # Fallback to server time if user not found
        today = datetime.date.today().isoformat()
    
    return f"quota:{today}:{user_id}:{model}"

def hit_quota(user_id: str, model: str, limit: int) -> bool:
    """
    Check and increment the quota for a user/model combination.
    
    Returns True if the user has ALREADY exhausted today's limit.
    """
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
                is_guest_user = isinstance(user_id, str) and (user_id.startswith('guest_') or user_id == 'guest')
                
                if not is_guest_user:
                    # Get user's timezone
                    user = CustomUser.objects.get(id=int(user_id))
                    user_timezone = pytz.timezone(user.timezone if user.timezone else 'UTC')
                    
                    # Calculate seconds until midnight in user's timezone
                    now = datetime.datetime.now(user_timezone)
                    midnight = datetime.datetime.combine(
                        now.date() + datetime.timedelta(days=1),
                        datetime.time.min
                    ).replace(tzinfo=user_timezone)
                    
                    seconds_till_midnight = int((midnight - now).total_seconds())
                else:
                    # For guests, use server time
                    seconds_till_midnight = (
                        (datetime.datetime.combine(
                            datetime.date.today() + datetime.timedelta(days=1),
                            datetime.time.min
                        ) - datetime.datetime.now()).seconds
                    )
            except (ValueError, CustomUser.DoesNotExist):
                # Fallback to server time
                seconds_till_midnight = (
                    (datetime.datetime.combine(
                        datetime.date.today() + datetime.timedelta(days=1),
                        datetime.time.min
                    ) - datetime.datetime.now()).seconds
                )
            
            r.expire(k, seconds_till_midnight)
        
        quota_exceeded = n > limit
        if quota_exceeded:
            logger.info(f"QUOTA_EXCEEDED: {user_id} has used {n}/{limit} of {model}")
        
        return quota_exceeded
    
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.error(f"Redis connection error in quota check: {str(e)}")
        # If Redis is down, allow the request (fail open)
        return False
    except Exception as e:
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