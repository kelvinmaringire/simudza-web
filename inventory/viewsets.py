from django.urls import path
from wagtail.admin.panels import FieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet

from simudza.utils.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.utils.admin_grid import GridPanel, GridRow
from simudza.utils.admin_import_export import ImportExportViewSetMixin
from simudza.utils.admin_save_actions import SaveActionsViewSetMixin

from .forms import InventoryForm
from .models import Inventory
from .resources import InventoryResource


class InventoryViewSet(
    SaveActionsViewSetMixin, BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet
):
    model = Inventory
    resource_class = InventoryResource

    bulk_edit_fields = [
        BulkEditField("low_stock_threshold"),
    ]

    name = "inventory"
    menu_label = "Inventory"
    menu_icon = "table"

    add_to_admin_menu = False
    copy_view_enabled = False

    list_display = [
        "variant",
        "sku",
        "barcode",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "low_stock_threshold",
        "updated_at",
    ]

    list_filter = [
        "variant__product__category",
        "variant__product__business",
    ]

    search_fields = [
        "variant__product__name",
        "variant__product__slug",
        "sku",
        "barcode",
        "variant__product__brand_name",
        "variant__product__business__name",
    ]

    # Inventory is auto-created with each variant — edit identifiers and stock only.
    edit_handler = ObjectList(
        [
            GridPanel(
                [
                    FieldPanel("variant", read_only=True),
                    GridRow([FieldPanel("sku"), FieldPanel("barcode")]),
                ],
                heading="Identifiers",
            ),
            GridPanel(
                [
                    GridRow(
                        [
                            FieldPanel("quantity"),
                            FieldPanel("reserved_quantity"),
                            FieldPanel("low_stock_threshold"),
                        ]
                    ),
                ],
                heading="Stock levels",
            ),
        ],
        base_form_class=InventoryForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "variant",
        "sku",
        "barcode",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "is_low_stock",
        "low_stock_threshold",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request=None):
        # Stock admin only for marketplace products that track quantity.
        from marketplace.models import VariantOffer

        return Inventory.objects.filter(
            variant__product__marketplace_enabled=True,
            variant__offer__stock_mode=VariantOffer.StockMode.TRACKED,
        ).select_related("variant", "variant__product", "variant__offer")

    def get_common_view_kwargs(self, **kwargs):
        view_kwargs = super().get_common_view_kwargs(**kwargs)
        # Wagtail IndexView/EditView read ``queryset``; ViewSet.get_queryset alone
        # is never called by the admin list.
        view_kwargs["queryset"] = self.get_queryset()
        # No manual create — inventory comes from product variants.
        view_kwargs["add_url_name"] = None
        return view_kwargs

    def get_urlpatterns(self):
        conv = self.pk_path_converter
        patterns = [
            path("", self.index_view, name="index"),
            path("results/", self.index_results_view, name="index_results"),
            path(f"edit/<{conv}:pk>/", self.edit_view, name="edit"),
            path(f"delete/<{conv}:pk>/", self.delete_view, name="delete"),
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
