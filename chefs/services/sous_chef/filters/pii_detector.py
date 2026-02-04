# chefs/services/sous_chef/filters/pii_detector.py
"""
PII detector for incoming messages on restricted channels.

When users share health data despite instructions not to, this detector
identifies it so we can ignore the PII rather than process it.
"""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns that indicate health/dietary PII
HEALTH_PII_PATTERNS = [
    # Allergy mentions - various phrasings
    (r'\b(allergic|allergy|allergies)\b', 'allergy'),
    (r'\b\w+\s+allergy\b', 'allergy'),  # "nut allergy", "peanut allergy"
    # Intolerance mentions
    (r'\b(intoleran(?:t|ce)|intolerant)\b', 'intolerance'),
    (r'\blactose\s+intolerant\b', 'intolerance'),
    # Dietary restrictions with specifics
    (r"\b(can'?t|cannot|doesn'?t|don'?t)\s+eat\s+\w+", 'restriction'),
    # Specific conditions
    (r'\b(celiac|crohn|ibs|diabetic|diabetes)\b', 'medical_condition'),
    # Common allergens being listed as allergens
    (r'\b(peanut|tree\s*nut|shellfish|egg|wheat|soy|fish|sesame)\s*(allergy|allergic|intolerant)?\b', 'allergen_mention'),
]

# General dietary preferences (less sensitive, but still shouldn't be solicited)
DIETARY_PREFERENCE_PATTERNS = [
    (r'\b(vegan|vegetarian|pescatarian|kosher|halal|keto|paleo)\b', 'dietary_preference'),
    (r'\b(gluten|dairy|nut|soy|egg)[- ]?free\b', 'free_from'),
]


def detect_health_pii(message: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if a message contains health-related PII.

    Args:
        message: The incoming message text

    Returns:
        Tuple of (contains_pii: bool, pii_type: Optional[str])
    """
    message_lower = message.lower()

    # Check high-sensitivity patterns first
    for pattern, pii_type in HEALTH_PII_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            logger.info(f"Detected health PII type '{pii_type}' in incoming message")
            return True, pii_type

    # Check dietary preference patterns
    for pattern, pii_type in DIETARY_PREFERENCE_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            logger.info(f"Detected dietary PII type '{pii_type}' in incoming message")
            return True, pii_type

    return False, None


def should_ignore_pii_in_message(message: str, channel: str) -> bool:
    """
    Determine if PII in this message should be ignored.

    On restricted channels (telegram, line), if a user shares health PII,
    we should not process it for the request.

    Args:
        message: The incoming message text
        channel: The channel (telegram, line, web, etc.)

    Returns:
        True if the message contains PII that should be ignored
    """
    from chefs.services.sous_chef.tools.categories import SENSITIVE_RESTRICTED_CHANNELS

    if channel not in SENSITIVE_RESTRICTED_CHANNELS:
        return False

    contains_pii, pii_type = detect_health_pii(message)

    if contains_pii:
        logger.warning(
            f"User shared health PII (type: {pii_type}) on restricted channel "
            f"'{channel}'. PII will not be processed for this request."
        )

    return contains_pii
