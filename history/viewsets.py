from django.urls import path, reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView
from wagtail.admin.ui.tables import Column, DateColumn
from wagtail.admin.views.generic import InspectView
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.widgets import Button

from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .models import ChangeLog
from .resources import ChangeLogResource
from .views import ChangeLogUndoView


class UndoColumn(Column):
    cell_template_name = "history/admin/undo_cell.html"

    def get_cell_context_data(self, instance, parent_context):
        context = super().get_cell_context_data(instance, parent_context)
        if instance.may_be_undoable:
            context["undo_url"] = reverse("change_log:undo", args=[instance.pk])
        return context


class ChangeLogInspectView(InspectView):
    @cached_property
    def header_buttons(self):
        buttons = list(super().header_buttons)
        if self.object.may_be_undoable:
            buttons.append(
                Button(
                    _("Undo"),
                    url=reverse("change_log:undo", args=[self.object.pk]),
                    icon_name="undo",
                    priority=10,
                )
            )
        return buttons


class ChangeLogViewSet(ImportExportViewSetMixin, ModelViewSet):
    model = ChangeLog
    resource_class = ChangeLogResource

    name = "change_log"
    menu_label = _("Change history")
    menu_icon = "history"
    menu_order = 50

    add_to_admin_menu = False
    add_to_settings_menu = True

    add_view_enabled = False
    edit_view_enabled = False
    delete_view_enabled = False
    copy_view_enabled = False
    inspect_view_enabled = True

    form_fields = []

    list_display = [
        "object_repr",
        Column("action", label=_("Action"), accessor="get_action_display"),
        Column("field_label", label=_("Field"), accessor="field_display"),
        Column("old_value", label=_("Old value"), accessor="old_value_display"),
        Column("new_value", label=_("New value"), accessor="new_value_display"),
        Column("changed_by_repr", label=_("Changed by"), accessor="changed_by_repr"),
        DateColumn("changed_at", label=_("When"), sort_key="changed_at"),
        Column("source", label=_("Source"), accessor="get_source_display"),
        "reason",
        UndoColumn("undo", label=_("Undo")),
    ]

    inspect_view_class = ChangeLogInspectView

    list_filter = [
        "content_type",
        "action",
        "source",
        "changed_by",
        "changed_at",
    ]

    search_fields = [
        "object_repr",
        "field_name",
        "field_label",
        "old_value",
        "new_value",
        "reason",
        "changed_by_repr",
    ]

    inspect_view_fields = [
        "content_type",
        "object_id",
        "object_repr",
        "action",
        "field_name",
        "field_label",
        "old_value",
        "new_value",
        "changed_by",
        "changed_by_repr",
        "changed_at",
        "source",
        "reason",
        "batch_id",
        "undone_at",
        "undone_by",
    ]

    def get_urlpatterns(self):
        patterns = [p for p in super().get_urlpatterns() if p.name != "edit"]
        return patterns + [
            path(
                "edit/<int:pk>/",
                RedirectView.as_view(pattern_name="change_log:inspect"),
                name="edit",
            ),
            path("undo/<int:pk>/", ChangeLogUndoView.as_view(), name="undo"),
        ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ct_id = request.GET.get("content_type_id")
        object_id = request.GET.get("object_id")
        if ct_id and object_id:
            qs = qs.filter(content_type_id=ct_id, object_id=str(object_id))
        return qs
