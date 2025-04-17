import json
from django import template

register = template.Library()

@register.filter
def json_parse(value):
    """Parse a JSON string into a Python object."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None
