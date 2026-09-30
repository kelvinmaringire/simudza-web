from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from businesses.models import Business
from businesses.verification_workflow import notify_owner_of_report
from products.models import Product

from .forms_public import ListingReportForm
from .models import BusinessReview, ProductReview, ReportStatus

REPORT_LIMIT = 5
REPORT_WINDOW_SECONDS = 3600


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _throttle_key(kind, listing_pk, ip):
    return f"listing-report:{kind}:{listing_pk}:{ip}"


def _is_throttled(request, kind, listing_pk):
    ip = _client_ip(request) or "unknown"
    key = _throttle_key(kind, listing_pk, ip)
    count = cache.get(key, 0)
    return count >= REPORT_LIMIT


def _record_throttle(request, kind, listing_pk):
    ip = _client_ip(request) or "unknown"
    key = _throttle_key(kind, listing_pk, ip)
    count = cache.get(key, 0)
    cache.set(key, count + 1, REPORT_WINDOW_SECONDS)


class ReportProductView(View):
    http_method_names = ["post"]

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        form = ListingReportForm(request.POST, kind="product")
        if form.is_honeypot_triggered():
            return self._success(request, product.get_absolute_url())

        if _is_throttled(request, "product", product.pk):
            return self._success(request, product.get_absolute_url())

        if not form.is_valid():
            return self._error(request, product.get_absolute_url())

        _record_throttle(request, "product", product.pk)
        report = ProductReview.objects.create(
            product=product,
            user=request.user if request.user.is_authenticated else None,
            reason=form.cleaned_data["reason"],
            body=form.cleaned_data.get("details") or "",
            status=ReportStatus.OPEN,
            guest_name=form.cleaned_data.get("guest_name") or "",
            guest_email=form.cleaned_data.get("guest_email") or "",
            ip_address=_client_ip(request),
            is_published=False,
            rating=None,
        )
        notify_owner_of_report(report)
        return self._success(request, product.get_absolute_url())

    def _success(self, request, redirect_url):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                render_thanks(),
                content_type="text/html; charset=utf-8",
            )
        return redirect(f"{redirect_url}?reported=1")

    def _error(self, request, redirect_url):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<p class="text-sm text-error">Please check your report and try again.</p>',
                status=400,
            )
        return redirect(redirect_url)


class ReportBusinessView(View):
    http_method_names = ["post"]

    def post(self, request, slug):
        business = get_object_or_404(Business, slug=slug)
        form = ListingReportForm(request.POST, kind="business")
        if form.is_honeypot_triggered():
            return self._success(request, business.get_absolute_url())

        if _is_throttled(request, "business", business.pk):
            return self._success(request, business.get_absolute_url())

        if not form.is_valid():
            return self._error(request, business.get_absolute_url())

        _record_throttle(request, "business", business.pk)
        report = BusinessReview.objects.create(
            business=business,
            user=request.user if request.user.is_authenticated else None,
            reason=form.cleaned_data["reason"],
            body=form.cleaned_data.get("details") or "",
            status=ReportStatus.OPEN,
            guest_name=form.cleaned_data.get("guest_name") or "",
            guest_email=form.cleaned_data.get("guest_email") or "",
            ip_address=_client_ip(request),
            is_published=False,
            rating=None,
        )
        notify_owner_of_report(report)
        return self._success(request, business.get_absolute_url())

    def _success(self, request, redirect_url):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                render_thanks(),
                content_type="text/html; charset=utf-8",
            )
        return redirect(f"{redirect_url}?reported=1")

    def _error(self, request, redirect_url):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<p class="text-sm text-error">Please check your report and try again.</p>',
                status=400,
            )
        return redirect(redirect_url)


def render_thanks():
    from django.template.loader import render_to_string

    return render_to_string("reviews/partials/report_thanks.html")
