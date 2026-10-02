import django_filters
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import WagtailFilterSet

from .models import Business
from .quality import ISSUE_LABELS


class BusinessQualityFilterSet(WagtailFilterSet):
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
        model = Business
        fields = [
            "business_type",
            "verification_level",
            "is_active",
        ]

    def filter_issue(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(quality_issues__contains=[value])
