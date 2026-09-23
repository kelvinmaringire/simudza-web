from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from .forms import BusinessReviewForm, ProductReviewForm
from .models import BusinessReview, ProductReview


class ProductReviewViewSet(ModelViewSet):
    model = ProductReview

    name = "product_review"
    menu_label = "Product reviews"
    menu_icon = "comment"
    add_to_admin_menu = False

    list_display = [
        "user",
        "product",
        "rating",
        "is_published",
        "created_at",
    ]

    list_filter = [
        "rating",
        "is_published",
    ]

    search_fields = [
        "title",
        "body",
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
                    FieldPanel("user"),
                    FieldPanel("product"),
                    FieldPanel("rating"),
                    FieldPanel("title"),
                    FieldPanel("body"),
                    FieldPanel("is_published"),
                ],
                heading="Product review",
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
        "is_published",
        "created_at",
        "updated_at",
    ]


class BusinessReviewViewSet(ModelViewSet):
    model = BusinessReview

    name = "business_review"
    menu_label = "Business reviews"
    menu_icon = "comment"
    add_to_admin_menu = False

    list_display = [
        "user",
        "business",
        "rating",
        "is_published",
        "created_at",
    ]

    list_filter = [
        "rating",
        "is_published",
    ]

    search_fields = [
        "title",
        "body",
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
                    FieldPanel("user"),
                    FieldPanel("business"),
                    FieldPanel("rating"),
                    FieldPanel("title"),
                    FieldPanel("body"),
                    FieldPanel("is_published"),
                ],
                heading="Business review",
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
        "is_published",
        "created_at",
        "updated_at",
    ]


class ReviewsViewSetGroup(ModelViewSetGroup):
    menu_label = "Reviews"
    menu_icon = "comment"
    items = (
        ProductReviewViewSet,
        BusinessReviewViewSet,
    )
