from django.db.models import F, Q
from django.views.generic import DetailView, ListView

from products.models import Product

from .models import DirectoryListing, DirectoryPage


class DirectoryListingQuerysetMixin:
    """Shared queryset + search for directory listing views."""

    paginate_by = 24

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def get_queryset(self):
        qs = (
            DirectoryListing.objects.filter(
                show_in_directory=True,
                product__status=Product.ProductStatus.PUBLISHED,
            )
            .select_related(
                "product",
                "product__business",
                "product__category",
                "product__image",
            )
            .order_by("-featured", "product__name")
        )

        query = self.get_search_query()
        if query:
            qs = qs.filter(
                Q(product__name__icontains=query)
                | Q(product__brand_name__icontains=query)
                | Q(product__short_description__icontains=query)
                | Q(product__description__icontains=query)
                | Q(product__sku__icontains=query)
                | Q(product__business__name__icontains=query)
                | Q(product__category__name__icontains=query)
            ).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.get_search_query()
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
    model = DirectoryListing
    context_object_name = "listing"
    template_name = "directory/product_detail.html"
    slug_field = "product__slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return DirectoryListing.objects.filter(
            show_in_directory=True,
            product__status=Product.ProductStatus.PUBLISHED,
        ).select_related(
            "product",
            "product__business",
            "product__category",
            "product__image",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = self.object.product
        context["directory_page"] = DirectoryPage.objects.live().public().first()
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        DirectoryListing.objects.filter(pk=self.object.pk).update(views=F("views") + 1)
        self.object.refresh_from_db(fields=["views"])
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)
