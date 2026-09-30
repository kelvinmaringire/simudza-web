from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from accounts.models import CustomUser
from businesses.models import Business
from products.models import Product

from .models import BusinessReview, ProductReview


class ProductReviewResource(resources.ModelResource):
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    product = fields.Field(
        column_name="product",
        attribute="product",
        widget=ForeignKeyWidget(Product, "slug"),
    )

    class Meta:
        model = ProductReview
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = (
            "id",
            "user",
            "product",
            "rating",
            "title",
            "body",
            "reason",
            "status",
            "guest_name",
            "guest_email",
            "resolved_at",
            "is_published",
        )
        export_order = fields


class BusinessReviewResource(resources.ModelResource):
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    business = fields.Field(
        column_name="business",
        attribute="business",
        widget=ForeignKeyWidget(Business, "slug"),
    )

    class Meta:
        model = BusinessReview
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = (
            "id",
            "user",
            "business",
            "rating",
            "title",
            "body",
            "reason",
            "status",
            "guest_name",
            "guest_email",
            "resolved_at",
            "is_published",
        )
        export_order = fields
