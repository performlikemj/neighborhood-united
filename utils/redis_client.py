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

logger = logging.getLogger(__name__)

def get_redis_connection():
    """Get a properly configured Redis connection with SSL support for Azure Redis."""
    redis_url = os.getenv('REDIS_URL', '') or os.getenv('CELERY_BROKER_URL', '')
    
    if not redis_url:
        logger.error("No Redis URL found in environment variables (REDIS_URL or CELERY_BROKER_URL)")
        return None
    
    logger.info(f"Attempting Redis connection to: {redis_url.split('@')[0]}@[REDACTED]")
    
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
        logger.info("Redis connection successful to Azure Redis")
        return client
        
    except Exception as e:
        # n8n traceback
        n8n_traceback = {
            'error': str(e),
            'source': 'get_redis_connection',
            'traceback': traceback.format_exc()
        }
        requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
        logger.error(f"Redis connection failed to Azure Redis: {e}")
        
        # Try with modified SSL settings - NEVER fallback to localhost
        try:
            # Change ssl_cert_reqs from 'required' to 'none' for compatibility
            modified_url = redis_url.replace('ssl_cert_reqs=required', 'ssl_cert_reqs=none')
            logger.info(f"Trying modified SSL settings: {modified_url.split('@')[0]}@[REDACTED]")
            
            client = redis.Redis.from_url(
                modified_url,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )
            client.ping()
            logger.warning("Redis connected with modified SSL configuration (ssl_cert_reqs=none)")
            return client
            
        except Exception as fallback_error:
            # n8n traceback
            n8n_traceback = {
                'error': str(fallback_error),
                'source': 'get_redis_connection',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
            logger.error(f"Redis connection failed even with modified SSL: {fallback_error}")
            logger.error("WILL NOT FALLBACK TO LOCALHOST - returning None")
            return None

class RedisClient:
    """
    Shared Redis client with proper SSL support for Azure Redis.
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
                # Try direct connection - URL now contains lowercase ssl_cert_reqs=none
                # that both Celery and redis-py accept
                connection = redis.Redis.from_url(
                    self._redis_url,
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
                connection.ping()
                logger.info("Redis connection successful")
                self._connection = connection
                return self._connection
                
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                
                # Try with modified SSL settings instead of basic fallback
                try:
                    modified_url = self._redis_url.replace('ssl_cert_reqs=required', 'ssl_cert_reqs=none')
                    connection = redis.Redis.from_url(
                        modified_url,
                        decode_responses=True,
                        socket_connect_timeout=10,
                        socket_timeout=10,
                        retry_on_timeout=True
                    )
                    connection.ping()
                    logger.warning("Redis connected with modified SSL configuration")
                    self._connection = connection
                    return self._connection
                    
                except Exception as fallback_error:
                    logger.error(f"Redis fallback connection failed: {fallback_error}")
                    # n8n traceback
                    n8n_traceback = {
                        'error': str(fallback_error),
                        'source': 'get_redis_connection',
                        'traceback': traceback.format_exc()
                    }
                    requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'get_redis_connection',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'get_redis_connection',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'get_redis_connection',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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
            # n8n traceback
            n8n_traceback = {
                'error': str(e),
                'source': 'get_redis_connection',
                'traceback': traceback.format_exc()
            }
            requests.post(os.getenv('N8N_TRACEBACK_URL'), json=n8n_traceback)
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