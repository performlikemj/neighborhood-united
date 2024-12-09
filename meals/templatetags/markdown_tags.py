# meals/templatetags/markdown_tags.py
from django import template
import re

register = template.Library()

@register.filter(name='bold_asterisks')
def bold_asterisks(value):
    # Replace **text** with <strong>text</strong>
    return re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', value)