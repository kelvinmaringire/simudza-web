"""Recover raw values for change log rows recorded before raw values were stored."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from .formatting import format_field_value
from .models import ChangeLog
from .services import _json_raw

_NO_MATCH = object()


def _reverse_display(obj, field, display):
    """Raw value whose formatted display is ``display``, or _NO_MATCH."""
    if display == "":
        candidates = [None, ""]
    elif field.is_relation:
        model = field.remote_field.model
        candidates = [r.pk for r in model._default_manager.all() if str(r) == display]
        if len(candidates) != 1:
            return _NO_MATCH
    elif getattr(field, "choices", None):
        candidates = [v for v, label in field.flatchoices if str(label) == display]
    elif display in ("Yes", "No"):
        candidates = [display == "Yes"]
    else:
        candidates = [display]
        try:
            candidates.append(Decimal(display.lstrip("$").replace(",", "")))
        except InvalidOperation:
            pass

    for candidate in candidates:
        try:
            value = None if candidate is None else field.to_python(candidate)
        except ValidationError:
            continue
        if value in ("", None) and not field.null and candidate is None:
            continue
        if format_field_value(obj, field.name, value) == display:
            return _json_raw(value)
    return _NO_MATCH


def backfill_raw_values():
    """Fill old_raw/new_raw on legacy updates whose text round-trips exactly. Returns count."""
    filled = 0
    legacy = ChangeLog.objects.filter(
        raw_captured=False, action=ChangeLog.Action.UPDATED
    ).exclude(field_name="").select_related("content_type")
    for entry in legacy:
        model = entry.content_type.model_class()
        obj = model and model._default_manager.filter(pk=entry.object_id).first()
        if obj is None:
            continue
        try:
            field = obj._meta.get_field(entry.field_name)
        except Exception:
            continue
        old_raw = _reverse_display(obj, field, entry.old_value)
        new_raw = _reverse_display(obj, field, entry.new_value)
        if old_raw is _NO_MATCH or new_raw is _NO_MATCH:
            continue
        entry.old_raw, entry.new_raw, entry.raw_captured = old_raw, new_raw, True
        entry.save(update_fields=["old_raw", "new_raw", "raw_captured"])
        filled += 1
    return filled
