from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Category


class CategoryResource(resources.ModelResource):
    # Database ids differ between environments; rows are matched on slug.
    id = fields.Field(attribute="id", column_name="id", readonly=True)
    parent = fields.Field(
        column_name="parent",
        attribute="parent",
        widget=ForeignKeyWidget(Category, "slug"),
    )
    created_at = fields.Field(
        attribute="created_at", column_name="created_at", readonly=True
    )
    updated_at = fields.Field(
        attribute="updated_at", column_name="updated_at", readonly=True
    )

    class Meta:
        model = Category
        import_id_fields = ("slug",)
        skip_unchanged = True
        clean_model_instances = True
        fields = (
            "id",
            "name",
            "slug",
            "parent",
            "is_active",
            "created_at",
            "updated_at",
        )
        export_order = fields
