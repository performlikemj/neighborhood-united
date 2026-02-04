# chefs/services/sous_chef/filters/__init__.py
"""
Filters for incoming and outgoing message content.

Includes PII detection for restricting health data on certain channels.
"""

from .pii_detector import detect_health_pii, should_ignore_pii_in_message

__all__ = ["detect_health_pii", "should_ignore_pii_in_message"]
