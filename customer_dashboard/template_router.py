"""
Template router for assistant-driven emails.

Purpose: Map a caller-provided `template_key` to intent-specific partials that
wrap or replace the three body sections: body_main, body_data, body_final.

Design:
- Callers may pass `template_key` and optional `extra_context`.
- If a specific section template exists for the key, render it; otherwise fall back
  to generic section templates.
- Section templates receive `content_html` (the raw HTML produced upstream) and
  any additional context provided by the caller.

This module keeps the base email shell (`customer_dashboard/assistant_email_template.html`)
unchanged while allowing consistent, intent-specific content rendering.
"""

from typing import Dict, Tuple, Optional, List, Type
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from pydantic import BaseModel, ValidationError

from .email_schemas import (
    EmailBody,
    EmailMealPlanApproval,
    EmailShoppingList,
    EmailDailyPrep,
    EmailBulkPrep,
    EmailEmergencySupply,
    EmailSystemUpdate,
    EmailPaymentConfirmation,
    EmailRefundNotification,
    EmailOrderCancellation,
)


# Mapping from template_key -> per-section template paths
# Only include overrides you actually have; router will fallback to generic.
TEMPLATE_MAP: Dict[str, Dict[str, str]] = {
    # Example mappings (add concrete partials over time):
    'meal_plan_approval': {
        'main': 'emails/sections/meal_plan_approval_main.html',
        'data': 'emails/sections/meal_plan_approval_data.html',
        'final': 'emails/sections/meal_plan_approval_final.html',
    },
    'bulk_prep_instructions': {
        'main': 'emails/sections/bulk_prep_instructions_main.html',
        'data': 'emails/sections/bulk_prep_instructions_data.html',
        'final': 'emails/sections/bulk_prep_instructions_final.html',
    },
    'daily_prep_instructions': {
        'main': 'emails/sections/daily_prep_instructions_main.html',
        'data': 'emails/sections/daily_prep_instructions_data.html',
        'final': 'emails/sections/daily_prep_instructions_final.html',
    },
    'shopping_list': {
        'main': 'emails/sections/shopping_list_main.html',
        'data': 'emails/sections/shopping_list_data.html',
        'final': 'emails/sections/shopping_list_final.html',
    },
    'emergency_supply': {
        'main': 'emails/sections/emergency_supply_main.html',
        'data': 'emails/sections/emergency_supply_data.html',
        'final': 'emails/sections/emergency_supply_final.html',
    },
    'system_update': {
        'main': 'emails/sections/system_update_main.html',
        'data': 'emails/sections/system_update_data.html',
        'final': 'emails/sections/system_update_final.html',
    },
    'payment_confirmation': {
        'main': 'emails/sections/payment_confirmation_main.html',
        'data': 'emails/sections/payment_confirmation_data.html',
        'final': 'emails/sections/payment_confirmation_final.html',
    },
    'refund_notification': {
        'main': 'emails/sections/refund_notification_main.html',
        'data': 'emails/sections/refund_notification_data.html',
        'final': 'emails/sections/refund_notification_final.html',
    },
    'order_cancellation': {
        'main': 'emails/sections/order_cancellation_main.html',
        'data': 'emails/sections/order_cancellation_data.html',
        'final': 'emails/sections/order_cancellation_final.html',
    },
}
SCHEMA_MAP: Dict[str, Type[BaseModel]] = {
    'meal_plan_approval': EmailMealPlanApproval,
    'daily_prep_instructions': EmailDailyPrep,
    'bulk_prep_instructions': EmailBulkPrep,
    'shopping_list': EmailShoppingList,
    'emergency_supply': EmailEmergencySupply,
    'system_update': EmailSystemUpdate,
    'payment_confirmation': EmailPaymentConfirmation,
    'refund_notification': EmailRefundNotification,
    'order_cancellation': EmailOrderCancellation,
}

def get_schema_for_key(template_key: Optional[str]) -> Type[BaseModel]:
    """Return the Pydantic schema for a template key, defaulting to EmailBody."""
    if template_key and template_key in SCHEMA_MAP:
        return SCHEMA_MAP[template_key]
    return EmailBody

def parse_structured_email(template_key: Optional[str], payload: dict) -> BaseModel:
    """Parse a structured email payload using the schema for the key."""
    schema = get_schema_for_key(template_key)
    try:
        return schema(**payload)
    except ValidationError:
        # Fallback to generic schema with minimal mapping
        return EmailBody(
            main_text=str(payload.get('main_text') or ''),
            final_text=str(payload.get('final_text') or ''),
            css_classes=payload.get('css_classes') or None,
        )



# Generic fallbacks for each section
GENERIC_SECTION_TEMPLATES: Dict[str, str] = {
    'main': 'emails/sections/generic_main.html',
    'data': 'emails/sections/generic_data.html',
    'final': 'emails/sections/generic_final.html',
}


def render_email_sections(
    template_key: Optional[str],
    section_html: Dict[str, str],
    extra_context: Optional[Dict] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Render email body sections using a `template_key` mapping when provided,
    otherwise fall back to generic wrappers. Returns a tuple of:
      - rendered_sections: dict with keys 'main', 'data', 'final'
      - css_classes: list of css class names to append on the base template

    section_html should contain raw HTML strings for keys: 'main', 'data', 'final'.
    """
    rendered: Dict[str, str] = {}
    css_classes: List[str] = []

    key_map = TEMPLATE_MAP.get(template_key or '', {}) if template_key else {}

    # Add a stable CSS class for template scoping when a key is used
    if template_key:
        css_classes.append(f"intent-{template_key}")

    context_base = extra_context.copy() if isinstance(extra_context, dict) else {}

    for section in ('main', 'data', 'final'):
        content_html = section_html.get(section, '') or ''
        template_path = key_map.get(section) or GENERIC_SECTION_TEMPLATES[section]

        # Build rendering context
        ctx = {
            'content_html': content_html,
            **context_base,
        }

        try:
            rendered[section] = render_to_string(template_path, ctx)
        except TemplateDoesNotExist:
            fallback_path = GENERIC_SECTION_TEMPLATES[section]
            rendered[section] = render_to_string(fallback_path, ctx)

    return rendered, css_classes


