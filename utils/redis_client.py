"""
Shared Redis client utility for the application.
This provides a consistent Redis interface that bypasses Django's cache system.
"""
import os
import requests
import redis
import logging
import json
import traceback
from typing import Any, Optional, Union
try:
    from django.conf import settings as dj_settings
except Exception:
    dj_settings = None

logger = logging.getLogger(__name__)

def _true(val: str) -> bool:
    return str(val).lower() in ('true', '1', 'yes', 'on')


def get_redis_connection():
    """Get a properly configured Redis connection.
    
    Works with any TLS-enabled Redis provider (Upstash, Azure, etc.) that uses
    properly formatted rediss:// URLs. No special SSL manipulation needed.
    """
    redis_url = os.getenv('REDIS_URL', '') or os.getenv('CELERY_BROKER_URL', '')
    
    if not redis_url:
        logger.error("No Redis URL found in environment variables (REDIS_URL or CELERY_BROKER_URL)")
        return None
    
    # Redact password for logging
    try:
        redacted_url = redis_url.split('@')[0] + '@[REDACTED]' if '@' in redis_url else '[REDACTED]'
    except Exception:
        redacted_url = '[REDACTED]'
    
    logger.info(f"Attempting Redis connection to: {redacted_url}")
    
    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30,
            socket_connect_timeout=10,
            socket_timeout=10,
            retry_on_timeout=True
        )
        
        # Test the connection
        client.ping()
        logger.info("Redis connection successful")
        return client
        
    except Exception as e:
        # Send error to n8n for monitoring
        n8n_url = os.getenv('N8N_TRACEBACK_URL')
        if n8n_url:
            try:
                n8n_traceback = {
                    'error': str(e),
                    'source': 'get_redis_connection',
                    'traceback': traceback.format_exc()
                }
                requests.post(n8n_url, json=n8n_traceback, timeout=5)
            except Exception:
                pass  # Don't let traceback reporting break the main flow
        
        logger.error(f"Redis connection failed: {e}")
        return None

class RedisClient:
    """
    Shared Redis client for TLS-enabled Redis providers (Upstash, Azure, etc.).
    """
    
    def __init__(self):
        self._connection = None
        self._redis_url = os.getenv('REDIS_URL', '') or os.getenv('CELERY_BROKER_URL', '')
    
    def _get_connection(self):
        """Get or create Redis connection."""
        if self._connection is None:
            if not self._redis_url:
                logger.error("REDIS_URL environment variable not set")
                return None
            
            try:
                connection = redis.Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    health_check_interval=30,
                    socket_connect_timeout=10,
                    socket_timeout=10,
                    retry_on_timeout=True
                )
                
                # Test the connection
                connection.ping()
                logger.info("Redis connection successful")
                self._connection = connection
                return self._connection
                
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                
                # Send error to n8n for monitoring
                n8n_url = os.getenv('N8N_TRACEBACK_URL')
                if n8n_url:
                    try:
                        n8n_traceback = {
                            'error': str(e),
                            'source': 'RedisClient._get_connection',
                            'traceback': traceback.format_exc()
                        }
                        requests.post(n8n_url, json=n8n_traceback, timeout=5)
                    except Exception:
                        pass  # Don't let traceback reporting break the main flow
                
                logger.error("No Redis connection available - operations will be skipped")
                return None
        
        return self._connection
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from Redis cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            conn = self._get_connection()
            if conn is None:
                logger.warning(f"Redis connection not available for GET {key} - returning default")
                return default
                
            value = conn.get(key)
            if value is None:
                return default
                
            # Try to deserialize JSON if possible
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Return as string if not JSON
                return value
                
        except Exception as e:
            logger.error(f"Error getting key '{key}' from Redis: {str(e)}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """
        Set value in Redis cache.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Expiration time in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self._get_connection()
            if conn is None:
                logger.warning(f"Redis connection not available for SET {key} - operation skipped")
                return False
            
            # Serialize complex objects as JSON
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            if timeout:
                conn.setex(key, timeout, serialized_value)
            else:
                conn.set(key, serialized_value)
                
            return True
            
        except Exception as e:
            logger.error(f"Error setting key '{key}' in Redis: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete key from Redis cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self._get_connection()
            if conn is None:
                logger.warning(f"Redis connection not available for DELETE {key} - operation skipped")
                return False
                
            conn.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Error deleting key '{key}' from Redis: {str(e)}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            conn = self._get_connection()
            if conn is None:
                logger.warning(f"Redis connection not available for EXISTS {key} - returning False")
                return False
                
            return bool(conn.exists(key))
            
        except Exception as e:
            logger.error(f"Error checking existence of key '{key}' in Redis: {str(e)}")
            return False

# Global instance for application use
redis_client = RedisClient()

# Convenience functions that match Django cache API
def get(key: str, default: Any = None) -> Any:
    """Get value from Redis cache."""
    return redis_client.get(key, default)

def set(key: str, value: Any, timeout: Optional[int] = None) -> bool:
    """Set value in Redis cache."""
    return redis_client.set(key, value, timeout)

def delete(key: str) -> bool:
    """Delete key from Redis cache."""
    return redis_client.delete(key)

def exists(key: str) -> bool:
    """Check if key exists in Redis cache."""
    return redis_client.exists(key) 
