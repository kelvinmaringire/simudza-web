from django.db.models.signals import post_delete, post_save, pre_save

from .registry import is_tracked_model, tracked_field_names
from .services import log_instance_changes, log_instance_deleted

SNAPSHOT_ATTR = "_history_old_values"


def _snapshot_instance(instance):
    if instance.pk is None:
        return {}
    model = instance.__class__
    names = tracked_field_names(model)
    if not names:
        return {}
    attnames = [_attname(model, name) for name in names]
    row = (
        model._default_manager.filter(pk=instance.pk).values(*attnames).first()
    )
    if not row:
        return {}
    return {
        field_name: row[_attname(model, field_name)]
        for field_name in names
    }


def _attname(model, field_name):
    return model._meta.get_field(field_name).attname


def capture_old_values(sender, instance, **kwargs):
    if not is_tracked_model(sender):
        return
    setattr(instance, SNAPSHOT_ATTR, _snapshot_instance(instance))


def log_changes(sender, instance, created, update_fields=None, **kwargs):
    if not is_tracked_model(sender):
        return

    old_values = getattr(instance, SNAPSHOT_ATTR, None)
    fields_filter = None
    if update_fields is not None and not created:
        fields_filter = set(update_fields)

    log_instance_changes(
        instance,
        old_values=old_values if old_values is not None else {},
        created=created,
        fields_filter=fields_filter,
    )


def log_deletion(sender, instance, **kwargs):
    if not is_tracked_model(sender):
        return
    log_instance_deleted(instance)


def connect_signals():
    from .registry import tracked_models

    for model in tracked_models():
        pre_save.connect(capture_old_values, sender=model, weak=False)
        post_save.connect(log_changes, sender=model, weak=False)
        post_delete.connect(log_deletion, sender=model, weak=False)


connect_signals()
