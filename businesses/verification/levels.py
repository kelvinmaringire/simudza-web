from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from django.db import models
from django.db.models import Q
from django.utils import timezone

CURRENT_DAYS = 90
NEEDS_DAYS = 180
HIDE_AFTER_DAYS = 365

REMINDER_INTERVAL_DAYS = 30
OWNER_RESPONSE_GRACE_DAYS = 14


class VerificationLevel(models.TextChoices):
    """How reliable a listing's information is (not whether it is still trading)."""

    SIMUDZA_VERIFIED = "simudza_verified", "Simudza Verified"
    SOURCE_VERIFIED = "source_verified", "Information source checked"
    COMMUNITY_REPORTED = (
        "community_reported",
        "Community reported — not verified by Simudza",
    )
    UNVERIFIED = "unverified", "Not yet verified"


class LifecycleStatus(models.TextChoices):
    """Whether a business is still trading / a product is still made."""

    ACTIVE = "active", "Active"
    DISCONTINUED = "discontinued", "Discontinued / withdrawn"


@dataclass(frozen=True)
class VerificationLevelMeta:
    level: VerificationLevel
    label: str
    description: str
    badge_class: str
    emoji: str
    rank: int
    shows_reference: bool = False


LEVEL_META = {
    VerificationLevel.SIMUDZA_VERIFIED: VerificationLevelMeta(
        level=VerificationLevel.SIMUDZA_VERIFIED,
        label=VerificationLevel.SIMUDZA_VERIFIED.label,
        description=(
            "Simudza checked this listing against defined evidence and completed "
            "its verification process (registration documents, confirmed contact "
            "details, or contact through an independently established channel)."
        ),
        badge_class="badge-success",
        emoji="🟢",
        rank=0,
    ),
    VerificationLevel.SOURCE_VERIFIED: VerificationLevelMeta(
        level=VerificationLevel.SOURCE_VERIFIED,
        label=VerificationLevel.SOURCE_VERIFIED.label,
        description=(
            "Simudza confirmed specific information against a reliable source, "
            "such as the manufacturer's official website or catalogue, but has "
            "not completed its full verification process."
        ),
        badge_class="badge-info",
        emoji="🔵",
        rank=1,
        shows_reference=True,
    ),
    VerificationLevel.COMMUNITY_REPORTED: VerificationLevelMeta(
        level=VerificationLevel.COMMUNITY_REPORTED,
        label=VerificationLevel.COMMUNITY_REPORTED.label,
        description=(
            "Submitted by a customer, retailer, supplier, or member of the public. "
            "Simudza has not independently verified it."
        ),
        badge_class="badge-warning",
        emoji="🟡",
        rank=2,
    ),
    VerificationLevel.UNVERIFIED: VerificationLevelMeta(
        level=VerificationLevel.UNVERIFIED,
        label=VerificationLevel.UNVERIFIED.label,
        description=(
            "Listed in Simudza's database, but the required verification checks "
            "have not been completed."
        ),
        badge_class="badge-ghost",
        emoji="⚪",
        rank=3,
    ),
}

# Levels the public "Verified only" filter accepts, and the levels an
# unconfirmed edit drops back to Community reported.
TRUSTED_LEVELS = frozenset(
    {
        VerificationLevel.SIMUDZA_VERIFIED,
        VerificationLevel.SOURCE_VERIFIED,
    }
)


def level_meta(level: str) -> VerificationLevelMeta:
    try:
        key = VerificationLevel(level)
    except ValueError:
        key = VerificationLevel.UNVERIFIED
    return LEVEL_META[key]


def level_legend():
    return [
        LEVEL_META[level]
        for level in sorted(VerificationLevel, key=lambda lv: LEVEL_META[lv].rank)
    ]


def is_trusted_level(level: str) -> bool:
    try:
        return VerificationLevel(level) in TRUSTED_LEVELS
    except ValueError:
        return False


class FreshnessTier(str, Enum):
    CURRENT = "current"
    NEEDS = "needs"
    STALE = "stale"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class Freshness:
    tier: FreshnessTier
    label: str
    range_text: str
    badge_class: str
    emoji: str

    @property
    def is_hidden_from_search(self) -> bool:
        return self.tier is FreshnessTier.HIDDEN


FRESHNESS_BY_TIER = {
    FreshnessTier.CURRENT: Freshness(
        tier=FreshnessTier.CURRENT,
        label="Current",
        range_text="0–3 months",
        badge_class="badge-success",
        emoji="🟢",
    ),
    FreshnessTier.NEEDS: Freshness(
        tier=FreshnessTier.NEEDS,
        label="Needs verification",
        range_text="3–6 months",
        badge_class="badge-warning",
        emoji="🟡",
    ),
    FreshnessTier.STALE: Freshness(
        tier=FreshnessTier.STALE,
        label="Stale",
        range_text="6–12 months",
        badge_class="badge-outline border-orange-500 text-orange-600",
        emoji="🟠",
    ),
    FreshnessTier.HIDDEN: Freshness(
        tier=FreshnessTier.HIDDEN,
        label="Hide from search",
        range_text="13+ months",
        badge_class="badge-error",
        emoji="🔴",
    ),
}


def search_cutoff() -> datetime:
    return timezone.now() - timezone.timedelta(days=HIDE_AFTER_DAYS)


def searchable_q(prefix: str = "") -> Q:
    """
    Visibility rule for one listing; prefix reaches it through relations.
    Every verification level is searchable; discontinued or stale listings are not.
    """
    return Q(
        **{
            f"{prefix}verified_at__gte": search_cutoff(),
            f"{prefix}lifecycle_status": LifecycleStatus.ACTIVE,
        }
    )


def age_days(dt: Optional[datetime], *, now: Optional[datetime] = None) -> Optional[int]:
    if dt is None:
        return None
    now = now or timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = now - dt
    return max(delta.days, 0)


def freshness_for(dt: Optional[datetime], *, now: Optional[datetime] = None) -> Freshness:
    if dt is None:
        return FRESHNESS_BY_TIER[FreshnessTier.HIDDEN]
    days = age_days(dt, now=now)
    if days is None or days > HIDE_AFTER_DAYS:
        return FRESHNESS_BY_TIER[FreshnessTier.HIDDEN]
    if days <= CURRENT_DAYS:
        return FRESHNESS_BY_TIER[FreshnessTier.CURRENT]
    if days <= NEEDS_DAYS:
        return FRESHNESS_BY_TIER[FreshnessTier.NEEDS]
    return FRESHNESS_BY_TIER[FreshnessTier.STALE]


def older_verified_at(
    product_verified_at: Optional[datetime],
    business_verified_at: Optional[datetime],
) -> Optional[datetime]:
    if product_verified_at is None and business_verified_at is None:
        return None
    if product_verified_at is None:
        return business_verified_at
    if business_verified_at is None:
        return product_verified_at
    return min(product_verified_at, business_verified_at)
