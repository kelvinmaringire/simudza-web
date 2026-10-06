"""
Wagtail ModelViewSet mixin: bulk edit via Wagtail bulk-action framework.
"""

from __future__ import annotations

from dataclasses import dataclass

from django import forms
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.functional import cached_property, classproperty
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from wagtail.admin.admin_url_finder import AdminURLFinder
from wagtail.admin.forms.models import formfield_for_dbfield
from wagtail.admin.ui.tables import BulkActionsCheckboxColumn
from wagtail.admin.views.bulk_action import BulkAction
from wagtail.admin.views.generic.models import IndexView
from wagtail.permissions import ModelPermissionPolicy

from simudza.utils.bulk_edit import (
    BulkEditValidationError,
    apply_bulk_changes,
    preview_bulk_changes,
)


@dataclass
class BulkEditField:
    name: str
    label: str = ""
    applier: str | None = None
    companions: tuple[str, ...] = ()


def _build_bulk_edit_form(model, bulk_fields: list[BulkEditField]):
    companion_names: set[str] = set()
    for spec in bulk_fields:
        companion_names.update(spec.companions)

    declared: dict[str, forms.Field] = {
        "change_reason": forms.CharField(
            label=_("Reason for change"),
            max_length=500,
            required=True,
            widget=forms.Textarea(attrs={"rows": 2}),
            help_text=_("Stored in change history for this bulk edit."),
        ),
    }

    field_specs_by_name = {spec.name: spec for spec in bulk_fields}

    for spec in bulk_fields:
        change_name = f"change_{spec.name}"
        label = spec.label or capfirst(
            model._meta.get_field(spec.name).verbose_name
        )
        declared[change_name] = forms.BooleanField(
            label=_("Change %(field)s") % {"field": label},
            required=False,
        )
        db_field = model._meta.get_field(spec.name)
        form_field = formfield_for_dbfield(db_field)
        form_field.required = False
        declared[spec.name] = form_field

        for companion in spec.companions:
            if companion in declared:
                continue
            companion_field = model._meta.get_field(companion)
            companion_form_field = formfield_for_dbfield(companion_field)
            companion_form_field.required = False
            declared[companion] = companion_form_field

    class BulkEditForm(forms.Form):
        pass

    for name, form_field in declared.items():
        BulkEditForm.base_fields[name] = form_field

    BulkEditForm._bulk_field_specs = field_specs_by_name
    BulkEditForm._companion_names = companion_names
    return BulkEditForm


def _values_from_form(form, bulk_fields: list[BulkEditField]):
    values = {}
    use_verification = False
    for spec in bulk_fields:
        if not form.cleaned_data.get(f"change_{spec.name}"):
            continue
        values[spec.name] = form.cleaned_data[spec.name]
        if spec.applier == "verification":
            use_verification = True
        for companion in spec.companions:
            if companion not in values:
                values[companion] = form.cleaned_data.get(companion)
    return values, use_verification


def make_bulk_edit_action(
    model,
    bulk_fields: list[BulkEditField],
    *,
    validate_category_parent: bool = False,
):
    bulk_edit_form_class = _build_bulk_edit_form(model, bulk_fields)
    permission_policy = ModelPermissionPolicy(model)

    class ModelBulkEditAction(BulkAction):
        display_name = _("Bulk edit")
        action_type = "bulk_edit"
        aria_label = _("Bulk edit selected items")
        template_name = "admin_bulk_edit/form.html"
        action_priority = 10
        form_class = bulk_edit_form_class

        @classproperty
        def models(cls):
            return [model]

        def check_perm(self, obj):
            return permission_policy.user_has_permission_for_instance(
                self.request.user,
                "change",
                obj,
            )

        def get_all_objects_in_listing_query(self, parent_id):
            return self.model._default_manager.order_by("pk").values_list(
                "pk", flat=True
            )

        def object_context(self, obj):
            return {
                "item": obj,
                "edit_url": AdminURLFinder(self.request.user).get_edit_url(obj),
            }

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["header_icon"] = "edit"
            context["action_button_text"] = _("Continue to preview")
            context["no_action_button_text"] = _("Cancel")
            return context

        @classmethod
        def execute_action(cls, objects, **kwargs):
            action = kwargs["self"]
            values = kwargs["values"]
            use_verification = kwargs["use_verification"]
            reason = kwargs["reason"]
            updated, unchanged = apply_bulk_changes(
                objects,
                values,
                user=action.request.user,
                reason=reason,
                use_verification_applier=use_verification,
                validate_category_parent=validate_category_parent,
            )
            return updated, unchanged

        def get_success_message(self, num_updated, num_unchanged):
            parts = []
            if num_updated:
                parts.append(
                    ngettext(
                        "%(count)d item updated.",
                        "%(count)d items updated.",
                        num_updated,
                    )
                    % {"count": num_updated}
                )
            if num_unchanged:
                parts.append(
                    ngettext(
                        "%(count)d item already had the chosen values.",
                        "%(count)d items already had the chosen values.",
                        num_unchanged,
                    )
                    % {"count": num_unchanged}
                )
            return " ".join(parts) if parts else None

        def form_valid(self, form):
            request = self.request
            objects, _items_without_access = self.get_actionable_objects()
            values, use_verification = _values_from_form(form, bulk_fields)
            reason = form.cleaned_data["change_reason"]

            if not values:
                form.add_error(None, _("Select at least one field to change."))
                return self.form_invalid(form)

            if request.POST.get("confirm") != "1":
                try:
                    change_rows, unchanged_count = preview_bulk_changes(
                        objects,
                        values,
                        use_verification_applier=use_verification,
                    )
                except BulkEditValidationError as exc:
                    form.add_error(None, exc.messages[0])
                    return self.form_invalid(form)

                preview_limit = 100
                context = self.get_context_data(form=form)
                context.update(
                    {
                        "change_rows": change_rows[:preview_limit],
                        "change_rows_truncated": len(change_rows) > preview_limit,
                        "total_selected": len(objects),
                        "will_change_count": len(change_rows),
                        "unchanged_count": unchanged_count,
                        "values": values,
                        "use_verification": use_verification,
                        "reason": reason,
                        "post_data": request.POST,
                    }
                )
                return render(
                    request,
                    "admin_bulk_edit/preview.html",
                    context,
                )

            try:
                with transaction.atomic():
                    before_hook_result = self._BulkAction__run_before_hooks(
                        self.action_type, request, objects
                    )
                    if before_hook_result is not None:
                        return before_hook_result
                    num_updated, num_unchanged = self.execute_action(
                        objects,
                        self=self,
                        values=values,
                        use_verification=use_verification,
                        reason=reason,
                    )
                    after_hook_result = self._BulkAction__run_after_hooks(
                        self.action_type, request, objects
                    )
                    if after_hook_result is not None:
                        return after_hook_result
            except BulkEditValidationError as exc:
                form.add_error(None, exc.messages[0])
                return self.form_invalid(form)

            from wagtail.admin import messages

            success_message = self.get_success_message(num_updated, num_unchanged)
            if success_message:
                messages.success(request, success_message)
            return redirect(self.next_url)

    return ModelBulkEditAction


class BulkEditIndexView(IndexView):
    template_name = "admin_bulk_edit/index.html"

    @cached_property
    def columns(self):
        return [
            BulkActionsCheckboxColumn("bulk_actions", obj_type="snippet"),
            *super().columns,
        ]


class BulkEditViewSetMixin:
    """
    Enable bulk edit on a ModelViewSet. Declare ``bulk_edit_fields`` and register
    ``bulk_edit_action`` via ``register_bulk_action`` in wagtail_hooks.
    """

    bulk_edit_fields: list[BulkEditField] = []
    bulk_edit_validate_category_parent: bool = False
    index_view_class = BulkEditIndexView

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.bulk_edit_fields:
            return
        model = getattr(cls, "model", None)
        if model is None:
            return
        cls.bulk_edit_action = make_bulk_edit_action(
            model,
            cls.bulk_edit_fields,
            validate_category_parent=getattr(
                cls, "bulk_edit_validate_category_parent", False
            ),
        )
