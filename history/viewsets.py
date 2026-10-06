from django.utils.translation import gettext_lazy as _
from wagtail.admin.ui.tables import Column, DateColumn
from wagtail.admin.viewsets.model import ModelViewSet

from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .models import ChangeLog
from .resources import ChangeLogResource


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
        Column("field_label", label=_("Field"), accessor="field_label"),
        "old_value",
        "new_value",
        Column("changed_by_repr", label=_("Changed by"), accessor="changed_by_repr"),
        DateColumn("changed_at", label=_("When"), sort_key="changed_at"),
        Column("source", label=_("Source"), accessor="get_source_display"),
        "reason",
    ]

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
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ct_id = request.GET.get("content_type_id")
        object_id = request.GET.get("object_id")
        if ct_id and object_id:
            qs = qs.filter(content_type_id=ct_id, object_id=str(object_id))
        return qs
