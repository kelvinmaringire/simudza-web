import json

from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from products.models import Product

from .models import MarketplacePage
from .services import (
    filter_marketplace_products,
    get_marketplace_products,
    sync_user_cart,
)


class MarketplaceProductQuerysetMixin:
    paginate_by = 24

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def get_queryset(self):
        qs = get_marketplace_products()
        return filter_marketplace_products(qs, self.get_search_query())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.get_search_query()
        context["marketplace_page"] = MarketplacePage.objects.live().public().first()
        return context


class MarketplaceIndexView(MarketplaceProductQuerysetMixin, ListView):
    model = Product
    context_object_name = "products"
    template_name = "marketplace/marketplace_page.html"


class MarketplaceResultsView(MarketplaceProductQuerysetMixin, ListView):
    model = Product
    context_object_name = "products"
    template_name = "marketplace/partials/product_results.html"


def _parse_sync_payload(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
        return data.get("items") or []

    raw = request.POST.get("payload", "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data.get("items") or []


@require_POST
def cart_sync(request):
    """Silent backend cart store driven by client localStorage. No UI payload."""
    if not request.user.is_authenticated:
        return HttpResponse(status=204)

    items = _parse_sync_payload(request)
    if not isinstance(items, list):
        return HttpResponse(status=400)

    sync_user_cart(request.user, items)
    return HttpResponse(status=204)
