from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin

from businesses.quality import ISSUE_LABELS as BUSINESS_ISSUE_LABELS
from businesses.quality import issue_counts as business_issue_counts
from businesses.quality import score_band_counts as business_score_bands
from categories.quality import ISSUE_LABELS as CATEGORY_ISSUE_LABELS
from categories.quality import issue_counts as category_issue_counts
from categories.quality import needing_attention_count as categories_needing_attention
from products.quality import ISSUE_LABELS as PRODUCT_ISSUE_LABELS
from products.quality import issue_counts as product_issue_counts
from products.quality import score_band_counts as product_score_bands


def user_can_view_data_quality(user):
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    perms = user.get_all_permissions()
    return (
        "products.view_product" in perms or "businesses.view_business" in perms
    )


SCORE_BANDS = (
    ("0_3", "0–3", "low", {"quality_score_max": 3}),
    ("4_6", "4–6", "mid", {"quality_score_min": 4, "quality_score_max": 6}),
    ("7_8", "7–8", "good", {"quality_score_min": 7, "quality_score_max": 8}),
    ("9_10", "9–10", "high", {"quality_score_min": 9}),
)


def _issue_cards(labels, counts, index_url):
    """Issues with at least one match, linked to the filtered admin listing."""
    return [
        {
            "label": label,
            "count": counts[code],
            "url": f"{index_url}?{urlencode({'issue': code})}",
        }
        for code, label in labels.items()
        if counts.get(code, 0) > 0
    ]


def _score_band_cards(band_counts, index_url):
    return [
        {
            "label": label,
            "tone": tone,
            "count": band_counts.get(key, 0),
            "url": f"{index_url}?{urlencode(params)}",
        }
        for key, label, tone, params in SCORE_BANDS
    ]


class DataQualityIndexView(WagtailAdminTemplateMixin, TemplateView):
    template_name = "admin_data_quality/index.html"
    page_title = _("Data quality")

    def dispatch(self, request, *args, **kwargs):
        if not user_can_view_data_quality(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_url = reverse("product:index")
        business_url = reverse("business:index")
        category_url = reverse("category:index")
        context.update(
            {
                "product_issues": _issue_cards(
                    PRODUCT_ISSUE_LABELS, product_issue_counts(), product_url
                ),
                "business_issues": _issue_cards(
                    BUSINESS_ISSUE_LABELS, business_issue_counts(), business_url
                ),
                "category_issues": _issue_cards(
                    CATEGORY_ISSUE_LABELS, category_issue_counts(), category_url
                ),
                "product_score_bands": _score_band_cards(
                    product_score_bands(), product_url
                ),
                "business_score_bands": _score_band_cards(
                    business_score_bands(), business_url
                ),
                "categories_needing_attention": categories_needing_attention(),
                "categories_needing_attention_url": (
                    f"{category_url}?{urlencode({'needs_attention': 'yes'})}"
                ),
            }
        )
        return context
