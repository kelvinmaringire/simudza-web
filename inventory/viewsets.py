from django.urls import path
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet

from simudza.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.admin_import_export import ImportExportViewSetMixin

from .forms import InventoryForm
from .models import Inventory
from .resources import InventoryResource


class InventoryViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = Inventory
    resource_class = InventoryResource

    bulk_edit_fields = [
        BulkEditField("low_stock_threshold"),
    ]

    name = "inventory"
    menu_label = "Inventory"
    menu_icon = "table"

    add_to_admin_menu = True
    copy_view_enabled = False

    list_display = [
        "variant",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "low_stock_threshold",
        "updated_at",
    ]

    list_filter = [
        "variant__product__status",
        "variant__product__category",
        "variant__product__business",
    ]

    search_fields = [
        "variant__product__name",
        "variant__product__slug",
        "variant__sku",
        "variant__product__brand_name",
        "variant__product__business__name",
    ]

    # Inventory is auto-created with each product — edit stock only.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("variant", read_only=True),
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
        "variant",
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
        patterns = [
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
        patterns.extend(self.import_export_urlpatterns())
        return patterns
