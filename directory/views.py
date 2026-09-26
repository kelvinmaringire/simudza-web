from django.db.models import F
from django.shortcuts import redirect
from django.views.generic import DetailView, ListView

from products.models import Product

from .filters import DirectoryListingFilter, build_directory_category_tree
from .models import DirectoryListing, DirectoryPage


FILTER_PARAM_NAMES = (
    "q",
    "category",
    "town_or_city",
    "origin_type",
    "verified",
)


class DirectoryListingQuerysetMixin:
    """Shared queryset + search/filters for directory listing views."""

    paginate_by = 24

    def get_filterset(self):
        if not hasattr(self, "_filterset"):
            self._filterset = DirectoryListingFilter(
                self.request.GET or None,
                queryset=self.get_base_queryset(),
            )
        return self._filterset

    def get_base_queryset(self):
        return (
            DirectoryListing.objects.filter(
                show_in_directory=True,
                product__status=Product.ProductStatus.PUBLISHED,
            )
            .select_related(
                "product",
                "product__business",
                "product__category",
                "product__image",
                "product__inventory",
            )
            .order_by("-featured", "product__name")
        )

    def get_queryset(self):
        return self.get_filterset().qs.distinct()

    def get_filter_querystring(self):
        params = self.request.GET.copy()
        params.pop("page", None)
        return params.urlencode()

    def get_selected_category_id(self):
        return self.request.GET.get("category", "")

    def filters_are_active(self):
        for name in FILTER_PARAM_NAMES:
            if self.request.GET.get(name, "").strip():
                return True
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filterset = self.get_filterset()
        selected_category = self.get_selected_category_id()
        context["filterset"] = filterset
        context["q"] = (filterset.data.get("q") or "").strip() if filterset.data else ""
        context["filter_qs"] = self.get_filter_querystring()
        context["selected_category"] = selected_category
        context["category_tree"] = build_directory_category_tree(selected_category)
        context["filters_active"] = self.filters_are_active()
        context["directory_page"] = DirectoryPage.objects.live().public().first()
        return context


class DirectoryIndexView(DirectoryListingQuerysetMixin, ListView):
    model = DirectoryListing
    context_object_name = "listings"
    template_name = "directory/directory_page.html"


class DirectoryResultsView(DirectoryListingQuerysetMixin, ListView):
    """HTMX partial: listing rows only."""

    model = DirectoryListing
    context_object_name = "listings"
    template_name = "directory/partials/listing_results.html"


class DirectoryProductDetailView(DetailView):
    """Legacy URL: count a directory view, then open the product page."""

    model = DirectoryListing
    slug_field = "product__slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return DirectoryListing.objects.filter(
            show_in_directory=True,
            product__status=Product.ProductStatus.PUBLISHED,
        ).select_related("product")

    def get(self, request, *args, **kwargs):
        listing = self.get_object()
        DirectoryListing.objects.filter(pk=listing.pk).update(views=F("views") + 1)
        return redirect("products:detail", slug=listing.product.slug)
