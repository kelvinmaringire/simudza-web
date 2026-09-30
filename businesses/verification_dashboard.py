from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Least
from django.utils import timezone

from businesses.models import Business
from businesses.verification import (
    CURRENT_DAYS,
    FRESHNESS_BY_TIER,
    LEVEL_META,
    FreshnessTier,
    VerificationLevel,
    age_days,
    level_legend,
)
from products.models import Product
from reviews.models import BusinessReview, ProductReview, ReportStatus

FLAGGED_LIMIT = 25
OPEN_REPORTS_LIMIT = 25

OPEN_REPORT_FILTER = Q(status=ReportStatus.OPEN) & ~Q(reason="")


def _listing_ids_with_open_reports(model_review, listing_field):
    return model_review.objects.filter(OPEN_REPORT_FILTER).values_list(
        listing_field,
        flat=True,
    ).distinct()


def _thresholds():
    now = timezone.now()
    return {
        "now": now,
        "current": now - timedelta(days=CURRENT_DAYS),
        "needs": now - timedelta(days=180),
        "stale": now - timedelta(days=365),
    }


def business_level_counts():
    base = Business.objects.all()
    counts = {choice.value: 0 for choice in VerificationLevel}
    for row in base.values("verification_level").annotate(
        count=models.Count("pk"),
    ):
        level = row["verification_level"]
        if level in counts:
            counts[level] = row["count"]
    return counts


def product_level_counts():
    base = Product.objects.all()
    counts = {choice.value: 0 for choice in VerificationLevel}
    for row in base.values("verification_level").annotate(
        count=models.Count("pk"),
    ):
        level = row["verification_level"]
        if level in counts:
            counts[level] = row["count"]
    return counts


def level_count_rows(counts_dict):
    return [
        {
            "meta": LEVEL_META[level],
            "count": counts_dict.get(level.value, 0),
        }
        for level in sorted(VerificationLevel, key=lambda lv: LEVEL_META[lv].rank)
    ]


def business_tier_counts():
    thresholds = _thresholds()
    t90 = thresholds["current"]
    t180 = thresholds["needs"]
    t365 = thresholds["stale"]
    base = Business.objects.all()
    return {
        FreshnessTier.CURRENT: base.filter(verified_at__gte=t90).count(),
        FreshnessTier.NEEDS: base.filter(
            verified_at__lt=t90,
            verified_at__gte=t180,
        ).count(),
        FreshnessTier.STALE: base.filter(
            verified_at__lt=t180,
            verified_at__gte=t365,
        ).count(),
        FreshnessTier.HIDDEN: base.filter(
            Q(verified_at__isnull=True) | Q(verified_at__lt=t365)
        ).count(),
    }


def product_tier_counts():
    thresholds = _thresholds()
    t90 = thresholds["current"]
    t180 = thresholds["needs"]
    t365 = thresholds["stale"]
    base = Product.objects.annotate(
        effective_at=Least("verified_at", "business__verified_at")
    )
    return {
        FreshnessTier.CURRENT: base.filter(effective_at__gte=t90).count(),
        FreshnessTier.NEEDS: base.filter(
            effective_at__lt=t90,
            effective_at__gte=t180,
        ).count(),
        FreshnessTier.STALE: base.filter(
            effective_at__lt=t180,
            effective_at__gte=t365,
        ).count(),
        FreshnessTier.HIDDEN: base.filter(
            Q(verified_at__isnull=True)
            | Q(business__verified_at__isnull=True)
            | Q(effective_at__lt=t365)
        ).count(),
    }


def flagged_businesses(limit=FLAGGED_LIMIT):
    thresholds = _thresholds()
    t90 = thresholds["current"]
    report_business_ids = _listing_ids_with_open_reports(BusinessReview, "business_id")
    rows = (
        Business.objects.filter(
            Q(verified_at__isnull=True)
            | Q(verified_at__lt=t90)
            | Q(pk__in=report_business_ids)
        )
        .order_by(F("verified_at").asc(nulls_first=True), "name")[:limit]
    )
    return [_business_row(b) for b in rows]


def flagged_products(limit=FLAGGED_LIMIT):
    thresholds = _thresholds()
    t90 = thresholds["current"]
    report_product_ids = _listing_ids_with_open_reports(ProductReview, "product_id")
    rows = (
        Product.objects.select_related("business")
        .annotate(effective_at=Least("verified_at", "business__verified_at"))
        .filter(
            Q(verified_at__isnull=True)
            | Q(business__verified_at__isnull=True)
            | Q(effective_at__lt=t90)
            | Q(pk__in=report_product_ids)
        )
        .order_by(F("effective_at").asc(nulls_first=True), "name")[:limit]
    )
    return [_product_row(p) for p in rows]


def _business_row(business: Business) -> dict:
    freshness = business.freshness
    verified_at = business.verified_at
    open_report_count = getattr(business, "open_report_count", None)
    if open_report_count is None:
        open_report_count = BusinessReview.objects.filter(
            business=business,
        ).filter(OPEN_REPORT_FILTER).count()
    return {
        "obj": business,
        "name": business.name,
        "freshness": freshness,
        "level_meta": business.level_meta,
        "verification_level": business.verification_level,
        "verification_reference": business.verification_reference,
        "verified_at": verified_at,
        "age_days": age_days(verified_at),
        "via_business": False,
        "open_report_count": open_report_count,
        "admin_url": f"/admin/business/edit/{business.pk}/",
    }


def _product_row(product: Product) -> dict:
    freshness = product.freshness
    effective = product.effective_verified_at
    open_report_count = getattr(product, "open_report_count", None)
    if open_report_count is None:
        open_report_count = ProductReview.objects.filter(
            product=product,
        ).filter(OPEN_REPORT_FILTER).count()
    return {
        "obj": product,
        "name": product.name,
        "business_name": product.business.name if product.business_id else "",
        "freshness": freshness,
        "level_meta": product.level_meta,
        "verification_level": product.verification_level,
        "verification_reference": product.verification_reference,
        "verified_at": effective,
        "age_days": age_days(effective),
        "via_business": product.inherits_business_status,
        "open_report_count": open_report_count,
        "admin_url": f"/admin/product/edit/{product.pk}/",
    }


def verification_attention_count():
    thresholds = _thresholds()
    t90 = thresholds["current"]
    business_count = Business.objects.filter(
        Q(verified_at__isnull=True) | Q(verified_at__lt=t90)
    ).count()
    product_count = (
        Product.objects.annotate(
            effective_at=Least("verified_at", "business__verified_at")
        )
        .filter(
            Q(verified_at__isnull=True)
            | Q(business__verified_at__isnull=True)
            | Q(effective_at__lt=t90)
        )
        .count()
    )
    open_reports = (
        ProductReview.objects.filter(OPEN_REPORT_FILTER).count()
        + BusinessReview.objects.filter(OPEN_REPORT_FILTER).count()
    )
    return business_count + product_count + open_reports


def open_reports(limit=OPEN_REPORTS_LIMIT):
    product_reports = list(
        ProductReview.objects.filter(OPEN_REPORT_FILTER)
        .select_related("product")
        .order_by("-created_at")[:limit]
    )
    business_reports = list(
        BusinessReview.objects.filter(OPEN_REPORT_FILTER)
        .select_related("business")
        .order_by("-created_at")[:limit]
    )
    rows = []
    for report in product_reports:
        rows.append(
            {
                "kind": "product",
                "listing_name": report.product.name,
                "listing_url": report.product.get_absolute_url(),
                "reason": report.get_reason_display(),
                "reporter": report.reporter_display,
                "created_at": report.created_at,
                "admin_url": f"/admin/product_review/edit/{report.pk}/",
            }
        )
    for report in business_reports:
        rows.append(
            {
                "kind": "business",
                "listing_name": report.business.name,
                "listing_url": report.business.get_absolute_url(),
                "reason": report.get_reason_display(),
                "reporter": report.reporter_display,
                "created_at": report.created_at,
                "admin_url": f"/admin/business_review/edit/{report.pk}/",
            }
        )
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return rows[:limit]


def resolve_open_reports_for_business(business, *, resolved_at):
    BusinessReview.objects.filter(business=business).filter(OPEN_REPORT_FILTER).update(
        status=ReportStatus.RESOLVED,
        resolved_at=resolved_at,
    )


def resolve_open_reports_for_product(product, *, resolved_at):
    ProductReview.objects.filter(product=product).filter(OPEN_REPORT_FILTER).update(
        status=ReportStatus.RESOLVED,
        resolved_at=resolved_at,
    )


def freshness_legend():
    return [FRESHNESS_BY_TIER[tier] for tier in FreshnessTier]


def verification_level_legend():
    return level_legend()


def tier_count_rows(counts_dict):
    return [
        {"freshness": FRESHNESS_BY_TIER[tier], "count": counts_dict[tier]}
        for tier in FreshnessTier
    ]
