import django_filters
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import WagtailFilterSet

from .models import Category
from .quality import ISSUE_LABELS


class CategoryAttentionFilterSet(WagtailFilterSet):
    needs_attention = django_filters.ChoiceFilter(
        label=_("Needs attention"),
        choices=[
            ("", "---------"),
            ("yes", _("Yes")),
        ],
        method="filter_needs_attention",
    )
    parent = django_filters.ModelChoiceFilter(
        label=_("Parent"),
        queryset=Category.objects.with_tree_path().order_by("tree_path_names"),
    )
    issue = django_filters.ChoiceFilter(
        label=_("Issue"),
        choices=[("", "---------")] + list(ISSUE_LABELS.items()),
        method="filter_issue",
    )

    class Meta:
        model = Category
        fields = ["is_active", "parent"]

    def filter_needs_attention(self, queryset, name, value):
        if value != "yes":
            return queryset
        return queryset.needing_attention()

    def filter_issue(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.with_issue(value)
