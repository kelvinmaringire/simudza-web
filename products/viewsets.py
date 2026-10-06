from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.admin.panels import (
    FieldPanel,
    InlinePanel,
    MultiFieldPanel,
    ObjectList,
)
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic.chooser import ChooseResultsView, ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet

from duplicates.panels import PossibleDuplicatesPanel
from history.panels import ChangeHistoryPanel

from .admin_filters import ProductQualityFilterSet
from .panels import DataQualityPanel
from simudza.utils.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .forms import ProductForm, ProductVariantForm
from .models import Product, ProductVariant
from .resources import ProductResource, ProductVariantResource


class ProductChooserFilterForm(BaseFilterForm):
    q = forms.CharField(
        label=_("Search term"),
        widget=forms.TextInput(attrs={"placeholder": _("Search products")}),
        required=False,
    )

    def filter(self, objects):
        from django.db.models import Q

        objects = super().filter(objects)
        search_query = self.cleaned_data.get("q")
        if search_query:
            objects = objects.filter(
                Q(name__icontains=search_query)
                | Q(slug__icontains=search_query)
                | Q(brand_name__icontains=search_query)
                | Q(variants__sku__icontains=search_query)
                | Q(business__name__icontains=search_query)
            ).distinct()
            self.is_searching = True
            self.search_query = search_query
        return objects


class ProductChooseViewMixin:
    filter_form_class = ProductChooserFilterForm

    @property
    def columns(self):
        return [
            self.title_column,
            Column("business", label=_("Business"), accessor="business"),
            Column("category", label=_("Category"), accessor="category"),
            Column(
                "status",
                label=_("Status"),
                accessor="get_status_display",
            ),
        ]


class ProductChooseView(ProductChooseViewMixin, ChooseView):
    pass


class ProductChooseResultsView(ProductChooseViewMixin, ChooseResultsView):
    pass


class ProductChooserViewSet(ChooserViewSet):
    model = Product
    icon = "tag"
    choose_one_text = _("Choose a product")
    choose_another_text = _("Choose another product")
    edit_item_text = _("Edit this product")
    choose_view_class = ProductChooseView
    choose_results_view_class = ProductChooseResultsView


product_chooser_viewset = ProductChooserViewSet("product_chooser")


def _product_quality_display(product):
    return f"{product.quality_score}/10"


class ProductViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = Product
    resource_class = ProductResource

    bulk_edit_fields = [
        BulkEditField("business"),
        BulkEditField("category"),
        BulkEditField("status"),
        BulkEditField("origin_type"),
        BulkEditField("brand_name"),
        BulkEditField("featured"),
        BulkEditField(
            "verification_level",
            applier="verification",
            companions=("verification_reference",),
        ),
    ]

    name = "product"
    menu_label = "Products"
    menu_icon = "tag"
    menu_order = 200

    add_to_admin_menu = True
    filterset_class = ProductQualityFilterSet

    list_display = [
        "name",
        Column(
            "quality_score",
            label=_("Data quality"),
            accessor=_product_quality_display,
            sort_key="quality_score",
        ),
        "business",
        "category",
        "origin_type",
        "status",
        "verified_at",
        "verification_level",
        "verification_reference",
        "featured",
    ]

    list_filter = [
        "status",
        "origin_type",
        "featured",
        "category",
        "business",
        "issue",
        "quality_score_max",
        "quality_score_min",
    ]

    search_fields = [
        "name",
        "short_description",
        "description",
        "brand_name",
        "variants__sku",
        "variants__barcode",
        "slug",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("business"),
                    FieldPanel("name"),
                    FieldPanel("short_description"),
                    FieldPanel("description"),
                    FieldPanel("category"),
                    FieldPanel("image"),
                ],
                heading="Product details",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("origin_type"),
                    FieldPanel("brand_name"),
                ],
                heading="Origin & identity",
            ),
            InlinePanel("variants", label="Variant", min_num=1),
            MultiFieldPanel(
                [
                    FieldPanel("status"),
                    FieldPanel("featured"),
                    FieldPanel("verified_at"),
                    FieldPanel("verification_level"),
                    FieldPanel("verification_reference"),
                ],
                heading="Publishing",
            ),
            InlinePanel("images", label="Gallery image"),
            InlinePanel(
                "videos",
                label="Video",
                heading="Videos",
                help_text="YouTube links, e.g. demonstrations, adverts or reviews.",
            ),
            PossibleDuplicatesPanel(heading="Possible duplicates"),
            DataQualityPanel(heading="Data quality"),
            FieldPanel("change_reason"),
            ChangeHistoryPanel(),
        ],
        base_form_class=ProductForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "name",
        "slug",
        "business",
        "category",
        "short_description",
        "description",
        "origin_type",
        "brand_name",
        "status",
        "featured",
        "image",
        "verified_at",
        "verification_level",
        "verification_reference",
        "verified_by",
        "created_at",
        "updated_at",
    ]


def _variant_available_stock(variant):
    try:
        return variant.inventory.available_quantity
    except Exception:
        return 0


class ProductVariantViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = ProductVariant
    resource_class = ProductVariantResource

    bulk_edit_fields = [
        BulkEditField("is_available"),
        BulkEditField("price"),
        BulkEditField("packaging"),
        BulkEditField("size_unit"),
    ]

    name = "product_variant"
    menu_label = "Product variants"
    menu_icon = "list-ul"
    menu_order = 201

    add_to_admin_menu = True

    list_display = [
        Column("product", label=_("Product"), accessor="product"),
        Column("label", label=_("Label"), accessor="label"),
        "sku",
        "price",
        "is_available",
        Column(
            "available_stock",
            label=_("Available stock"),
            accessor=_variant_available_stock,
        ),
    ]

    list_filter = [
        "is_available",
        "product__business",
        "product__category",
    ]

    search_fields = [
        "name",
        "sku",
        "barcode",
        "product__name",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("product", "inventory")
            .order_by("product__name", "sort_order", "pk")
        )

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [FieldPanel("product")],
                heading="Product",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("name"),
                    FieldPanel("sku"),
                    FieldPanel("barcode"),
                ],
                heading="Identity",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("size_value"),
                    FieldPanel("size_unit"),
                    FieldPanel("packaging"),
                ],
                heading="Size & packaging",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("price"),
                    FieldPanel("is_available"),
                ],
                heading="Pricing & availability",
            ),
            InlinePanel("images", label="Variant image"),
            FieldPanel("change_reason"),
            ChangeHistoryPanel(),
        ],
        base_form_class=ProductVariantForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "product",
        "name",
        "label",
        "sku",
        "barcode",
        "size_value",
        "size_unit",
        "packaging",
        "price",
        "is_available",
        "created_at",
        "updated_at",
    ]
