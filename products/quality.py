"""Data-quality checks for products (domain logic, no HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from businesses.quality import is_contactable
from businesses.verification.levels import (
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
    "customer_reported": "Customer reported outdated information",
}

# Category fields read by evaluate_product; saves touching nothing else skip
# the per-category product refresh.
CATEGORY_QUALITY_FIELDS = ("is_active",)

# Business fields read by evaluate_product; same purpose for business saves.
BUSINESS_QUALITY_FIELDS = ("is_active", "email", "phone", "website", "verified_at")

REFRESH_BATCH_SIZE = 500


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


def evaluate_product(
    product,
    *,
    now=None,
    duplicate_ids=None,
    reported_ids=None,
) -> QualityReport:
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

    contact_ok = is_contactable(business)
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
    if duplicate_ids is None:
        duplicate_ids = _product_ids_with_open_duplicates([product.pk])
    if reported_ids is None:
        reported_ids = _product_ids_with_open_reports([product.pk])
    if product.pk in duplicate_ids:
        issues.append("duplicate_suspected")
    if product.pk in reported_ids:
        issues.append("customer_reported")

    return QualityReport(
        checks=checks,
        issues=sorted(set(issues)),
        score=score,
    )


def _product_ids_with_open_duplicates(product_ids) -> set[int]:
    from django.db.models import Q

    from duplicates.models import DuplicateFlag

    ids: set[int] = set()
    rows = DuplicateFlag.objects.open().filter(
        Q(product_a_id__in=product_ids) | Q(product_b_id__in=product_ids)
    ).values_list("product_a_id", "product_b_id")
    for a, b in rows:
        ids.update((a, b))
    return ids & set(product_ids)


def _product_ids_with_open_reports(product_ids) -> set[int]:
    from businesses.verification.dashboard import OPEN_REPORT_FILTER
    from reviews.models import ProductReview

    return set(
        ProductReview.objects.filter(product_id__in=product_ids)
        .filter(OPEN_REPORT_FILTER)
        .values_list("product_id", flat=True)
    )


def refresh_product_quality(product_or_qs, *, batch_size=REFRESH_BATCH_SIZE):
    """
    Recompute and store quality for one product or a queryset.

    Works in primary-key batches with a fixed number of queries per batch
    (products, duplicate flags, open reports, bulk update), so cost grows
    with batches rather than with per-product lookups.
    """
    from django.utils import timezone as tz

    from .models import Product

    if isinstance(product_or_qs, Product):
        qs = Product.objects.filter(pk=product_or_qs.pk)
    else:
        qs = product_or_qs

    qs = (
        qs.order_by("pk")
        .select_related("business", "category")
        .prefetch_related("variants", "images")
    )
    now = tz.now()
    last_pk = 0
    while True:
        batch = list(qs.filter(pk__gt=last_pk)[:batch_size])
        if not batch:
            break
        ids = [p.pk for p in batch]
        duplicate_ids = _product_ids_with_open_duplicates(ids)
        reported_ids = _product_ids_with_open_reports(ids)
        for product in batch:
            report = evaluate_product(
                product,
                now=now,
                duplicate_ids=duplicate_ids,
                reported_ids=reported_ids,
            )
            product.quality_score = report.score
            product.quality_issues = report.issues
            product.quality_checked_at = now
        Product.objects.bulk_update(
            batch,
            ["quality_score", "quality_issues", "quality_checked_at"],
        )
        last_pk = batch[-1].pk


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
