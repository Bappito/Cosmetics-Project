from django import template
from django.utils.safestring import mark_safe

from erp.icons import icon as render_icon

register = template.Library()


@register.filter
def icon(name):
    """Use as {{ "box"|icon }} to draw a sidebar or card icon."""
    return mark_safe(render_icon(name))


@register.filter
def sku_only(label):
    """'2101 - שמפו קרטין (בלק)' -> '2101'. Shows a parent product by its SKU alone."""
    return str(label).split(" - ", 1)[0].strip()
