from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from businesses.models import Business
from businesses.verification import VerificationLevel, level_legend
from businesses.verification_dashboard import (
    business_level_counts,
    business_tier_counts,
    flagged_businesses,
    flagged_products,
    freshness_legend,
    level_count_rows,
    open_reports,
    product_level_counts,
    product_tier_counts,
    tier_count_rows,
)
from businesses.verification_workflow import (
    owner_confirm_business,
    owner_confirm_products,
    owner_listings,
    staff_set_level,
    verification_exceptions,
)
from products.models import Product

from .forms import (
    MemberLoginForm,
    MemberPasswordChangeForm,
    MemberPasswordResetForm,
    MemberSetPasswordForm,
    MemberSignUpForm,
)

class MemberLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = MemberLoginForm
    redirect_authenticated_user = True


class MemberLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class MemberSignUpView(FormView):
    template_name = "accounts/signup.html"
    form_class = MemberSignUpForm
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self.redirect_authenticated_user()
        return super().dispatch(request, *args, **kwargs)

    def redirect_authenticated_user(self):
        from django.shortcuts import redirect

        return redirect(self.success_url)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class MemberPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    form_class = MemberPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")


class MemberPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class MemberPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = MemberSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class MemberPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class MemberPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    form_class = MemberPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")


class MemberPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["display_name"] = (
            user.get_full_name() or user.get_username()
        )
        context["order_count"] = user.orders.count()

        listings = owner_listings(user)
        context["owner_listings"] = listings
        context["owner_action_count"] = sum(1 for row in listings if row["needs_action"])

        if user.is_staff:
            context["verification_level_legend"] = level_legend()
            context["verification_level_choices"] = level_legend()
            context["verification_legend"] = freshness_legend()
            context["business_level_rows"] = level_count_rows(
                business_level_counts(),
            )
            context["product_level_rows"] = level_count_rows(
                product_level_counts(),
            )
            business_counts = business_tier_counts()
            product_counts = product_tier_counts()
            context["business_tier_rows"] = tier_count_rows(business_counts)
            context["product_tier_rows"] = tier_count_rows(product_counts)
            context["flagged_businesses"] = flagged_businesses()
            context["flagged_products"] = flagged_products()
            context["open_reports"] = open_reports()
            exceptions = verification_exceptions()
            context["verification_exceptions"] = exceptions
            context["verification_attention_count"] = len(exceptions)

        return context


class OwnerConfirmView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        kind = request.POST.get("kind", "").strip()
        business = get_object_or_404(
            Business,
            pk=request.POST.get("business"),
            owner=request.user,
        )
        if kind == "business":
            owner_confirm_business(business, request.user)
            messages.success(request, f'Thanks — "{business.name}" is confirmed as accurate.')
        elif kind == "products":
            count = owner_confirm_products(business, request.user)
            messages.success(request, f"Confirmed {count} product{'s' if count != 1 else ''} as accurate.")
        elif kind == "all":
            owner_confirm_business(business, request.user)
            count = owner_confirm_products(business, request.user)
            messages.success(
                request,
                f'Confirmed "{business.name}" and {count} product{"s" if count != 1 else ""}.',
            )
        elif kind == "product":
            product = get_object_or_404(
                Product,
                pk=request.POST.get("pk"),
                business=business,
            )
            owner_confirm_products(
                business,
                request.user,
                Product.objects.filter(pk=product.pk),
            )
            messages.success(request, f'Confirmed "{product.name}" as accurate.')
        else:
            messages.error(request, "Unknown listing type.")
        return redirect(reverse("accounts:dashboard") + "#my-listings")


class VerifyListingView(LoginRequiredMixin, UserPassesTestMixin, View):
    http_method_names = ["post"]

    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        kind = request.POST.get("kind", "").strip()
        pk = request.POST.get("pk")
        level = request.POST.get("level", "").strip()
        reference = request.POST.get("reference", "").strip()

        valid_levels = {choice.value for choice in VerificationLevel}
        if level not in valid_levels:
            messages.error(request, "Choose a valid verification level.")
            return redirect(reverse("accounts:dashboard") + "#verification")

        if kind == "business":
            business = get_object_or_404(Business, pk=pk)
            staff_set_level(business, request.user, level, reference)
            messages.success(
                request,
                f'Set "{business.name}" to {business.get_verification_level_display()}.',
            )
        elif kind == "product":
            product = get_object_or_404(Product, pk=pk)
            staff_set_level(product, request.user, level, reference)
            messages.success(
                request,
                f'Set "{product.name}" to {product.get_verification_level_display()}.',
            )
        else:
            messages.error(request, "Unknown listing type.")
            return redirect(reverse("accounts:dashboard") + "#verification")

        return redirect(reverse("accounts:dashboard") + "#verification")
