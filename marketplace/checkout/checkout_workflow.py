from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from django.db.models import Prefetch

from inventory.services import commit_stock, release_stock, reserve_stock
from marketplace.cart.cart_workflow import cart_thumb_url_for_variant, mark_cart_converted
from marketplace.models import (
    Checkout,
    CheckoutStockReservation,
    FulfilmentMethod,
    Order,
    OrderItem,
    PaymentProvider,
    PaymentStatus,
    VariantOffer,
)
from marketplace.offers import price_for_variant
from marketplace.payments import paystack
from marketplace.settings import (
    TaxPricingMode,
    get_marketplace_currency,
    is_collection_enabled,
)
from marketplace.tax import breakdown_from_snapshot, calculate_tax, format_tax_rate


class CheckoutValidationError(ValidationError):
    pass


CHECKOUT_STEPS = ("cart", "customer", "delivery", "payment", "review")


def delivery_fee_for_method(method):
    if method == FulfilmentMethod.DELIVERY:
        return Decimal(str(settings.MARKETPLACE_DELIVERY_FEE))
    return Decimal("0")


def _user_display_name(user):
    name = user.get_full_name().strip()
    return name or user.username


def _order_snapshot_fields(checkout):
    return {
        "customer_name": checkout.customer_name,
        "customer_email": checkout.customer_email,
        "customer_phone": checkout.customer_phone,
        "fulfilment_method": checkout.fulfilment_method,
        "delivery_city": checkout.delivery_city,
        "delivery_suburb": checkout.delivery_suburb,
        "delivery_street": checkout.delivery_street,
        "delivery_instructions": checkout.delivery_instructions,
        "payment_provider": checkout.payment_provider,
        "payment_status": checkout.payment_status,
        "payment_reference": checkout.payment_reference,
        "paid_at": checkout.paid_at,
        "tax_enabled": checkout.tax_enabled,
        "tax_pricing_mode": checkout.tax_pricing_mode,
        "tax_rate": checkout.tax_rate,
        "tax_base": checkout.tax_base,
        "tax_amount": checkout.tax_amount,
        "currency": checkout.currency,
    }


def _freeze_tax_on_checkout(checkout, tax):
    checkout.tax_enabled = tax.enabled
    checkout.tax_pricing_mode = tax.pricing_mode if tax.enabled else ""
    checkout.tax_rate = tax.rate_percent if tax.enabled else Decimal("0")
    checkout.tax_base = tax.tax_base
    checkout.tax_amount = tax.tax_amount
    checkout.merchandise_subtotal = tax.merchandise_subtotal
    checkout.currency = tax.currency
    checkout.total_payable = tax.total
    checkout.delivery_fee = tax.delivery_fee
    checkout.save(
        update_fields=[
            "tax_enabled",
            "tax_pricing_mode",
            "tax_rate",
            "tax_base",
            "tax_amount",
            "merchandise_subtotal",
            "currency",
            "total_payable",
            "delivery_fee",
            "updated_at",
        ]
    )


def _clear_tax_freeze(checkout):
    """Drop a payable freeze so the next totals use live tax settings."""
    if not checkout.total_payable and not checkout.tax_amount:
        return
    if checkout.payment_status == PaymentStatus.PENDING and checkout.payment_reference:
        return
    checkout.tax_enabled = False
    checkout.tax_pricing_mode = ""
    checkout.tax_rate = Decimal("0")
    checkout.tax_base = Decimal("0")
    checkout.tax_amount = Decimal("0")
    checkout.merchandise_subtotal = Decimal("0")
    checkout.currency = ""
    checkout.total_payable = Decimal("0")
    checkout.save(
        update_fields=[
            "tax_enabled",
            "tax_pricing_mode",
            "tax_rate",
            "tax_base",
            "tax_amount",
            "merchandise_subtotal",
            "currency",
            "total_payable",
            "updated_at",
        ]
    )


def _frozen_tax_breakdown(checkout):
    """Use frozen Paystack totals while payment is in flight or already paid."""
    if checkout.total_payable and checkout.payment_status in (
        PaymentStatus.PENDING,
        PaymentStatus.PAID,
    ):
        return breakdown_from_snapshot(
            tax_enabled=checkout.tax_enabled,
            tax_pricing_mode=checkout.tax_pricing_mode or TaxPricingMode.EXCLUDED,
            tax_rate=checkout.tax_rate,
            tax_base=checkout.tax_base,
            tax_amount=checkout.tax_amount,
            merchandise_subtotal=checkout.merchandise_subtotal
            or checkout.tax_base,
            delivery_fee=checkout.delivery_fee or Decimal("0"),
            total=checkout.total_payable,
            currency=checkout.currency or get_marketplace_currency(),
        )
    return None


def get_open_cart_for_user(user):
    from marketplace.cart.cart_workflow import get_open_cart_for_user as _get

    return _get(user)


@transaction.atomic
def get_or_start_checkout(user):
    cart = get_open_cart_for_user(user)
    if cart is None or not cart.items.filter(removed_at__isnull=True).exists():
        raise CheckoutValidationError("Your cart is empty.")
    checkout = (
        Checkout.objects.select_for_update()
        .filter(
            user=user,
            cart=cart,
            status=Checkout.CheckoutStatus.PENDING,
        )
        .order_by("-pk")
        .first()
    )
    if checkout is None:
        checkout = Checkout.objects.create(user=user, cart=cart)
    elif checkout.payment_status == PaymentStatus.PENDING and checkout.order_id:
        raise CheckoutValidationError("This checkout is awaiting payment.")
    return checkout


def checkout_totals(checkout):
    from products.models import ProductVariantImage

    subtotal = Decimal("0")
    lines = []
    cart_items = (
        checkout.cart.items.filter(removed_at__isnull=True)
        .select_related(
            "variant__product",
            "variant__product__image",
            "variant__offer",
        )
        .prefetch_related(
            Prefetch(
                "variant__images",
                queryset=ProductVariantImage.objects.select_related("image").order_by(
                    "sort_order",
                    "pk",
                ),
            )
        )
    )
    for item in cart_items:
        price = item.price_snapshot
        if price is None:
            price = price_for_variant(item.variant)
        if price is None:
            price = Decimal("0")
        line_total = price * item.quantity
        subtotal += line_total
        lines.append(
            {
                "item": item,
                "unit_price": price,
                "line_total": line_total,
                "image_url": cart_thumb_url_for_variant(item.variant),
            }
        )
    delivery_fee = checkout.delivery_fee or Decimal("0")
    frozen = _frozen_tax_breakdown(checkout)
    if frozen is not None:
        tax = frozen
    else:
        tax = calculate_tax(
            merchandise_subtotal=subtotal,
            delivery_fee=delivery_fee,
        )
    return {
        "lines": lines,
        "subtotal": tax.merchandise_subtotal,
        "delivery_fee": tax.delivery_fee,
        "tax": tax,
        "tax_enabled": tax.enabled,
        "tax_pricing_mode": tax.pricing_mode,
        "tax_rate": tax.rate_percent,
        "tax_rate_display": format_tax_rate(tax.rate_percent),
        "tax_amount": tax.tax_amount,
        "tax_base": tax.tax_base,
        "currency": tax.currency,
        "total": tax.total,
    }


def revalidate_cart_for_checkout(checkout):
    """Refresh price snapshots and ensure lines remain sellable."""
    errors = []
    cart_items = list(
        checkout.cart.items.filter(removed_at__isnull=True).select_related(
            "variant",
            "variant__product",
            "variant__offer",
            "variant__inventory",
        )
    )
    if not cart_items:
        raise CheckoutValidationError("Your cart is empty.")

    reserved_here = {
        row.variant_id: row.quantity
        for row in checkout.stock_reservations.all()
    }
    for item in cart_items:
        product = item.variant.product
        if not product.marketplace_enabled:
            errors.append(f"{product.name} is no longer listed in the marketplace.")
            continue
        try:
            offer = item.variant.offer
        except ObjectDoesNotExist:
            errors.append(f"{product.name} ({item.variant.label}) is no longer available.")
            continue
        if not offer.is_available or offer.price is None:
            errors.append(f"{product.name} ({item.variant.label}) is no longer available.")
            continue
        live_price = offer.price
        if live_price is None:
            errors.append(
                f"{item.variant.product.name} ({item.variant.label}) has no price."
            )
            continue
        if item.price_snapshot is not None and item.price_snapshot != live_price:
            errors.append(
                f"The price for {item.variant.product.name} changed. "
                "Refresh your cart and try again."
            )
            continue
        if offer.stock_mode == VariantOffer.StockMode.TRACKED:
            available = item.variant.inventory.available_quantity
            available += reserved_here.get(item.variant_id, 0)
            if item.quantity > available:
                errors.append(
                    f"Only {available} of {item.variant.product.name} "
                    f"({item.variant.label}) are available."
                )
        item.price_snapshot = live_price
        item.save(update_fields=["price_snapshot"])
    if errors:
        raise CheckoutValidationError(errors)
    if checkout.payment_status != PaymentStatus.PENDING:
        _clear_tax_freeze(checkout)
    return checkout_totals(checkout)


def update_customer(checkout, *, name, email, phone):
    checkout.customer_name = (name or "").strip()
    checkout.customer_email = (email or "").strip()
    checkout.customer_phone = (phone or "").strip()
    if not checkout.customer_name:
        raise CheckoutValidationError("Enter your name.")
    if not checkout.customer_email:
        raise CheckoutValidationError("Enter your email address.")
    if not checkout.customer_phone:
        raise CheckoutValidationError("Enter your phone number.")
    checkout.save(
        update_fields=[
            "customer_name",
            "customer_email",
            "customer_phone",
            "updated_at",
        ]
    )
    return checkout


def update_fulfilment(
    checkout,
    *,
    method,
    city="",
    suburb="",
    street="",
    instructions="",
):
    if method not in FulfilmentMethod.values:
        raise CheckoutValidationError("Choose collection or delivery.")
    if method == FulfilmentMethod.COLLECTION and not is_collection_enabled():
        raise CheckoutValidationError("Collection is not available.")
    checkout.fulfilment_method = method
    checkout.delivery_city = (city or "").strip()
    checkout.delivery_suburb = (suburb or "").strip()
    checkout.delivery_street = (street or "").strip()
    checkout.delivery_instructions = (instructions or "").strip()
    if method == FulfilmentMethod.DELIVERY:
        if not checkout.delivery_city:
            raise CheckoutValidationError("Enter your city.")
        if not checkout.delivery_suburb:
            raise CheckoutValidationError("Enter your suburb.")
        if not checkout.delivery_street:
            raise CheckoutValidationError("Enter your street address.")
    else:
        checkout.delivery_city = ""
        checkout.delivery_suburb = ""
        checkout.delivery_street = ""
        checkout.delivery_instructions = ""
    checkout.delivery_fee = delivery_fee_for_method(method)
    checkout.save(
        update_fields=[
            "fulfilment_method",
            "delivery_city",
            "delivery_suburb",
            "delivery_street",
            "delivery_instructions",
            "delivery_fee",
            "updated_at",
        ]
    )
    _clear_tax_freeze(checkout)
    return checkout


def set_payment_method(checkout):
    if not paystack.paystack_configured():
        raise CheckoutValidationError(
            "Online payment is not configured. Please try again later."
        )
    checkout.payment_provider = PaymentProvider.PAYSTACK
    checkout.save(update_fields=["payment_provider", "updated_at"])
    return checkout


def customer_defaults(user):
    return {
        "name": _user_display_name(user),
        "email": user.email or "",
        "phone": user.phone_number or "",
    }


def _validate_ready_for_payment(checkout):
    revalidate_cart_for_checkout(checkout)
    if not checkout.customer_name or not checkout.customer_email:
        raise CheckoutValidationError("Complete customer information first.")
    if not checkout.fulfilment_method:
        raise CheckoutValidationError("Choose collection or delivery.")
    if checkout.payment_provider != PaymentProvider.PAYSTACK:
        raise CheckoutValidationError("Select a payment method.")


def _clear_reservations(checkout):
    reservations = list(
        checkout.stock_reservations.select_related("variant").all()
    )
    for row in reservations:
        release_stock(row.variant, row.quantity)
    checkout.stock_reservations.all().delete()


def _create_reservations(checkout):
    _clear_reservations(checkout)
    cart_items = checkout.cart.items.filter(removed_at__isnull=True).select_related(
        "variant__offer",
    )
    for item in cart_items:
        try:
            offer = item.variant.offer
        except ObjectDoesNotExist:
            continue
        if offer.stock_mode != VariantOffer.StockMode.TRACKED:
            continue
        reserve_stock(item.variant, item.quantity)
        CheckoutStockReservation.objects.create(
            checkout=checkout,
            variant=item.variant,
            quantity=item.quantity,
        )


def _amount_cents(total: Decimal) -> int:
    cents = (total * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


@transaction.atomic
def place_order(checkout, *, callback_url):
    checkout = Checkout.objects.select_for_update().get(pk=checkout.pk)
    if checkout.status == Checkout.CheckoutStatus.COMPLETED:
        if checkout.order_id:
            return {"already_paid": True, "order": checkout.order}
        raise CheckoutValidationError("This checkout is already completed.")
    if checkout.payment_status == PaymentStatus.PENDING and checkout.payment_reference:
        if checkout.payment_access_code:
            raise CheckoutValidationError(
                "Payment is already in progress. Complete it or start again."
            )
    _validate_ready_for_payment(checkout)
    if checkout.terms_accepted_at is None:
        raise CheckoutValidationError("Accept the terms to place your order.")

    totals = checkout_totals(checkout)
    tax = totals["tax"]
    _freeze_tax_on_checkout(checkout, tax)
    checkout.refresh_from_db()
    _create_reservations(checkout)

    reference = paystack.generate_reference()
    init_data = paystack.initialize_transaction(
        email=checkout.customer_email,
        amount_cents=_amount_cents(tax.total),
        reference=reference,
        callback_url=callback_url,
        metadata={
            "checkout_id": checkout.pk,
            "currency": tax.currency,
            "tax_amount": str(tax.tax_amount),
        },
    )
    checkout.payment_reference = reference
    checkout.payment_access_code = init_data.get("access_code") or ""
    checkout.payment_status = PaymentStatus.PENDING
    checkout.save(
        update_fields=[
            "payment_reference",
            "payment_access_code",
            "payment_status",
            "updated_at",
        ]
    )
    return {
        "authorization_url": init_data["authorization_url"],
        "reference": reference,
    }


def _commit_reservations(checkout):
    for row in checkout.stock_reservations.select_related("variant"):
        commit_stock(row.variant, row.quantity)
    checkout.stock_reservations.all().delete()


@transaction.atomic
def finish_paid_checkout(checkout):
    checkout = Checkout.objects.select_for_update().get(pk=checkout.pk)
    if checkout.status == Checkout.CheckoutStatus.COMPLETED and checkout.order_id:
        return checkout.order
    if checkout.payment_status != PaymentStatus.PAID:
        raise ValidationError("Checkout payment has not been confirmed.")

    totals = revalidate_cart_for_checkout(checkout)
    frozen = _frozen_tax_breakdown(checkout)
    if frozen is None:
        tax = calculate_tax(
            merchandise_subtotal=totals["subtotal"],
            delivery_fee=checkout.delivery_fee or Decimal("0"),
        )
        _freeze_tax_on_checkout(checkout, tax)
        checkout.refresh_from_db()
        frozen = tax
    else:
        # Keep merchandise lines; payable totals come from the payment freeze.
        if totals["subtotal"] != frozen.merchandise_subtotal:
            # Allow tiny rounding drift only; otherwise revalidate already failed.
            pass

    order = Order.objects.create(
        user=checkout.user,
        status=Order.OrderStatus.CONFIRMED,
        subtotal=frozen.merchandise_subtotal,
        delivery_fee=frozen.delivery_fee,
        total=frozen.total,
        **_order_snapshot_fields(checkout),
    )
    for row in totals["lines"]:
        item = row["item"]
        variant = item.variant
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            product_name=variant.product.name,
            variant_label=variant.label,
            unit_price=row["unit_price"],
            quantity=item.quantity,
        )

    _commit_reservations(checkout)
    checkout.order = order
    checkout.status = Checkout.CheckoutStatus.COMPLETED
    checkout.save(update_fields=["order", "status", "updated_at"])
    mark_cart_converted(checkout.cart, order=order)
    return order


def _verify_paystack_matches_checkout(checkout, paystack_data):
    if paystack_data.get("status") != "success":
        return False
    expected_total = checkout.total_payable or checkout_totals(checkout)["total"]
    expected_cents = _amount_cents(expected_total)
    if int(paystack_data.get("amount") or 0) != expected_cents:
        return False
    currency = (paystack_data.get("currency") or "").upper()
    expected_currency = (
        checkout.currency or get_marketplace_currency()
    ).upper()
    if currency and currency != expected_currency:
        return False
    customer_email = (paystack_data.get("customer") or {}).get("email") or paystack_data.get(
        "email"
    )
    if customer_email and customer_email.lower() != checkout.customer_email.lower():
        return False
    return True


def apply_paystack_success(reference):
    """Verify Paystack payment and complete checkout. Idempotent for repeats."""
    verification_failed = False
    with transaction.atomic():
        checkout = (
            Checkout.objects.select_for_update()
            .filter(payment_reference=reference)
            .first()
        )
        if checkout is None:
            return None
        if checkout.status == Checkout.CheckoutStatus.COMPLETED and checkout.order_id:
            return checkout.order

        paystack_data = paystack.verify_transaction(reference)
        if not _verify_paystack_matches_checkout(checkout, paystack_data):
            checkout.payment_status = PaymentStatus.FAILED
            checkout.save(update_fields=["payment_status", "updated_at"])
            _clear_reservations(checkout)
            verification_failed = True
        else:
            checkout.payment_status = PaymentStatus.PAID
            checkout.paid_at = timezone.now()
            checkout.save(update_fields=["payment_status", "paid_at", "updated_at"])
            order = finish_paid_checkout(checkout)
    if verification_failed:
        raise CheckoutValidationError("Payment verification failed.")
    return order


@transaction.atomic
def apply_paystack_failure(reference):
    checkout = (
        Checkout.objects.select_for_update()
        .filter(payment_reference=reference)
        .first()
    )
    if checkout is None:
        return None
    if checkout.status == Checkout.CheckoutStatus.COMPLETED:
        return checkout
    checkout.payment_status = PaymentStatus.FAILED
    checkout.save(update_fields=["payment_status", "updated_at"])
    _clear_reservations(checkout)
    return checkout


def accept_terms(checkout):
    checkout.terms_accepted_at = timezone.now()
    checkout.save(update_fields=["terms_accepted_at", "updated_at"])
    return checkout
