"""
Centralized error reporting utility.

Currently uses Python logging. Designed for easy Sentry integration.

TODO: Integrate Sentry for production error tracking
- pip install sentry-sdk
- Add SENTRY_DSN to environment variables
- Initialize in settings.py or wsgi.py

Example Sentry setup (add to settings.py when ready):

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    SENTRY_DSN = os.getenv('SENTRY_DSN', '')
    if SENTRY_DSN:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
"""
import logging
import traceback as tb
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def report_error(
    error: Exception,
    source: str,
    extra_context: Optional[Dict[str, Any]] = None,
    include_traceback: bool = True
) -> None:
    """
    Report an error to the error tracking system.
    
    Currently logs to Python logger. When Sentry is integrated,
    this will also send to Sentry with full context.
    
    Args:
        error: The exception that occurred
        source: Identifier for where the error originated (e.g., 'meal_generation', 'payment_processing')
        extra_context: Additional context (user_id, request data, etc.)
        include_traceback: Whether to include full traceback in logs
    
    Example:
        try:
            do_something()
        except Exception as e:
            report_error(e, 'my_function', {'user_id': user.id, 'action': 'create'})
    """
    context_str = f" | Context: {extra_context}" if extra_context else ""
    
    if include_traceback:
        logger.exception(f"[{source}] {error}{context_str}")
    else:
        logger.error(f"[{source}] {error}{context_str}")
    
    # TODO: Add Sentry integration when SENTRY_DSN is configured
    # from django.conf import settings
    # if getattr(settings, 'SENTRY_DSN', ''):
    #     import sentry_sdk
    #     with sentry_sdk.push_scope() as scope:
    #         scope.set_tag("source", source)
    #         if extra_context:
    #             for key, value in extra_context.items():
    #                 scope.set_extra(key, str(value))
    #         sentry_sdk.capture_exception(error)


def report_warning(
    message: str,
    source: str,
    extra_context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Report a warning (non-exception) to the tracking system.
    
    Args:
        message: Warning message
        source: Identifier for where the warning originated
        extra_context: Additional context
    """
    context_str = f" | Context: {extra_context}" if extra_context else ""
    logger.warning(f"[{source}] {message}{context_str}")
    
    # TODO: Add Sentry integration
    # from django.conf import settings
    # if getattr(settings, 'SENTRY_DSN', ''):
    #     import sentry_sdk
    #     sentry_sdk.capture_message(f"[{source}] {message}", level="warning")

