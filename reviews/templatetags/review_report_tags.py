from django import template

from reviews.models import BUSINESS_REPORT_REASONS, PRODUCT_REPORT_REASONS

register = template.Library()


@register.simple_tag
def product_report_reason_choices():
    return PRODUCT_REPORT_REASONS


@register.simple_tag
def business_report_reason_choices():
    return BUSINESS_REPORT_REASONS
