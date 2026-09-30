from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import Category


class CategoryResource(resources.ModelResource):
    parent = fields.Field(
        column_name="parent",
        attribute="parent",
        widget=ForeignKeyWidget(Category, "slug"),
    )

    class Meta:
        model = Category
        import_id_fields = ("slug",)
        skip_unchanged = True
        fields = (
            "slug",
            "name",
            "description",
            "parent",
            "is_active",
            "sort_order",
        )
        export_order = fields
