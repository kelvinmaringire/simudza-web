from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms.choosers import BaseFilterForm
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, ObjectList
from wagtail.admin.ui.tables import Column
from wagtail.admin.views.generic.chooser import ChooseResultsView, ChooseView
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.viewsets.model import ModelViewSet

from .forms import BusinessForm
from .models import Business


class BusinessChooserFilterForm(BaseFilterForm):
    q = forms.CharField(
        label=_("Search term"),
        widget=forms.TextInput(attrs={"placeholder": _("Search businesses")}),
        required=False,
    )

    def filter(self, objects):
        objects = super().filter(objects)
        search_query = self.cleaned_data.get("q")
        if search_query:
            objects = objects.filter(
                Q(name__icontains=search_query)
                | Q(city__icontains=search_query)
                | Q(province__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(phone__icontains=search_query)
            )
            self.is_searching = True
            self.search_query = search_query
        return objects


class BusinessChooseViewMixin:
    filter_form_class = BusinessChooserFilterForm

    @property
    def columns(self):
        return [
            self.title_column,
            Column("city", label=_("City"), accessor="city"),
            Column(
                "business_type",
                label=_("Type"),
                accessor="get_business_type_display",
            ),
        ]


class BusinessChooseView(BusinessChooseViewMixin, ChooseView):
    pass


class BusinessChooseResultsView(BusinessChooseViewMixin, ChooseResultsView):
    pass


class BusinessChooserViewSet(ChooserViewSet):
    model = Business
    icon = "home"
    choose_one_text = _("Choose a business")
    choose_another_text = _("Choose another business")
    edit_item_text = _("Edit this business")
    choose_view_class = BusinessChooseView
    choose_results_view_class = BusinessChooseResultsView


business_chooser_viewset = BusinessChooserViewSet("business_chooser")


class BusinessViewSet(ModelViewSet):
    model = Business

    name = "business"
    menu_label = "Businesses"
    menu_icon = "home"

    add_to_admin_menu = True

    list_display = [
        "name",
        "business_type",
        "verification_status",
        "city",
        "country",
        "is_active",
    ]

    list_filter = [
        "business_type",
        "verification_status",
        "is_active",
        "country",
        "province",
    ]

    search_fields = [
        "name",
        "description",
        "city",
        "province",
        "country",
        "email",
        "phone",
    ]

    # Panels are required for Wagtail widgets (image chooser, date picker).
    # ModelViewSet ignores form_class and builds a plain Django form from
    # form_fields, which is why AdminImageChooser / AdminDateTimeInput
    # never appeared before.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("name"),
                    FieldPanel("business_type"),
                    FieldPanel("description"),
                    FieldPanel("logo"),
                ],
                heading="Business details",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("website"),
                    FieldPanel("email"),
                    FieldPanel("phone"),
                    FieldPanel("address"),
                    FieldPanel("city"),
                    FieldPanel("province"),
                    FieldPanel("country"),
                ],
                heading="Contact",
            ),
            MultiFieldPanel(
                [
                    FieldPanel("verification_status"),
                    FieldPanel("verified_at"),
                    FieldPanel("is_active"),
                ],
                heading="Verification",
            ),
        ],
        base_form_class=BusinessForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "name",
        "slug",
        "business_type",
        "description",
        "logo",
        "website",
        "email",
        "phone",
        "address",
        "city",
        "province",
        "country",
        "verification_status",
        "verified_at",
        "owner",
        "is_active",
        "created_at",
        "updated_at",
    ]
