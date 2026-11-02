import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from marketplace.checkout.checkout_forms import (
    CustomerCheckoutForm,
    FulfilmentCheckoutForm,
    PaymentCheckoutForm,
    ReviewCheckoutForm,
)
from marketplace.checkout.checkout_workflow import (
    CHECKOUT_STEPS,
    CheckoutValidationError,
    accept_terms,
    apply_paystack_failure,
    apply_paystack_success,
    customer_defaults,
    get_or_start_checkout,
    checkout_totals,
    place_order,
    revalidate_cart_for_checkout,
    set_payment_method,
    update_customer,
    update_fulfilment,
)
from marketplace.models import FulfilmentMethod, Order, PaymentStatus
from marketplace.payments import paystack
from marketplace.settings import (
    currency_symbol,
    get_marketplace_currency,
    is_collection_enabled,
)

logger = logging.getLogger(__name__)

STEP_LABELS = {
    "cart": "Cart",
    "customer": "Details",
    "delivery": "Delivery",
    "payment": "Payment",
    "review": "Review",
}

STEP_TEMPLATES = {
    "cart": "marketplace/checkout/step_cart.html",
    "customer": "marketplace/checkout/step_customer.html",
    "delivery": "marketplace/checkout/step_delivery.html",
    "payment": "marketplace/checkout/step_payment.html",
    "review": "marketplace/checkout/step_review.html",
}


def _step_index(step):
    try:
        return CHECKOUT_STEPS.index(step)
    except ValueError:
        return 0


def _default_fulfilment_method(checkout):
    method = checkout.fulfilment_method
    if method == FulfilmentMethod.COLLECTION and not is_collection_enabled():
        return FulfilmentMethod.DELIVERY
    if method:
        return method
    if is_collection_enabled():
        return FulfilmentMethod.COLLECTION
    return FulfilmentMethod.DELIVERY


def _checkout_context(request, checkout, step, *, form=None, extra=None):
    totals = checkout_totals(checkout)
    ctx = {
        "checkout": checkout,
        "step": step,
        "step_labels": STEP_LABELS,
        "step_index": _step_index(step),
        "checkout_steps": CHECKOUT_STEPS,
        "step_nav": [(key, STEP_LABELS[key]) for key in CHECKOUT_STEPS],
        "totals": totals,
        "paystack_configured": paystack.paystack_configured(),
        "paystack_public_key": settings.PAYSTACK_PUBLIC_KEY,
        "form": form,
        "marketplace_url": reverse("marketplace:index"),
        "currency_code": get_marketplace_currency(),
        "currency_symbol": currency_symbol(),
        "collection_enabled": is_collection_enabled(),
    }
    if extra:
        ctx.update(extra)
    return ctx


class CheckoutEntryView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request):
        return redirect("marketplace:checkout_step", step="cart")


class CheckoutStepView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request, step):
        if step not in CHECKOUT_STEPS:
            return redirect("marketplace:checkout_step", step="cart")
        try:
            checkout = get_or_start_checkout(request.user)
        except CheckoutValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
            return redirect("marketplace:index")

        form = None
        if step == "customer":
            form = CustomerCheckoutForm(
                initial=customer_defaults(request.user)
                if not checkout.customer_name
                else {
                    "customer_name": checkout.customer_name,
                    "customer_email": checkout.customer_email,
                    "customer_phone": checkout.customer_phone,
                }
            )
        elif step == "delivery":
            form = FulfilmentCheckoutForm(
                collection_enabled=is_collection_enabled(),
                initial={
                    "fulfilment_method": _default_fulfilment_method(checkout),
                    "delivery_city": checkout.delivery_city,
                    "delivery_suburb": checkout.delivery_suburb,
                    "delivery_street": checkout.delivery_street,
                    "delivery_instructions": checkout.delivery_instructions,
                },
            )
        elif step == "payment":
            form = PaymentCheckoutForm()
        elif step == "review":
            form = ReviewCheckoutForm()

        return render(
            request,
            "marketplace/checkout/base_checkout.html",
            _checkout_context(
                request,
                checkout,
                step,
                form=form,
                extra={"inner_template": STEP_TEMPLATES[step]},
            ),
        )

    def post(self, request, step):
        if step not in CHECKOUT_STEPS:
            return redirect("marketplace:checkout_step", step="cart")
        try:
            checkout = get_or_start_checkout(request.user)
        except CheckoutValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
            return redirect("marketplace:index")

        next_step = None
        try:
            if step == "cart":
                revalidate_cart_for_checkout(checkout)
                next_step = "customer"
            elif step == "customer":
                form = CustomerCheckoutForm(request.POST)
                if not form.is_valid():
                    return render(
                        request,
                        "marketplace/checkout/base_checkout.html",
                        _checkout_context(
                            request,
                            checkout,
                            step,
                            form=form,
                            extra={"inner_template": STEP_TEMPLATES[step]},
                        ),
                    )
                update_customer(
                    checkout,
                    name=form.cleaned_data["customer_name"],
                    email=form.cleaned_data["customer_email"],
                    phone=form.cleaned_data["customer_phone"],
                )
                next_step = "delivery"
            elif step == "delivery":
                form = FulfilmentCheckoutForm(
                    request.POST,
                    collection_enabled=is_collection_enabled(),
                )
                if not form.is_valid():
                    return render(
                        request,
                        "marketplace/checkout/base_checkout.html",
                        _checkout_context(
                            request,
                            checkout,
                            step,
                            form=form,
                            extra={"inner_template": STEP_TEMPLATES[step]},
                        ),
                    )
                update_fulfilment(
                    checkout,
                    method=form.cleaned_data["fulfilment_method"],
                    city=form.cleaned_data["delivery_city"],
                    suburb=form.cleaned_data["delivery_suburb"],
                    street=form.cleaned_data["delivery_street"],
                    instructions=form.cleaned_data["delivery_instructions"],
                )
                next_step = "payment"
            elif step == "payment":
                form = PaymentCheckoutForm(request.POST)
                if not form.is_valid():
                    return render(
                        request,
                        "marketplace/checkout/base_checkout.html",
                        _checkout_context(
                            request,
                            checkout,
                            step,
                            form=form,
                            extra={"inner_template": STEP_TEMPLATES[step]},
                        ),
                    )
                set_payment_method(checkout)
                next_step = "review"
            elif step == "review":
                form = ReviewCheckoutForm(request.POST)
                if not form.is_valid():
                    return render(
                        request,
                        "marketplace/checkout/base_checkout.html",
                        _checkout_context(
                            request,
                            checkout,
                            step,
                            form=form,
                            extra={"inner_template": STEP_TEMPLATES[step]},
                        ),
                    )
                accept_terms(checkout)
                callback_url = request.build_absolute_uri(
                    reverse("marketplace:checkout_payment_callback")
                )
                try:
                    result = place_order(checkout, callback_url=callback_url)
                except paystack.PaystackError as exc:
                    messages.error(
                        request,
                        str(exc)
                        or "Payment could not be started. Check the marketplace currency setting.",
                    )
                    return redirect("marketplace:checkout_step", step=step)
                if result.get("already_paid") and result.get("order"):
                    return redirect(
                        "marketplace:order_confirmation",
                        order_id=result["order"].pk,
                    )
                return redirect(result["authorization_url"])
        except CheckoutValidationError as exc:
            err = exc.messages[0] if exc.messages else str(exc)
            if isinstance(err, list):
                for message in err:
                    messages.error(request, message)
            else:
                messages.error(request, err)
            return redirect("marketplace:checkout_step", step=step)

        if request.POST.get("action") == "back":
            idx = _step_index(step)
            if idx > 0:
                return redirect(
                    "marketplace:checkout_step",
                    step=CHECKOUT_STEPS[idx - 1],
                )
            return redirect("marketplace:checkout_step", step="cart")

        if next_step:
            return redirect("marketplace:checkout_step", step=next_step)
        return redirect("marketplace:checkout_step", step=step)


class CheckoutPaymentCallbackView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request):
        reference = request.GET.get("reference", "").strip()
        if not reference:
            messages.error(request, "Payment reference missing.")
            return redirect("marketplace:checkout_step", step="payment")
        try:
            order = apply_paystack_success(reference)
        except CheckoutValidationError as exc:
            apply_paystack_failure(reference)
            messages.error(
                request,
                exc.messages[0] if exc.messages else "Payment could not be verified.",
            )
            return redirect("marketplace:checkout_step", step="review")
        except paystack.PaystackError:
            apply_paystack_failure(reference)
            messages.error(request, "Payment verification failed. Please try again.")
            return redirect("marketplace:checkout_step", step="review")
        if order is None:
            messages.error(request, "Checkout not found for this payment.")
            return redirect("marketplace:checkout_step", step="cart")
        return redirect("marketplace:order_confirmation", order_id=order.pk)


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(View):
    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        if not paystack.signature_valid(request.body, signature):
            return HttpResponse(status=403)
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return HttpResponseBadRequest("Invalid JSON")
        event = payload.get("event")
        data = payload.get("data") or {}
        reference = data.get("reference")
        if not reference:
            return HttpResponse(status=200)
        if event == "charge.success":
            try:
                apply_paystack_success(reference)
            except (CheckoutValidationError, paystack.PaystackError):
                logger.exception("Paystack webhook failed for %s", reference)
        elif event in ("charge.failed",):
            apply_paystack_failure(reference)
        return HttpResponse(status=200)


class OrderConfirmationView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.prefetch_related("items"),
            pk=order_id,
            user=request.user,
        )
        if order.payment_status != PaymentStatus.PAID:
            messages.warning(
                request,
                "This order has not been paid yet.",
            )
            return redirect("marketplace:index")
        return render(
            request,
            "marketplace/checkout/confirmation.html",
            {
                "order": order,
                "currency_code": get_marketplace_currency(),
                "currency_symbol": currency_symbol(),
            },
        )
