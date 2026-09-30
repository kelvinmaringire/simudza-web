from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from django.db import models
from django.utils import timezone

CURRENT_DAYS = 90
NEEDS_DAYS = 180
HIDE_AFTER_DAYS = 365

REMINDER_INTERVAL_DAYS = 30
OWNER_RESPONSE_GRACE_DAYS = 14


class VerificationLevel(models.TextChoices):
    VERIFIED_MANUFACTURER = (
        "verified_manufacturer",
        "Verified manufacturer",
    )
    SIMUDZA_CHECKED = "simudza_checked", "Simudza checked"
    VERIFIED_SOURCE = "verified_source", "Verified source"
    COMMUNITY_REPORTED = "community_reported", "Community reported"
    UNVERIFIED = "unverified", "Unverified"
    DISCONTINUED = "discontinued", "Discontinued / withdrawn"


@dataclass(frozen=True)
class VerificationLevelMeta:
    level: VerificationLevel
    label: str
    description: str
    badge_class: str
    emoji: str
    rank: int


LEVEL_META = {
    VerificationLevel.VERIFIED_MANUFACTURER: VerificationLevelMeta(
        level=VerificationLevel.VERIFIED_MANUFACTURER,
        label="Verified manufacturer",
        description=(
            "Information supplied or confirmed by the manufacturer."
        ),
        badge_class="badge-success",
        emoji="🟢",
        rank=0,
    ),
    VerificationLevel.SIMUDZA_CHECKED: VerificationLevelMeta(
        level=VerificationLevel.SIMUDZA_CHECKED,
        label="Simudza checked",
        description=(
            "Simudza staff confirmed directly (phone, site visit, or in-store)."
        ),
        badge_class="badge-secondary",
        emoji="🟣",
        rank=1,
    ),
    VerificationLevel.VERIFIED_SOURCE: VerificationLevelMeta(
        level=VerificationLevel.VERIFIED_SOURCE,
        label="Verified source",
        description=(
            "Corroborated through an authoritative source such as ZimTrade or SAZ."
        ),
        badge_class="badge-info",
        emoji="🔵",
        rank=2,
    ),
    VerificationLevel.COMMUNITY_REPORTED: VerificationLevelMeta(
        level=VerificationLevel.COMMUNITY_REPORTED,
        label="Community reported",
        description="Submitted by users but not independently verified.",
        badge_class="badge-warning",
        emoji="🟡",
        rank=3,
    ),
    VerificationLevel.UNVERIFIED: VerificationLevelMeta(
        level=VerificationLevel.UNVERIFIED,
        label="Unverified",
        description="Discovered or listed, awaiting confirmation.",
        badge_class="badge-ghost",
        emoji="⚪",
        rank=4,
    ),
    VerificationLevel.DISCONTINUED: VerificationLevelMeta(
        level=VerificationLevel.DISCONTINUED,
        label="Discontinued / withdrawn",
        description="Historical listing, no longer confirmed as active.",
        badge_class="badge-error",
        emoji="🔴",
        rank=5,
    ),
}

TRUSTED_LEVELS = frozenset(
    {
        VerificationLevel.VERIFIED_MANUFACTURER,
        VerificationLevel.SIMUDZA_CHECKED,
        VerificationLevel.VERIFIED_SOURCE,
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
