from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic.chooser import ChooseResultsView, ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet

from .forms import CategoryForm
from .models import Category


class CategoryChooserFilterForm(BaseFilterForm):
    q = forms.CharField(
        label=_("Search term"),
        widget=forms.TextInput(attrs={"placeholder": _("Search categories")}),
        required=False,
    )

    def filter(self, objects):
        objects = super().filter(objects)
        search_query = self.cleaned_data.get("q")
        if search_query:
            objects = objects.filter(
                Q(name__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(slug__icontains=search_query)
                | Q(parent__name__icontains=search_query)
            ).distinct()
            self.is_searching = True
            self.search_query = search_query
        return objects


class CategoryChooseViewMixin:
    filter_form_class = CategoryChooserFilterForm

    @property
    def columns(self):
        return [
            self.title_column,
            Column("parent", label=_("Parent"), accessor="parent"),
            Column(
                "is_active",
                label=_("Active"),
                accessor="is_active",
            ),
        ]


class CategoryChooseView(CategoryChooseViewMixin, ChooseView):
    pass


class CategoryChooseResultsView(CategoryChooseViewMixin, ChooseResultsView):
    pass


class CategoryChooserViewSet(ChooserViewSet):
    model = Category
    icon = "folder-open-inverse"
    choose_one_text = _("Choose a category")
    choose_another_text = _("Choose another category")
    edit_item_text = _("Edit this category")
    choose_view_class = CategoryChooseView
    choose_results_view_class = CategoryChooseResultsView


category_chooser_viewset = CategoryChooserViewSet("category_chooser")


class CategoryViewSet(ModelViewSet):
    model = Category

    name = "category"
    menu_label = "Categories"
    menu_icon = "folder-open-inverse"

    add_to_admin_menu = True

    list_display = [
        "name",
        "parent",
        "sort_order",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "parent",
    ]

    search_fields = [
        "name",
        "description",
        "slug",
    ]

    # Panels are required for Wagtail admin widgets. ModelViewSet ignores
    # form_class and otherwise builds a plain Django form from form_fields.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("name"),
                    FieldPanel("description"),
                    FieldPanel("parent"),
                ],
                heading="Category details",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("sort_order"),
                    FieldPanel("is_active"),
                ],
                heading="Settings",
            ),
        ],
        base_form_class=CategoryForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "name",
        "slug",
        "description",
        "parent",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    ]
