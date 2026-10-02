import uuid

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .context import current_context
from .formatting import format_field_value
from .models import ChangeLog
from .registry import is_tracked_model, tracked_field_names


def _attname(model, field_name):
    try:
        return model._meta.get_field(field_name).attname
    except Exception:
        return field_name


def _read_field(instance, field_name):
    field = instance._meta.get_field(field_name)
    return getattr(instance, field.attname)


def _values_equal(old, new):
    if old is None and new in ("", None):
        return True
    if new is None and old in ("", None):
        return True
    return old == new


def _actor_from_context(ctx):
    user = ctx.user
    if user is not None and getattr(user, "is_authenticated", False):
        return user, user.get_username()
    return None, ""


def _source_from_context(ctx):
    if ctx.source:
        return ctx.source
    return ChangeLog.Source.WEB


def changes_for(obj, *, limit=20):
    qs = ChangeLog.objects.for_object(obj)
    if limit is not None:
        qs = qs[:limit]
    return list(qs)


def _build_entries(
    instance,
    *,
    action,
    diffs,
    batch_id,
    user,
    username,
    source,
    reason,
):
    if not diffs:
        return []
    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    object_id = str(instance.pk)
    object_repr = str(instance)[:300]
    entries = []
    for field_name, old_raw, new_raw in diffs:
        field = instance._meta.get_field(field_name)
        old_display = format_field_value(instance, field_name, old_raw)
        new_display = format_field_value(instance, field_name, new_raw)
        if action == ChangeLog.Action.UPDATED and old_display == new_display:
            continue
        entries.append(
            ChangeLog(
                content_type=ct,
                object_id=object_id,
                object_repr=object_repr,
                action=action,
                field_name=field_name,
                field_label=str(field.verbose_name),
                old_value=old_display if action != ChangeLog.Action.CREATED else "",
                new_value=new_display if action != ChangeLog.Action.DELETED else "",
                changed_by=user,
                changed_by_repr=username,
                reason=reason or "",
                source=source,
                batch_id=batch_id,
            )
        )
    return entries


def log_instance_changes(
    instance,
    *,
    old_values,
    created=False,
    fields_filter=None,
):
    if not is_tracked_model(instance.__class__):
        return

    tracked = tracked_field_names(instance.__class__)
    if fields_filter is not None:
        tracked = tuple(f for f in tracked if f in fields_filter)

    diffs = []
    for field_name in tracked:
        new_raw = _read_field(instance, field_name)
        old_raw = old_values.get(field_name) if old_values else None
        if created:
            if _values_equal(None, new_raw):
                continue
            diffs.append((field_name, None, new_raw))
        else:
            if _values_equal(old_raw, new_raw):
                continue
            diffs.append((field_name, old_raw, new_raw))

    if not diffs and not created:
        return

    ctx = current_context()
    user, username = _actor_from_context(ctx)
    source = _source_from_context(ctx)
    reason = ctx.reason or ""
    batch_id = uuid.uuid4()
    action = ChangeLog.Action.CREATED if created else ChangeLog.Action.UPDATED

    entries = _build_entries(
        instance,
        action=action,
        diffs=diffs,
        batch_id=batch_id,
        user=user,
        username=username,
        source=source,
        reason=reason,
    )
    if not entries:
        return

    def write():
        ChangeLog.objects.bulk_create(entries)

    transaction.on_commit(write)


def log_instance_deleted(instance):
    if not is_tracked_model(instance.__class__):
        return
    if instance.pk is None:
        return

    ctx = current_context()
    user, username = _actor_from_context(ctx)
    source = _source_from_context(ctx)
    reason = ctx.reason or ""
    ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)

    entry = ChangeLog(
        content_type=ct,
        object_id=str(instance.pk),
        object_repr=str(instance)[:300],
        action=ChangeLog.Action.DELETED,
        changed_by=user,
        changed_by_repr=username,
        reason=reason,
        source=source,
        batch_id=uuid.uuid4(),
    )

    transaction.on_commit(lambda: ChangeLog.objects.bulk_create([entry]))


def update_with_history(queryset, **values):
    """Log field updates then run queryset.update (signals do not fire)."""
    if not values:
        return 0

    model = queryset.model
    if not is_tracked_model(model):
        return queryset.update(**values)

    tracked = set(tracked_field_names(model))
    update_fields = [name for name in values if name in tracked]
    if not update_fields:
        return queryset.update(**values)

    ctx = current_context()
    user, username = _actor_from_context(ctx)
    source = _source_from_context(ctx)
    reason = ctx.reason or ""
    batch_id = uuid.uuid4()
    ct = ContentType.objects.get_for_model(model, for_concrete_model=False)

    entries = []
    for obj in queryset.iterator():
        diffs = []
        for field_name in update_fields:
            old_raw = _read_field(obj, field_name)
            new_raw = values[field_name]
            if _values_equal(old_raw, new_raw):
                continue
            diffs.append((field_name, old_raw, new_raw))
        if not diffs:
            continue
        entries.extend(
            _build_entries(
                obj,
                action=ChangeLog.Action.UPDATED,
                diffs=diffs,
                batch_id=batch_id,
                user=user,
                username=username,
                source=source,
                reason=reason,
            )
        )

    count = queryset.update(**values)

    if entries:

        def write():
            ChangeLog.objects.bulk_create(entries)

        transaction.on_commit(write)

    return count
