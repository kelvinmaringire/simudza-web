from import_export import resources

from .models import ChangeLog


class ChangeLogResource(resources.ModelResource):
    class Meta:
        model = ChangeLog
        fields = (
            "id",
            "object_repr",
            "action",
            "field_name",
            "field_label",
            "old_value",
            "new_value",
            "changed_by_repr",
            "changed_at",
            "source",
            "reason",
            "batch_id",
        )
        export_order = fields
