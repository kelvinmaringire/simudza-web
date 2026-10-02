import django_filters
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import WagtailFilterSet

from .models import Category


class CategoryAttentionFilterSet(WagtailFilterSet):
    needs_attention = django_filters.ChoiceFilter(
        label=_("Needs attention"),
        choices=[
            ("", "---------"),
            ("yes", _("Yes")),
        ],
        method="filter_needs_attention",
    )

    class Meta:
        model = Category
        fields = ["is_active", "parent"]

    def filter_needs_attention(self, queryset, name, value):
        if value != "yes":
            return queryset
        return queryset.needing_attention()
