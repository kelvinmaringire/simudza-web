from django.urls import path
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet

from .forms import InventoryForm
from .models import Inventory


class InventoryViewSet(ModelViewSet):
    model = Inventory

    name = "inventory"
    menu_label = "Inventory"
    menu_icon = "table"

    add_to_admin_menu = True
    copy_view_enabled = False

    list_display = [
        "product",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "low_stock_threshold",
        "updated_at",
    ]

    list_filter = [
        "product__status",
        "product__category",
        "product__business",
    ]

    search_fields = [
        "product__name",
        "product__slug",
        "product__sku",
        "product__brand_name",
        "product__business__name",
    ]

    # Inventory is auto-created with each product — edit stock only.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("product", read_only=True),
                    FieldPanel("quantity"),
                    FieldPanel("reserved_quantity"),
                    FieldPanel("low_stock_threshold"),
                ],
                heading="Stock levels",
            ),
        ],
        base_form_class=InventoryForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "product",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "is_low_stock",
        "low_stock_threshold",
        "created_at",
        "updated_at",
    ]

    def get_common_view_kwargs(self, **kwargs):
        view_kwargs = super().get_common_view_kwargs(**kwargs)
        # No manual create/delete — inventory comes from products.
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
