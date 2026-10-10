import django_filters
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import WagtailFilterSet

from .models import Product
from .quality import ISSUE_LABELS


class ProductQualityFilterSet(WagtailFilterSet):
    issue = django_filters.ChoiceFilter(
        label=_("Issue"),
        choices=[("", "---------")] + [(k, v) for k, v in ISSUE_LABELS.items()],
        method="filter_issue",
    )
    quality_score_max = django_filters.NumberFilter(
        field_name="quality_score",
        lookup_expr="lte",
        label=_("Score at most"),
    )
    quality_score_min = django_filters.NumberFilter(
        field_name="quality_score",
        lookup_expr="gte",
        label=_("Score at least"),
    )

    class Meta:
        model = Product
        fields = [
            "status",
            "lifecycle_status",
            "verification_level",
            "origin_type",
            "featured",
            "category",
            "business",
        ]

    def filter_issue(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(quality_issues__contains=[value])
