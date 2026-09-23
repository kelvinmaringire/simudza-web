from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
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
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from marketplace.models import Cart

from .forms import (
    MemberLoginForm,
    MemberPasswordChangeForm,
    MemberPasswordResetForm,
    MemberSetPasswordForm,
    MemberSignUpForm,
)

REMEMBER_ME_SECONDS = 60 * 60 * 24 * 30


class MemberLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = MemberLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = form.cleaned_data.get("remember_me")
        if remember_me:
            self.request.session.set_expiry(REMEMBER_ME_SECONDS)
        else:
            self.request.session.set_expiry(0)
        return super().form_valid(form)


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
        cart_item_count = 0
        try:
            cart_item_count = user.cart.item_count
        except Cart.DoesNotExist:
            pass

        context["display_name"] = (
            user.get_full_name() or user.get_username()
        )
        context["cart_item_count"] = cart_item_count
        context["order_count"] = user.orders.count()
        return context
