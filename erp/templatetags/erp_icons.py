from django import template
from django.utils.safestring import mark_safe

from erp.icons import icon as render_icon

register = template.Library()


@register.filter
def icon(name):
    """Use as {{ "box"|icon }} to draw a sidebar or card icon."""
    return mark_safe(render_icon(name))
