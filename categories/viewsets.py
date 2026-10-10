from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from django.contrib.admin.utils import quote
from django.urls import reverse
from wagtail.admin.ui.tables import Column, TitleColumn
from wagtail.admin.views.generic.chooser import ChooseResultsView, ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet

from simudza.utils.admin_bulk_edit import (
    BulkEditField,
    BulkEditIndexView,
    BulkEditViewSetMixin,
)
from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .admin_filters import CategoryAttentionFilterSet
from .forms import CategoryForm
from .models import Category
from .panels import CategoryIssuesPanel
from .resources import CategoryResource


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


class CategoryTreeTitleColumn(TitleColumn):
    """Title cell showing the full path, with every ancestor linked."""

    cell_template_name = "categories/admin/tree_title_cell.html"

    def __init__(self, *args, get_ancestor_url=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_ancestor_url = get_ancestor_url

    def get_cell_context_data(self, instance, parent_context):
        context = super().get_cell_context_data(instance, parent_context)
        ids = getattr(instance, "tree_path_ids", None) or [instance.pk]
        names = getattr(instance, "tree_path_names", None) or [instance.name]
        context["ancestors"] = [
            {
                "name": name,
                "url": self.get_ancestor_url(pk) if self.get_ancestor_url else None,
            }
            for pk, name in zip(ids[:-1], names[:-1])
        ]
        return context


class CategoryIndexView(BulkEditIndexView):
    default_ordering = "tree_path_names"

    def get_base_queryset(self):
        return super().get_base_queryset().with_tree_path().with_attention()

    def _get_ancestor_url(self, pk):
        if self.edit_url_name and self.user_has_permission("change"):
            return reverse(self.edit_url_name, args=(quote(pk),))
        return None

    def _get_title_column(self, field_name, column_class=TitleColumn, **kwargs):
        column_class = self._get_title_column_class(CategoryTreeTitleColumn)
        return column_class(
            "name",
            label=_("Category"),
            sort_key="tree_path_names",
            get_url=lambda instance: (
                self.get_edit_url(instance) or self.get_inspect_url(instance)
            ),
            get_ancestor_url=self._get_ancestor_url,
            **kwargs,
        )


class CategoryViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = Category
    resource_class = CategoryResource
    index_view_class = CategoryIndexView

    bulk_edit_validate_category_parent = True
    bulk_edit_fields = [
        BulkEditField("parent"),
        BulkEditField("is_active"),
    ]

    name = "category"
    menu_label = "Categories"
    menu_icon = "folder-open-inverse"

    add_to_admin_menu = False
    filterset_class = CategoryAttentionFilterSet

    list_display = [
        "name",
        Column(
            "attention_count",
            label=_("Needs attention"),
            accessor="attention_count",
            sort_key="attention_count",
        ),
        "is_active",
    ]

    list_filter = [
        "is_active",
        "parent",
        "needs_attention",
    ]

    search_fields = [
        "name",
        "slug",
    ]

    # Panels are required for Wagtail admin widgets. ModelViewSet ignores
    # form_class and otherwise builds a plain Django form from form_fields.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("name"),
                    FieldPanel("parent"),
                ],
                heading="Category details",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("is_active"),
                ],
                heading="Settings",
            ),
            CategoryIssuesPanel(heading="Data quality"),
        ],
        base_form_class=CategoryForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "name",
        "slug",
        "parent",
        "is_active",
        "created_at",
        "updated_at",
    ]
