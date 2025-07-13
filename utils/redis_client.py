"""
Shared Redis client utility for the application.
This provides a consistent Redis interface that bypasses Django's cache system.
"""
import os
import redis
import ssl
import logging
import json
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

class RedisClient:
    """
    Shared Redis client with proper SSL support for Azure Redis.
    """
    
    def __init__(self):
        self._connection = None
        self._redis_url = os.getenv('REDIS_URL', '')
    
    def _get_connection(self):
        """Get or create Redis connection."""
        if self._connection is None:
            if not self._redis_url:
                logger.error("REDIS_URL environment variable not set")
                return None
            
            try:
                # Use ssl_cert_reqs instead of ssl_check_hostname for compatibility with older Celery/Kombu
                self._connection = redis.Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30,
                    retry_on_error=[redis.exceptions.ReadOnlyError, redis.exceptions.ConnectionError],
                    ssl_cert_reqs=ssl.CERT_NONE,  # Skip SSL certificate verification (compatible with older packages)
                )
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.error(f"Failed to create Redis connection: {str(e)}")
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
                logger.warning("Redis connection not available")
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
                logger.warning("Redis connection not available")
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
                logger.warning("Redis connection not available")
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