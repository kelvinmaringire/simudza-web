"""Data-quality checks for businesses (domain logic, no HTTP)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.utils import timezone

from businesses.verification import FreshnessTier, freshness_for

from .models import Business

PHONE_MIN_DIGITS = 7
_phone_digit_re = re.compile(r"\d")

ISSUE_LABELS = {
    "missing_contact": "Missing contact",
    "invalid_contact": "Invalid contact",
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


def _phone_valid(phone: str) -> bool:
    if not phone or not phone.strip():
        return False
    digits = len(_phone_digit_re.findall(phone))
    return digits >= PHONE_MIN_DIGITS


def _email_valid(email: str) -> bool:
    if not email or not email.strip():
        return False
    try:
        EmailValidator()(email)
        return True
    except ValidationError:
        return False


def _website_valid(website: str) -> bool:
    if not website or not website.strip():
        return False
    try:
        URLValidator()(website)
        return True
    except ValidationError:
        return False


def contact_field_errors(*, email: str, phone: str, website: str) -> bool:
    """True if any non-empty contact field fails validation."""
    if email and email.strip() and not _email_valid(email):
        return True
    if website and website.strip() and not _website_valid(website):
        return True
    if phone and phone.strip() and not _phone_valid(phone):
        return True
    return False


def has_valid_contact(*, email: str, phone: str) -> bool:
    return _email_valid(email) or _phone_valid(phone)


def evaluate_business(business: Business, *, now=None) -> QualityReport:
    now = now or timezone.now()
    issues: list[str] = []

    has_phone = bool(business.phone and business.phone.strip())
    has_email = bool(business.email and business.email.strip())
    has_location = bool(
        (business.address and business.address.strip())
        or (business.town_or_city and business.town_or_city.strip())
    )
    has_website = bool(business.website and business.website.strip())
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

    if not has_phone and not has_email:
        issues.append("missing_contact")
    if contact_field_errors(
        email=business.email or "",
        phone=business.phone or "",
        website=business.website or "",
    ):
        issues.append("invalid_contact")
    if business.logo_id is None:
        issues.append("missing_logo")
    if not verification_ok:
        issues.append("verification_expired")
    if not published_products:
        issues.append("no_products")

    from businesses.verification_dashboard import OPEN_REPORT_FILTER
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
