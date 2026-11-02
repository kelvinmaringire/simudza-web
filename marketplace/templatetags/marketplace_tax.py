from django import template

from marketplace.tax import format_tax_rate

register = template.Library()


@register.filter(name="tax_rate")
def tax_rate_filter(value):
    """Format a stored tax rate percent without trailing zeros."""
    return format_tax_rate(value)
