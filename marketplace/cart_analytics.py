from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from marketplace.cart_lifecycle import (
    CART_STATUS_LABELS,
    CartStatus,
    analytics_cart_queryset,
)
from marketplace.models import CartItem


def user_can_view_cart_analytics(user):
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    return "marketplace.view_cart" in user.get_all_permissions()


def _status_counts(*, now=None):
    qs = analytics_cart_queryset(now=now)
    rows = qs.values("lifecycle_status_code").annotate(count=Count("pk"))
    counts = {status.value: 0 for status in CartStatus if status != CartStatus.MERGED}
    for row in rows:
        code = row["lifecycle_status_code"]
        if code in counts:
            counts[code] = row["count"]
    return counts


def _value_for_statuses(statuses, *, now=None):
    qs = (
        analytics_cart_queryset(now=now)
        .filter(lifecycle_status_code__in=[s.value for s in statuses])
        .with_value()
    )
    total = qs.aggregate(total=Sum("cart_value"))["total"]
    return total or Decimal("0")


def cart_analytics_summary(*, now=None):
    counts = _status_counts(now=now)
    potential = _value_for_statuses(
        [CartStatus.ACTIVE, CartStatus.INACTIVE],
        now=now,
    )
    abandoned = _value_for_statuses([CartStatus.ABANDONED], now=now)
    status_rows = [
        (CART_STATUS_LABELS[CartStatus(code)], counts.get(code, 0), code)
        for code in (
            CartStatus.ACTIVE.value,
            CartStatus.INACTIVE.value,
            CartStatus.ABANDONED.value,
            CartStatus.CONVERTED.value,
            CartStatus.EXPIRED.value,
        )
    ]
    return {
        "status_rows": status_rows,
        "potential_cart_value": potential,
        "abandoned_cart_value": abandoned,
        "most_abandoned_products": most_abandoned_products(limit=10, now=now),
    }


def most_abandoned_products(*, limit=10, now=None):
    abandoned_ids = analytics_cart_queryset(now=now).filter(
        lifecycle_status_code=CartStatus.ABANDONED.value,
    )
    rows = (
        CartItem.objects.filter(
            cart__in=abandoned_ids,
            removed_at__isnull=True,
        )
        .values("variant__product_id", "variant__product__name")
        .annotate(units=Sum("quantity"))
        .order_by("-units")[:limit]
    )
    return [
        {
            "product_id": row["variant__product_id"],
            "product_name": row["variant__product__name"],
            "units": row["units"],
        }
        for row in rows
    ]
