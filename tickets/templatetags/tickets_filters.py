# tickets/templatetags/tickets_filters.py

from django import template

register = template.Library()

@register.filter(name='underscore_to_space')
def underscore_to_space(value):
    """
    Replaces all underscores in a string with spaces.
    Usage: {{ value|underscore_to_space }}
    """
    if not isinstance(value, str):
        return value
    return value.replace('_', ' ')
