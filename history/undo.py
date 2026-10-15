"""Undo logged field changes by writing the old value back (and logging that as a new change)."""

from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .context import change_context
from .models import ChangeLog
from .registry import is_tracked_model
from .services import _json_raw, _values_equal

# These change only through businesses.verification.workflow, never by direct write.
UNDO_EXCLUDED_FIELDS = frozenset(
    {
        "verification_level",
        "verification_reference",
        "verified_at",
        "verified_by",
        "owner",
        "confirmed_owner",
        "owner_confirmed_at",
    }
)


class UndoError(Exception):
    pass


def _target(entry):
    model = entry.content_type.model_class()
    if model is None or not is_tracked_model(model):
        return None, None
    return model, model._default_manager.filter(pk=entry.object_id).first()


def _python_value(field, raw):
    if raw is None:
        return None
    return field.to_python(raw)


def undo_blocker(entry, obj=None):
    """Why this entry can't be undone right now, or None if it can."""
    if entry.undone_at is not None:
        return "Already undone."
    if entry.action != ChangeLog.Action.UPDATED:
        return "Only field updates can be undone."
    if not entry.raw_captured:
        return "Recorded before undo was available."
    if entry.field_name in UNDO_EXCLUDED_FIELDS:
        return "Change verification and ownership through the verification workflow."
    if obj is None:
        _model, obj = _target(entry)
    if obj is None:
        return "The record no longer exists."
    field = obj._meta.get_field(entry.field_name)
    current = _json_raw(getattr(obj, field.attname))
    if not _values_equal(current, entry.new_raw):
        return "This field has changed since; undo the later change first."
    return None


def batch_entries(entry):
    return list(
        ChangeLog.objects.filter(batch_id=entry.batch_id)
        .select_related("content_type")
        .order_by("pk")
    )


def undo_entries(entries, *, user, reason=""):
    """Restore old values for every entry; all or nothing. Returns the number undone."""
    entries = list(entries)
    if not entries:
        return 0

    grouped = defaultdict(list)
    targets = {}
    for entry in entries:
        key = (entry.content_type_id, entry.object_id)
        if key not in targets:
            targets[key] = _target(entry)[1]
        blocker = undo_blocker(entry, targets[key])
        if blocker:
            raise UndoError(f"{entry.object_repr} — {entry.field_display}: {blocker}")
        grouped[key].append(entry)

    reason = reason or "Undo of change log " + ", ".join(f"#{e.pk}" for e in entries)
    try:
        with transaction.atomic(), change_context(
            user=user, source=ChangeLog.Source.UNDO, reason=reason
        ):
            for key, group in grouped.items():
                obj = targets[key]
                names = []
                for entry in group:
                    field = obj._meta.get_field(entry.field_name)
                    setattr(obj, field.attname, _python_value(field, entry.old_raw))
                    names.append(entry.field_name)
                others = [f.name for f in obj._meta.fields if f.name not in names]
                obj.clean_fields(exclude=others)
                obj.validate_unique()
                obj.save(update_fields=names)
            ChangeLog.objects.filter(pk__in=[e.pk for e in entries]).update(
                undone_at=timezone.now(), undone_by=user
            )
    except ValidationError as exc:
        raise UndoError("; ".join(exc.messages)) from exc
    except IntegrityError as exc:
        raise UndoError("The old value conflicts with another record.") from exc
    return len(entries)
