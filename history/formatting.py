from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.formats import localize
from django.utils.formats import number_format


def format_field_value(instance, field_name, raw):
    if raw is None or raw == "":
        return ""

    if hasattr(raw, "_meta") and hasattr(raw, "pk"):
        return str(raw)

    field = instance._meta.get_field(field_name)

    if getattr(field, "choices", None):
        for value, label in field.flatchoices:
            if value == raw:
                return str(label)

    if field.is_relation:
        if raw is None:
            return ""
        related_model = field.remote_field.model
        try:
            related = related_model.objects.get(pk=raw)
            return str(related)
        except related_model.DoesNotExist:
            return str(raw)

    if isinstance(raw, bool):
        return "Yes" if raw else "No"

    if isinstance(raw, Decimal):
        if field_name == "price" or getattr(field, "decimal_places", None) == 2:
            return f"${raw:.2f}"
        formatted = number_format(raw, decimal_pos=2, use_l10n=True)
        return str(formatted)

    if hasattr(raw, "isoformat"):
        if timezone.is_aware(raw):
            raw = timezone.localtime(raw)
        elif settings.USE_TZ:
            raw = timezone.make_aware(raw, timezone.get_current_timezone())
            raw = timezone.localtime(raw)
        return localize(raw)

    return str(raw)
