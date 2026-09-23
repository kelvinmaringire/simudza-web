from django.urls import path
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet

from .forms import DirectoryListingForm
from .models import DirectoryListing


class DirectoryListingViewSet(ModelViewSet):
    model = DirectoryListing

    name = "directory_listing"
    menu_label = "Directory"
    menu_icon = "list-ul"

    add_to_admin_menu = True
    copy_view_enabled = False

    list_display = [
        "product",
        "featured",
        "show_in_directory",
        "views",
    ]

    list_filter = [
        "featured",
        "show_in_directory",
        "product__status",
        "product__category",
        "product__business",
    ]

    search_fields = [
        "product__name",
        "product__slug",
        "product__brand_name",
        "product__short_description",
    ]

    # Listings are auto-created with each product — edit toggles only.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("product", read_only=True),
                    FieldPanel("featured"),
                    FieldPanel("show_in_directory"),
                ],
                heading="Directory visibility",
            ),
        ],
        base_form_class=DirectoryListingForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "product",
        "featured",
        "show_in_directory",
        "views",
        "created_at",
        "updated_at",
    ]

    def get_common_view_kwargs(self, **kwargs):
        view_kwargs = super().get_common_view_kwargs(**kwargs)
        # No manual create/delete — listings come from products.
        view_kwargs["add_url_name"] = None
        view_kwargs["delete_url_name"] = None
        return view_kwargs

    def get_urlpatterns(self):
        conv = self.pk_path_converter
        return [
            path("", self.index_view, name="index"),
            path("results/", self.index_results_view, name="index_results"),
            path(f"edit/<{conv}:pk>/", self.edit_view, name="edit"),
            path(f"history/<{conv}:pk>/", self.history_view, name="history"),
            path(
                f"history-results/<{conv}:pk>/",
                self.history_results_view,
                name="history_results",
            ),
            path(f"usage/<{conv}:pk>/", self.usage_view, name="usage"),
            path(f"inspect/<{conv}:pk>/", self.inspect_view, name="inspect"),
        ]
