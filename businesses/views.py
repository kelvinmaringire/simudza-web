from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView

from products.models import Product

from .forms import (
    CompanySubmissionForm,
    ProductSubmissionForm,
    RetailLocationSubmissionForm,
)
from .models import Business, ManufacturerSubmission


FILTER_PARAM_NAMES = (
    "q",
    "business_type",
    "town_or_city",
    "verified",
)


class BusinessQuerysetMixin:
    """Shared queryset for public business profiles."""

    def get_base_queryset(self):
        published_products = Prefetch(
            "products",
            queryset=(
                Product.objects.filter(status=Product.ProductStatus.PUBLISHED)
                .select_related("category", "image")
                .order_by("name")
            ),
            to_attr="published_products",
        )
        return (
            Business.objects.filter(is_active=True)
            .exclude(slug="")
            .select_related("logo")
            .prefetch_related(
                published_products,
                "retail_locations",
            )
            .annotate(
                product_count=Count(
                    "products",
                    filter=Q(products__status=Product.ProductStatus.PUBLISHED),
                    distinct=True,
                )
            )
            .order_by("name")
        )


class BusinessListQuerysetMixin(BusinessQuerysetMixin):
    """Shared listing filters for companies index + HTMX results."""

    paginate_by = 24
    include_filter_facets = True

    def get_search_query(self):
        return (self.request.GET.get("q") or "").strip()

    def get_selected_business_type(self):
        return (self.request.GET.get("business_type") or "").strip()

    def get_selected_town(self):
        return (self.request.GET.get("town_or_city") or "").strip()

    def get_verified_only(self):
        return self.request.GET.get("verified") in {"1", "true", "on", "yes"}

    def filters_are_active(self):
        if self.get_verified_only():
            return True
        for name in FILTER_PARAM_NAMES:
            if name == "verified":
                continue
            if self.request.GET.get(name, "").strip():
                return True
        return False

    def get_filter_querystring(self):
        params = self.request.GET.copy()
        params.pop("page", None)
        return params.urlencode()

    def get_town_choices(self):
        return list(
            self.get_base_queryset()
            .exclude(town_or_city="")
            .values_list("town_or_city", flat=True)
            .distinct()
            .order_by("town_or_city")
        )

    def get_queryset(self):
        queryset = self.get_base_queryset()
        q = self.get_search_query()
        if len(q) >= 2:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(town_or_city__icontains=q)
                | Q(business_type__icontains=q)
            )

        business_type = self.get_selected_business_type()
        if business_type:
            queryset = queryset.filter(business_type=business_type)

        town = self.get_selected_town()
        if town:
            queryset = queryset.filter(town_or_city__iexact=town)

        if self.get_verified_only():
            queryset = queryset.filter(
                verification_status=Business.VerificationStatus.VERIFIED
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.get_search_query()
        context["filter_qs"] = self.get_filter_querystring()
        context["filters_active"] = self.filters_are_active()
        context["selected_business_type"] = self.get_selected_business_type()
        context["selected_town"] = self.get_selected_town()
        context["verified_only"] = self.get_verified_only()
        if self.include_filter_facets:
            context["business_types"] = Business.BusinessType.choices
            context["town_choices"] = self.get_town_choices()
        return context


class BusinessListView(BusinessListQuerysetMixin, ListView):
    model = Business
    context_object_name = "businesses"
    template_name = "businesses/business_list.html"


class BusinessResultsView(BusinessListQuerysetMixin, ListView):
    """HTMX partial: company cards only."""

    model = Business
    context_object_name = "businesses"
    template_name = "businesses/partials/business_results.html"
    include_filter_facets = False


class BusinessDetailView(BusinessQuerysetMixin, DetailView):
    model = Business
    context_object_name = "business"
    template_name = "businesses/business_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return self.get_base_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        products = getattr(self.object, "published_products", [])
        categories = []
        seen = set()
        for product in products:
            category = product.category
            if category is None or category.pk in seen:
                continue
            seen.add(category.pk)
            categories.append(category)
        categories.sort(key=lambda item: item.name.lower())
        context["products"] = products
        context["categories"] = categories
        context["retail_locations"] = [
            location
            for location in self.object.retail_locations.all()
            if location.is_active
        ]
        return context


class SubmissionHubView(LoginRequiredMixin, TemplateView):
    template_name = "businesses/submission_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["owned_businesses"] = Business.objects.filter(
            owner=user,
        ).order_by("name")
        context["submissions"] = ManufacturerSubmission.objects.filter(
            submitted_by=user,
        ).select_related("business", "product")[:20]
        context["owned_products"] = Product.objects.filter(
            business__owner=user,
        ).select_related("business", "category")[:50]
        return context


class CompanySubmitView(LoginRequiredMixin, FormView):
    template_name = "businesses/submit_company.html"
    form_class = CompanySubmissionForm
    success_url = reverse_lazy("businesses:submit")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        submission = form.save()
        if submission.status == ManufacturerSubmission.Status.APPLIED:
            messages.success(
                self.request,
                "Company profile saved and published on Simudza.",
            )
        else:
            messages.info(
                self.request,
                "Company submission received and is pending review.",
            )
        return super().form_valid(form)


class ProductSubmitView(LoginRequiredMixin, FormView):
    template_name = "businesses/submit_product.html"
    form_class = ProductSubmissionForm
    success_url = reverse_lazy("businesses:submit")

    def dispatch(self, request, *args, **kwargs):
        self.product = None
        product_id = kwargs.get("product_id")
        if product_id:
            self.product = get_object_or_404(
                Product,
                pk=product_id,
                business__owner=request.user,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["product"] = self.product
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = self.product
        return context

    def form_valid(self, form):
        submission = form.save()
        if submission.status == ManufacturerSubmission.Status.APPLIED:
            if submission.kind == ManufacturerSubmission.Kind.NEW_PRODUCT:
                messages.success(
                    self.request,
                    "Product submitted. It is pending review before it appears "
                    "in the directory.",
                )
            else:
                messages.success(
                    self.request,
                    "Product information updated.",
                )
        else:
            messages.info(
                self.request,
                "Product submission received and is pending review.",
            )
        return super().form_valid(form)


class RetailLocationSubmitView(LoginRequiredMixin, FormView):
    template_name = "businesses/submit_location.html"
    form_class = RetailLocationSubmissionForm
    success_url = reverse_lazy("businesses:submit")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        submission = form.save()
        if submission.status == ManufacturerSubmission.Status.APPLIED:
            messages.success(self.request, "Retail location saved.")
        else:
            messages.info(
                self.request,
                "Retail location submission received and is pending review.",
            )
        return super().form_valid(form)
