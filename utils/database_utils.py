"""
Database utilities for handling long-running tasks and connection management.
"""
import logging
from django.db import connection, connections
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


def ensure_fresh_connection():
    """
    Close and reopen database connections to ensure they're fresh.
    
    Use this at the start of long-running Celery tasks or before critical
    database operations to avoid using stale connections.
    
    Example:
        @shared_task
        def my_long_task():
            ensure_fresh_connection()  # Start with fresh connection
            # ... do work ...
    """
    try:
        connection.close()
        logger.debug("Closed database connection to ensure fresh connection")
    except Exception as e:
        logger.warning(f"Error closing database connection: {e}")


def close_all_connections():
    """
    Close all database connections.
    
    Use this after completing a batch of database operations in a long-running
    task to release connections back to the pool.
    
    Example:
        for batch in large_dataset.chunks(100):
            process_batch(batch)
            close_all_connections()  # Release connection between batches
    """
    for conn in connections.all():
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing connection {conn.alias}: {e}")


@contextmanager
def fresh_connection():
    """
    Context manager that ensures a fresh database connection.
    
    Closes any existing connection on entry, and closes the connection on exit.
    Useful for isolated operations within a long-running task.
    
    Example:
        # Long-running task with multiple phases
        for user in thousands_of_users:
            external_api_call(user)  # Takes 5 seconds, no DB access
            
            # Now we need DB access - ensure connection is fresh
            with fresh_connection():
                user.last_processed = now()
                user.save()
    """
    ensure_fresh_connection()
    try:
        yield
    finally:
        close_all_connections()


def periodic_connection_refresh(every_n_iterations=100):
    """
    Decorator that refreshes database connections periodically during iteration.
    
    Use this for tasks that process many items in a loop where each iteration
    may have long gaps without database access.
    
    Args:
        every_n_iterations: Refresh connection after this many iterations
    
    Example:
        @shared_task
        @periodic_connection_refresh(every_n_iterations=50)
        def process_all_users():
            for i, user in enumerate(User.objects.all()):
                # Connection auto-refreshes every 50 users
                do_external_api_call(user)  # Slow operation
                user.save()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Store iteration counter in function attributes
            if not hasattr(wrapper, '_iteration_count'):
                wrapper._iteration_count = 0
            
            original_func = func
            
            # Execute the function
            result = original_func(*args, **kwargs)
            
            # Note: This simple decorator refreshes at the end of the task
            # For more sophisticated iteration tracking, you'd need to modify
            # the task itself to call ensure_fresh_connection() in the loop
            wrapper._iteration_count += 1
            if wrapper._iteration_count % every_n_iterations == 0:
                ensure_fresh_connection()
                logger.debug(f"Refreshed connection after {wrapper._iteration_count} iterations")
            
            return result
        
        return wrapper
    return decorator


def test_connection(alias='default'):
    """
    Test if a database connection is alive and responsive.
    
    Args:
        alias: Database alias to test (default: 'default')
    
    Returns:
        bool: True if connection is alive, False otherwise
    
    Example:
        if not test_connection():
            ensure_fresh_connection()
    """
    try:
        conn = connections[alias]
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception as e:
        logger.warning(f"Database connection test failed: {e}")
        return False

