from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from marketplace.models import Cart, CartEvent, CartItem
from products.models import ProductVariant

MAX_CART_LINES = 100


def _sellable_variants_by_id(variant_ids):
    return {
        variant.pk: variant
        for variant in ProductVariant.objects.sellable()
        .filter(pk__in=variant_ids)
        .select_related("inventory", "product", "product__image")
    }


def _normalize_wanted_items(items, sellable):
    wanted = {}
    for item in items[:MAX_CART_LINES]:
        variant_id = item.get("variant_id")
        try:
            quantity = int(item.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        if variant_id not in sellable or quantity <= 0:
            continue
        available = sellable[variant_id].inventory.available_quantity
        wanted[variant_id] = min(quantity, available)
    return wanted


def get_open_cart_for_user(user):
    return Cart.objects.open().filter(user=user).first()


def get_or_create_open_cart(user, *, token=None):
    cart = get_open_cart_for_user(user)
    if cart:
        return cart
    return Cart.objects.create(
        user=user,
        token=token or uuid.uuid4(),
        last_activity_at=timezone.now(),
    )


def get_guest_cart_by_token(token):
    return Cart.objects.open().filter(token=token, user__isnull=True).first()


def _log_event(*, cart, kind, variant=None, quantity=0, quantity_delta=0, unit_price=None):
    CartEvent.objects.create(
        cart=cart,
        variant=variant,
        kind=kind,
        quantity=quantity,
        quantity_delta=quantity_delta,
        unit_price=unit_price,
    )


def _apply_snapshot(cart, wanted, sellable):
    now = timezone.now()
    live = {
        row.variant_id: row
        for row in cart.items.filter(removed_at__isnull=True).select_related("variant")
    }
    all_rows = {row.variant_id: row for row in cart.items.all()}

    for variant_id, quantity in wanted.items():
        variant = sellable[variant_id]
        price = variant.price
        if price is None:
            continue

        row = live.get(variant_id)
        if row:
            if row.quantity != quantity:
                delta = quantity - row.quantity
                row.quantity = quantity
                row.price_snapshot = price
                row.save(update_fields=["quantity", "price_snapshot"])
                _log_event(
                    cart=cart,
                    kind=CartEvent.Kind.QUANTITY_CHANGED,
                    variant=variant,
                    quantity=quantity,
                    quantity_delta=delta,
                    unit_price=price,
                )
            continue

        row = all_rows.get(variant_id)
        if row:
            row.removed_at = None
            row.quantity = quantity
            row.price_snapshot = price
            row.save(update_fields=["removed_at", "quantity", "price_snapshot"])
            _log_event(
                cart=cart,
                kind=CartEvent.Kind.ADDED,
                variant=variant,
                quantity=quantity,
                quantity_delta=quantity,
                unit_price=price,
            )
            continue

        CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            price_snapshot=price,
            added_at=now,
        )
        _log_event(
            cart=cart,
            kind=CartEvent.Kind.ADDED,
            variant=variant,
            quantity=quantity,
            quantity_delta=quantity,
            unit_price=price,
        )

    for variant_id, row in live.items():
        if variant_id in wanted:
            continue
        row.removed_at = now
        row.save(update_fields=["removed_at"])
        _log_event(
            cart=cart,
            kind=CartEvent.Kind.REMOVED,
            variant=row.variant,
            quantity=0,
            quantity_delta=-row.quantity,
            unit_price=row.price_snapshot,
        )


@transaction.atomic
def merge_guest_cart(guest_cart, user):
    if guest_cart.user_id or guest_cart.merged_into_id:
        return get_or_create_open_cart(user)

    target = get_or_create_open_cart(user)
    guest_live = list(
        guest_cart.items.filter(removed_at__isnull=True).select_related(
            "variant",
            "variant__inventory",
        )
    )
    if guest_live:
        existing = {
            row.variant_id: row
            for row in target.items.filter(removed_at__isnull=True)
        }
        sellable_ids = [item.variant_id for item in guest_live]
        sellable = _sellable_variants_by_id(sellable_ids)

        merge_wanted = {}
        for item in guest_live:
            variant_id = item.variant_id
            if variant_id not in sellable:
                continue
            qty = item.quantity
            if variant_id in existing:
                qty = max(qty, existing[variant_id].quantity)
            available = sellable[variant_id].inventory.available_quantity
            merge_wanted[variant_id] = min(qty, available)

        if merge_wanted:
            _apply_snapshot(target, merge_wanted, sellable)

    guest_cart.merged_into = target
    guest_cart.save(update_fields=["merged_into", "updated_at"])
    _log_event(cart=guest_cart, kind=CartEvent.Kind.MERGED)
    return target


@transaction.atomic
def mark_cart_converted(cart, *, order):
    if cart.converted_at:
        return cart
    cart.converted_at = timezone.now()
    cart.save(update_fields=["converted_at", "updated_at"])
    _log_event(cart=cart, kind=CartEvent.Kind.CONVERTED)
    return cart


def serialize_cart_lines(cart):
    rows = (
        cart.items.filter(removed_at__isnull=True)
        .select_related("variant", "variant__product", "variant__product__image", "variant__inventory")
        .order_by("sort_order", "pk")
    )
    lines = []
    for row in rows:
        variant = row.variant
        product = variant.product
        image_url = ""
        if product.image:
            image_url = product.image.get_rendition("fill-96x96").url
        price = row.price_snapshot if row.price_snapshot is not None else variant.price
        lines.append(
            {
                "id": variant.pk,
                "name": product.name,
                "variantLabel": variant.label,
                "price": str(price or "0"),
                "imageUrl": image_url,
                "url": product.get_marketplace_url(),
                "maxQty": variant.inventory.available_quantity,
                "quantity": row.quantity,
            }
        )
    return lines


@transaction.atomic
def sync_cart(*, token, user=None, items, apply=True):
    """
    Apply a client cart snapshot. Guest carts are created on first meaningful item.
    Logged-in users merge guest token carts then sync to their open account cart.
    """
    try:
        token_uuid = uuid.UUID(str(token))
    except (TypeError, ValueError, AttributeError):
        return None

    variant_ids = [item.get("variant_id") for item in items if item.get("variant_id")]
    sellable = _sellable_variants_by_id(variant_ids)
    wanted = _normalize_wanted_items(items, sellable)

    cart = None
    if user and user.is_authenticated:
        guest = get_guest_cart_by_token(token_uuid)
        if guest:
            merge_guest_cart(guest, user)
        cart = get_open_cart_for_user(user)
        if cart is None:
            if not wanted and not apply:
                return None
            if not wanted and apply:
                return None
            cart = get_or_create_open_cart(user, token=token_uuid)
        if apply or wanted:
            _apply_snapshot(cart, wanted, sellable)
            cart.last_activity_at = timezone.now()
            cart.save(update_fields=["last_activity_at", "updated_at"])
        return cart

    if not wanted:
        cart = get_guest_cart_by_token(token_uuid)
        return cart

    cart = get_guest_cart_by_token(token_uuid)
    if cart is None:
        cart = Cart.objects.create(
            token=token_uuid,
            last_activity_at=timezone.now(),
        )

    _apply_snapshot(cart, wanted, sellable)
    cart.last_activity_at = timezone.now()
    cart.save(update_fields=["last_activity_at", "updated_at"])
    return cart


def get_cart_with_items(user):
    cart = get_open_cart_for_user(user)
    if cart is None:
        cart = get_or_create_open_cart(user)
    return (
        Cart.objects.prefetch_related(
            "items__variant__product__image",
            "items__variant__inventory",
        )
        .filter(pk=cart.pk)
        .first()
    )
