from django import forms
from django.db.models import Q
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

from .forms import ProductForm
from .models import Product


class ProductChooserFilterForm(BaseFilterForm):
    q = forms.CharField(
        label=_("Search term"),
        widget=forms.TextInput(attrs={"placeholder": _("Search products")}),
        required=False,
    )

    def filter(self, objects):
        objects = super().filter(objects)
        search_query = self.cleaned_data.get("q")
        if search_query:
            objects = objects.filter(
                Q(name__icontains=search_query)
                | Q(slug__icontains=search_query)
                | Q(brand_name__icontains=search_query)
                | Q(sku__icontains=search_query)
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


class ProductViewSet(ModelViewSet):
    model = Product

    name = "product"
    menu_label = "Products"
    menu_icon = "tag"

    add_to_admin_menu = True

    list_display = [
        "name",
        "business",
        "category",
        "origin_type",
        "status",
        "featured",
    ]

    list_filter = [
        "status",
        "origin_type",
        "featured",
        "category",
        "business",
    ]

    search_fields = [
        "name",
        "short_description",
        "description",
        "brand_name",
        "sku",
        "barcode",
        "slug",
    ]

    # Panels are required for Wagtail admin widgets. ModelViewSet ignores
    # form_class and otherwise builds a plain Django form from form_fields.
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
                    FieldPanel("sku"),
                    FieldPanel("barcode"),
                    FieldPanel("size_value"),
                    FieldPanel("size_unit"),
                ],
                heading="Origin & identity",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("price"),
                ],
                heading="Pricing",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("status"),
                    FieldPanel("featured"),
                    FieldPanel("verified_at"),
                ],
                heading="Publishing",
            ),
            InlinePanel("images", label="Gallery image"),
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
        "sku",
        "barcode",
        "size_value",
        "size_unit",
        "price",
        "status",
        "featured",
        "image",
        "verified_at",
        "created_at",
        "updated_at",
    ]
