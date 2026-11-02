from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from django.db.models import Case, CharField, Q, Value, When
from django.utils import timezone

ACTIVE_AFTER = timedelta(hours=24)
INACTIVE_AFTER = timedelta(days=7)
EXPIRED_AFTER = timedelta(days=90)


class CartStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ABANDONED = "abandoned"
    CONVERTED = "converted"
    EXPIRED = "expired"
    MERGED = "merged"


CART_STATUS_LABELS = {
    CartStatus.ACTIVE: "Active",
    CartStatus.INACTIVE: "Inactive",
    CartStatus.ABANDONED: "Abandoned",
    CartStatus.CONVERTED: "Converted",
    CartStatus.EXPIRED: "Expired",
    CartStatus.MERGED: "Merged",
}


def lifecycle_status_for_cart(
    *,
    last_activity_at: datetime | None,
    converted_at: datetime | None,
    merged_into_id: int | None,
    now: datetime | None = None,
) -> CartStatus:
    now = now or timezone.now()
    if merged_into_id:
        return CartStatus.MERGED
    if converted_at is not None:
        return CartStatus.CONVERTED
    if last_activity_at is None:
        return CartStatus.ABANDONED
    if last_activity_at < now - EXPIRED_AFTER:
        return CartStatus.EXPIRED
    if last_activity_at < now - INACTIVE_AFTER:
        return CartStatus.ABANDONED
    if last_activity_at < now - ACTIVE_AFTER:
        return CartStatus.INACTIVE
    return CartStatus.ACTIVE


def annotate_lifecycle(queryset, *, now=None):
    now = now or timezone.now()
    active_cutoff = now - ACTIVE_AFTER
    inactive_cutoff = now - INACTIVE_AFTER
    expired_cutoff = now - EXPIRED_AFTER

    return queryset.annotate(
        lifecycle_status_code=Case(
            When(merged_into_id__isnull=False, then=Value(CartStatus.MERGED.value)),
            When(converted_at__isnull=False, then=Value(CartStatus.CONVERTED.value)),
            When(last_activity_at__lt=expired_cutoff, then=Value(CartStatus.EXPIRED.value)),
            When(
                last_activity_at__lt=inactive_cutoff,
                then=Value(CartStatus.ABANDONED.value),
            ),
            When(
                last_activity_at__lt=active_cutoff,
                then=Value(CartStatus.INACTIVE.value),
            ),
            default=Value(CartStatus.ACTIVE.value),
            output_field=CharField(max_length=20),
        )
    )


def analytics_cart_queryset(*, now=None):
    """Carts included in headline analytics (excludes merged)."""
    from marketplace.models import Cart

    return annotate_lifecycle(
        Cart.objects.filter(merged_into__isnull=True),
        now=now,
    )
