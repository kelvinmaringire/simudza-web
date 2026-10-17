from django import forms
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.admin.panels import (
    FieldPanel,
    InlinePanel,
    ObjectList,
)
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic.chooser import ChooseResultsView, ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet

from duplicates.panels import PossibleDuplicatesPanel
from history.panels import ChangeHistoryPanel

from .admin_filters import ProductQualityFilterSet
from .panels import CollapsedInlinePanel, DataQualityPanel
from .quality import MAX_SCORE
from simudza.utils.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.utils.admin_grid import GridPanel, GridRow
from simudza.utils.admin_import_export import ImportExportViewSetMixin
from simudza.utils.admin_save_actions import SaveActionsViewSetMixin

from .forms import ProductForm
from .models import Product
from .resources import ProductResource


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
    return f"{product.quality_score}/{MAX_SCORE}"


class ProductViewSet(
    SaveActionsViewSetMixin, BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet
):
    model = Product
    resource_class = ProductResource

    bulk_edit_fields = [
        BulkEditField("business"),
        BulkEditField("category"),
        BulkEditField("status"),
        BulkEditField("lifecycle_status"),
        BulkEditField("origin_type"),
        BulkEditField("brand_name"),
        BulkEditField("featured"),
        BulkEditField("marketplace_enabled"),
        BulkEditField(
            "verification_level",
            applier="verification",
            companions=("verification_reference",),
        ),
    ]

    name = "product"
    menu_label = "Products"
    menu_icon = "tag"

    add_to_admin_menu = False
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
        "lifecycle_status",
        "verified_at",
        "verification_level",
        "verification_reference",
        "featured",
        "marketplace_enabled",
    ]

    list_filter = [
        "status",
        "lifecycle_status",
        "verification_level",
        "origin_type",
        "featured",
        "marketplace_enabled",
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
        "slug",
    ]

    edit_handler = ObjectList(
        [
            GridPanel(
                [
                    GridRow([FieldPanel("name"), FieldPanel("business")]),
                    GridRow([FieldPanel("category"), FieldPanel("short_description")]),
                    FieldPanel("description"),
                    FieldPanel("image"),
                ],
                heading="Product details",
            ),
            GridPanel(
                [
                    GridRow([FieldPanel("origin_type"), FieldPanel("brand_name")]),
                ],
                heading="Origin & identity",
            ),
            CollapsedInlinePanel(
                "variants",
                label="Variant",
                help_text="Optional. Add variants only for different flavours, sizes or packaging.",
            ),
            GridPanel(
                [
                    GridRow([FieldPanel("status"), FieldPanel("lifecycle_status")]),
                    GridRow([FieldPanel("verification_level")]),
                    GridRow([FieldPanel("verified_at")]),
                    GridRow(
                        [FieldPanel("verification_reference"), FieldPanel("featured")]
                    ),
                    FieldPanel("marketplace_enabled"),
                ],
                heading="Publishing",
            ),
            CollapsedInlinePanel("images", label="Gallery image"),
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
        "lifecycle_status",
        "featured",
        "marketplace_enabled",
        "image",
        "verified_at",
        "verification_level",
        "verification_reference",
        "verified_by",
        "created_at",
        "updated_at",
    ]

