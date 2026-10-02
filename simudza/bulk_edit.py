"""Domain logic for Wagtail admin bulk edits (no HTTP)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from history.context import change_context
from history.models import ChangeLog
from history.services import _read_field, _values_equal


class BulkEditValidationError(ValidationError):
    pass


VERIFICATION_APPLIER_FIELDS = frozenset(
    {"verification_level", "verification_reference"},
)


def _normalize_assign_value(instance, field_name, value):
    if value is None:
        return None
    field = instance._meta.get_field(field_name)
    if field.is_relation and hasattr(value, "pk"):
        return value
    return value


def _compare_raw(instance, field_name, value):
    field = instance._meta.get_field(field_name)
    if field.is_relation and hasattr(value, "pk"):
        new_raw = value.pk
    else:
        new_raw = value
    old_raw = _read_field(instance, field_name)
    return old_raw, new_raw


def _descendant_pks(category_model, root_pk):
    found: set[int] = set()
    queue = list(
        category_model.objects.filter(parent_id=root_pk).values_list("pk", flat=True)
    )
    while queue:
        pk = queue.pop()
        if pk in found:
            continue
        found.add(pk)
        queue.extend(
            category_model.objects.filter(parent_id=pk).values_list("pk", flat=True)
        )
    return found


def validate_category_parent_bulk(objects, parent_value):
    from categories.models import Category

    if parent_value is None:
        return
    parent_pk = parent_value.pk if hasattr(parent_value, "pk") else parent_value
    selected_pks = {obj.pk for obj in objects}
    if parent_pk in selected_pks:
        raise BulkEditValidationError(
            "Parent cannot be one of the selected categories.",
        )
    for obj in objects:
        if parent_pk == obj.pk:
            raise BulkEditValidationError(
                "A category cannot be its own parent.",
            )
        if parent_pk in _descendant_pks(Category, obj.pk):
            raise BulkEditValidationError(
                f"Cannot set parent to a descendant of “{obj}”.",
            )


def _field_diffs_for_object(obj, values, *, applier_field_names):
    from history.formatting import format_field_value

    diffs = []
    for field_name, new_value in values.items():
        if field_name in applier_field_names:
            continue
        old_raw, new_raw = _compare_raw(obj, field_name, new_value)
        if _values_equal(old_raw, new_raw):
            continue
        diffs.append(
            {
                "field_name": field_name,
                "field_label": obj._meta.get_field(field_name).verbose_name,
                "old_display": format_field_value(obj, field_name, old_raw),
                "new_display": format_field_value(obj, field_name, new_raw),
            }
        )
    return diffs


def _verification_diffs_for_object(obj, values):
    from history.formatting import format_field_value

    diffs = []
    if "verification_level" not in values:
        return diffs
    level = values["verification_level"]
    reference = values.get("verification_reference", "")
    old_level = _read_field(obj, "verification_level")
    old_ref = _read_field(obj, "verification_reference")
    if not _values_equal(old_level, level):
        diffs.append(
            {
                "field_name": "verification_level",
                "field_label": obj._meta.get_field("verification_level").verbose_name,
                "old_display": format_field_value(obj, "verification_level", old_level),
                "new_display": format_field_value(obj, "verification_level", level),
            }
        )
    if not _values_equal(old_ref, reference or ""):
        diffs.append(
            {
                "field_name": "verification_reference",
                "field_label": obj._meta.get_field(
                    "verification_reference"
                ).verbose_name,
                "old_display": format_field_value(
                    obj, "verification_reference", old_ref
                ),
                "new_display": format_field_value(
                    obj, "verification_reference", reference or ""
                ),
            }
        )
    return diffs


def preview_bulk_changes(objects, values, *, use_verification_applier=False):
    applier_field_names = VERIFICATION_APPLIER_FIELDS if use_verification_applier else frozenset()
    rows = []
    unchanged = 0
    for obj in objects:
        diffs = list(_field_diffs_for_object(obj, values, applier_field_names=applier_field_names))
        if use_verification_applier and "verification_level" in values:
            diffs.extend(_verification_diffs_for_object(obj, values))
        if diffs:
            rows.append({"object": obj, "diffs": diffs})
        else:
            unchanged += 1
    return rows, unchanged


def apply_bulk_changes(
    objects,
    values,
    *,
    user,
    reason,
    use_verification_applier=False,
    validate_category_parent=False,
):
    if validate_category_parent and "parent" in values:
        validate_category_parent_bulk(objects, values["parent"])

    updated = 0
    unchanged = 0

    with transaction.atomic():
        with change_context(
            user=user,
            source=ChangeLog.Source.BULK_EDIT,
            reason=reason,
        ):
            for obj in objects:
                obj_changed = False

                if use_verification_applier and "verification_level" in values:
                    from businesses.verification_workflow import staff_set_level

                    level = values["verification_level"]
                    reference = values.get("verification_reference", "")
                    old_level = _read_field(obj, "verification_level")
                    old_ref = _read_field(obj, "verification_reference")
                    if not _values_equal(old_level, level) or not _values_equal(
                        old_ref, reference or ""
                    ):
                        staff_set_level(
                            obj,
                            user,
                            level,
                            reference=reference or "",
                        )
                        obj_changed = True

                update_fields = []
                for field_name, new_value in values.items():
                    if field_name in VERIFICATION_APPLIER_FIELDS:
                        continue
                    old_raw, new_raw = _compare_raw(obj, field_name, new_value)
                    if _values_equal(old_raw, new_raw):
                        continue
                    field = obj._meta.get_field(field_name)
                    assign_value = _normalize_assign_value(obj, field_name, new_value)
                    if field.is_relation and hasattr(assign_value, "pk"):
                        setattr(obj, field.name, assign_value)
                    else:
                        setattr(obj, field.attname, new_raw)
                    update_fields.append(field_name)

                if update_fields:
                    obj.save(update_fields=update_fields)
                    obj_changed = True

                if obj_changed:
                    updated += 1
                else:
                    unchanged += 1

    return updated, unchanged


def verification_applier_field_names():
    return VERIFICATION_APPLIER_FIELDS
