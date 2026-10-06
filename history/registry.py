from django.apps import apps

GLOBAL_EXCLUDED = frozenset(
    {
        "created_at",
        "updated_at",
        "verification_reminder_sent_at",
    }
)

TRACKED_FIELDS = {
    "businesses.Business": [
        "name",
        "business_type",
        "description",
        "logo",
        "website",
        "email",
        "phone",
        "address",
        "town_or_city",
        "verification_level",
        "verification_reference",
        "verified_at",
        "verified_by",
        "owner",
        "is_active",
    ],
    "businesses.RetailLocation": [
        "business",
        "name",
        "address",
        "town_or_city",
        "phone",
        "notes",
        "is_active",
    ],
    "businesses.BusinessVideo": [
        "url",
        "title",
        "kind",
    ],
    "products.Product": [
        "business",
        "name",
        "short_description",
        "description",
        "category",
        "origin_type",
        "brand_name",
        "status",
        "featured",
        "image",
        "verification_level",
        "verification_reference",
        "verified_at",
        "verified_by",
    ],
    "products.ProductVideo": [
        "url",
        "title",
        "kind",
    ],
    "products.ProductVariant": [
        "name",
        "sku",
        "barcode",
        "size_value",
        "size_unit",
        "packaging",
        "price",
        "is_available",
    ],
    "inventory.Inventory": [
        "quantity",
        "low_stock_threshold",
    ],
    "categories.Category": [
        "name",
        "slug",
        "parent",
        "is_active",
    ],
    "reviews.ProductReview": [
        "status",
        "is_published",
        "resolved_at",
    ],
    "reviews.BusinessReview": [
        "status",
        "is_published",
        "resolved_at",
    ],
    "duplicates.DuplicateFlag": [
        "status",
        "review_notes",
    ],
}


def tracked_models():
    for label in TRACKED_FIELDS:
        yield apps.get_model(label)


def tracked_field_names(model):
    label = f"{model._meta.app_label}.{model._meta.object_name}"
    names = TRACKED_FIELDS.get(label)
    if names is None:
        return ()
    return tuple(names)


def is_tracked_model(model):
    label = f"{model._meta.app_label}.{model._meta.object_name}"
    return label in TRACKED_FIELDS
