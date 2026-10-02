"""Data-quality checks for products (domain logic, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from businesses.quality import contact_field_errors, has_valid_contact
from businesses.verification import (
    FreshnessTier,
    freshness_for,
    older_verified_at,
)

ISSUE_LABELS = {
    "missing_manufacturer": "Missing manufacturer",
    "missing_category": "Missing category",
    "missing_image": "Missing image",
    "verification_expired": "Verification expired",
    "duplicate_suspected": "Duplicate suspected",
    "invalid_contact": "Invalid contact",
    "customer_reported": "Customer reported outdated information",
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


def evaluate_product(product, *, now=None) -> QualityReport:
    from .models import Product
    now = now or timezone.now()
    business = product.business
    category = product.category
    issues: list[str] = []

    manufacturer_ok = business.is_active
    category_ok = category.is_active
    has_description = bool(
        (product.short_description and product.short_description.strip())
        or (product.description and product.description.strip())
    )
    has_image = product.image_id is not None
    if not has_image:
        try:
            has_image = product.images.exists()
        except Exception:
            pass

    contact_ok = has_valid_contact(
        email=business.email or "",
        phone=business.phone or "",
    )
    verified_at = older_verified_at(product.verified_at, business.verified_at)
    freshness = freshness_for(verified_at, now=now)
    verification_ok = freshness.tier not in (
        FreshnessTier.STALE,
        FreshnessTier.HIDDEN,
    )
    has_website = bool(business.website and business.website.strip())

    has_price = False
    variants = product.variants.all()
    if hasattr(variants, "_result_cache") and variants._result_cache is not None:
        has_price = any(v.price is not None for v in variants)
    else:
        has_price = product.variants.filter(price__isnull=False).exists()

    origin_ok = product.origin_type != Product.OriginType.OTHER

    checks = (
        Check("name", "Product name", bool(product.name and product.name.strip())),
        Check("manufacturer", "Manufacturer", manufacturer_ok),
        Check("category", "Category", category_ok),
        Check("description", "Description", has_description),
        Check("image", "Image", has_image),
        Check("contact", "Contact information", contact_ok),
        Check("verification_date", "Verification date", verification_ok),
        Check("website", "Website", has_website),
        Check("price", "Price", has_price),
        Check("origin", "Origin documented", origin_ok),
    )
    score = sum(1 for c in checks if c.passed)

    if not manufacturer_ok:
        issues.append("missing_manufacturer")
    if not category_ok:
        issues.append("missing_category")
    if not has_image:
        issues.append("missing_image")
    if not verification_ok:
        issues.append("verification_expired")
    if contact_field_errors(
        email=business.email or "",
        phone=business.phone or "",
        website=business.website or "",
    ):
        issues.append("invalid_contact")

    from businesses.verification_dashboard import OPEN_REPORT_FILTER
    from duplicates.models import DuplicateFlag
    from reviews.models import ProductReview

    if DuplicateFlag.objects.open().for_object(product).exists():
        issues.append("duplicate_suspected")
    if ProductReview.objects.filter(product=product).filter(
        OPEN_REPORT_FILTER
    ).exists():
        issues.append("customer_reported")

    return QualityReport(
        checks=checks,
        issues=sorted(set(issues)),
        score=score,
    )


def refresh_product_quality(product_or_qs):
    from django.utils import timezone as tz

    from .models import Product

    if isinstance(product_or_qs, Product):
        qs = Product.objects.filter(pk=product_or_qs.pk)
    else:
        qs = product_or_qs

    qs = qs.select_related("business", "category").prefetch_related(
        "variants", "images"
    )
    now = tz.now()
    for product in qs:
        report = evaluate_product(product, now=now)
        Product.objects.filter(pk=product.pk).update(
            quality_score=report.score,
            quality_issues=report.issues,
            quality_checked_at=now,
        )


def issue_counts():
    from .models import Product

    return {
        code: Product.objects.filter(quality_issues__contains=[code]).count()
        for code in ISSUE_LABELS
    }


def score_band_counts():
    from .models import Product

    return {
        "0_3": Product.objects.filter(quality_score__lte=3).count(),
        "4_6": Product.objects.filter(
            quality_score__gte=4, quality_score__lte=6
        ).count(),
        "7_8": Product.objects.filter(
            quality_score__gte=7, quality_score__lte=8
        ).count(),
        "9_10": Product.objects.filter(quality_score__gte=9).count(),
    }


def listings_needing_attention_count():
    from .models import Product

    return Product.objects.exclude(quality_issues=[]).count()
