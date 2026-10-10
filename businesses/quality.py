"""Data-quality checks for businesses (domain logic, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from businesses.verification.levels import FreshnessTier, freshness_for

from .models import Business

ISSUE_LABELS = {
    "missing_contact": "Not contactable (no website, email or phone)",
    "missing_logo": "Missing logo",
    "verification_expired": "Verification expired",
    "duplicate_suspected": "Duplicate suspected",
    "customer_reported": "Customer reported outdated information",
    "no_products": "No published products",
}


@dataclass(frozen=True)
class Check:
    code: str
    label: str
    passed: bool


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[Check, ...]
    issues: list[str]
    score: int
    max_score: int = 10


def _filled(value) -> bool:
    return bool(value and value.strip())


def is_contactable(business: Business) -> bool:
    """
    A website, email or phone is required. Address alone does not count:
    it changes too easily to be the only way to reach a business.
    """
    return any(_filled(v) for v in (business.website, business.email, business.phone))


def evaluate_business(business: Business, *, now=None) -> QualityReport:
    now = now or timezone.now()
    issues: list[str] = []

    has_phone = _filled(business.phone)
    has_email = _filled(business.email)
    has_location = _filled(business.address) or _filled(business.town_or_city)
    has_website = _filled(business.website)
    freshness = freshness_for(business.verified_at, now=now)
    verification_ok = freshness.tier not in (
        FreshnessTier.STALE,
        FreshnessTier.HIDDEN,
    )
    from products.models import Product

    published_products = Product.objects.filter(
        business=business,
        status=Product.ProductStatus.PUBLISHED,
    ).exists()

    checks = (
        Check("name", "Business name", bool(business.name and business.name.strip())),
        Check(
            "business_type",
            "Business type",
            bool(business.business_type),
        ),
        Check(
            "description",
            "Description",
            bool(business.description and business.description.strip()),
        ),
        Check("logo", "Logo", business.logo_id is not None),
        Check("phone", "Phone", has_phone),
        Check("email", "Email", has_email),
        Check("location", "Address or town", has_location),
        Check("website", "Website", has_website),
        Check("verification_date", "Verification date", verification_ok),
        Check("products", "Published products", published_products),
    )
    score = sum(1 for c in checks if c.passed)

    if not is_contactable(business):
        issues.append("missing_contact")
    if business.logo_id is None:
        issues.append("missing_logo")
    if not verification_ok:
        issues.append("verification_expired")
    if not published_products:
        issues.append("no_products")

    from businesses.verification.dashboard import OPEN_REPORT_FILTER
    from duplicates.models import DuplicateFlag
    from reviews.models import BusinessReview

    if DuplicateFlag.objects.open().for_object(business).exists():
        issues.append("duplicate_suspected")
    if BusinessReview.objects.filter(business=business).filter(
        OPEN_REPORT_FILTER
    ).exists():
        issues.append("customer_reported")

    return QualityReport(
        checks=checks,
        issues=sorted(set(issues)),
        score=score,
    )


def refresh_business_quality(business_or_qs):
    from django.utils import timezone as tz

    if isinstance(business_or_qs, Business):
        qs = Business.objects.filter(pk=business_or_qs.pk)
    else:
        qs = business_or_qs

    now = tz.now()
    for business in qs:
        report = evaluate_business(business, now=now)
        Business.objects.filter(pk=business.pk).update(
            quality_score=report.score,
            quality_issues=report.issues,
            quality_checked_at=now,
        )


def issue_counts():
    return {
        code: Business.objects.filter(quality_issues__contains=[code]).count()
        for code in ISSUE_LABELS
    }


def score_band_counts():
    return {
        "0_3": Business.objects.filter(quality_score__lte=3).count(),
        "4_6": Business.objects.filter(
            quality_score__gte=4, quality_score__lte=6
        ).count(),
        "7_8": Business.objects.filter(
            quality_score__gte=7, quality_score__lte=8
        ).count(),
        "9_10": Business.objects.filter(quality_score__gte=9).count(),
    }


def listings_needing_attention_count():
    return Business.objects.exclude(quality_issues=[]).count()
