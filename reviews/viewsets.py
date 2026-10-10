from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.ui.tables import Column
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .forms import BusinessReviewForm, ProductReviewForm
from .models import BusinessReview, ProductReview
from .resources import BusinessReviewResource, ProductReviewResource


def _reporter_column():
    return Column(
        "reporter_display",
        label="Reporter",
        accessor="reporter_display",
    )


class ProductReviewViewSet(ImportExportViewSetMixin, ModelViewSet):
    model = ProductReview
    resource_class = ProductReviewResource

    name = "product_review"
    menu_label = "Product reviews"
    menu_icon = "comment"
    add_to_admin_menu = False

    list_display = [
        "product",
        "reason",
        "status",
        _reporter_column(),
        "rating",
        "created_at",
    ]

    list_filter = [
        "reason",
        "status",
        "rating",
        "is_published",
    ]

    search_fields = [
        "title",
        "body",
        "guest_name",
        "guest_email",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "product__name",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("product"),
                    FieldPanel("user"),
                    FieldPanel("rating"),
                    FieldPanel("title"),
                    FieldPanel("body"),
                    FieldPanel("is_published"),
                ],
                heading="Review",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("reason"),
                    FieldPanel("status"),
                    FieldPanel("guest_name"),
                    FieldPanel("guest_email"),
                    FieldPanel("resolved_at"),
                ],
                heading="Report",
            ),
        ],
        base_form_class=ProductReviewForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "user",
        "product",
        "rating",
        "title",
        "body",
        "reason",
        "status",
        "guest_name",
        "guest_email",
        "ip_address",
        "resolved_at",
        "is_published",
        "created_at",
        "updated_at",
    ]


class BusinessReviewViewSet(ImportExportViewSetMixin, ModelViewSet):
    model = BusinessReview
    resource_class = BusinessReviewResource

    name = "business_review"
    menu_label = "Business reviews"
    menu_icon = "comment"
    add_to_admin_menu = False

    list_display = [
        "business",
        "reason",
        "status",
        _reporter_column(),
        "rating",
        "created_at",
    ]

    list_filter = [
        "reason",
        "status",
        "rating",
        "is_published",
    ]

    search_fields = [
        "title",
        "body",
        "guest_name",
        "guest_email",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "business__name",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("business"),
                    FieldPanel("user"),
                    FieldPanel("rating"),
                    FieldPanel("title"),
                    FieldPanel("body"),
                    FieldPanel("is_published"),
                ],
                heading="Review",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("reason"),
                    FieldPanel("status"),
                    FieldPanel("guest_name"),
                    FieldPanel("guest_email"),
                    FieldPanel("resolved_at"),
                ],
                heading="Report",
            ),
        ],
        base_form_class=BusinessReviewForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "user",
        "business",
        "rating",
        "title",
        "body",
        "reason",
        "status",
        "guest_name",
        "guest_email",
        "ip_address",
        "resolved_at",
        "is_published",
        "created_at",
        "updated_at",
    ]


class ReviewsViewSetGroup(ModelViewSetGroup):
    menu_label = "Reviews"
    menu_icon = "comment"
    menu_order = 640
    items = (
        ProductReviewViewSet,
        BusinessReviewViewSet,
    )
