"""
Verification workflow:

    Manufacturer -> verifies      (owner confirms or updates their own listings)
    Customer     -> reports       (public "Report outdated information")
    System       -> monitors      (monitor_verification command: reminders + exceptions)
    Staff        -> investigates  (only the exceptions queue, not every listing)
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.db.models.functions import Least
from django.urls import reverse
from django.utils import timezone

from history.context import change_context
from history.services import update_with_history
from products.models import Product
from reviews.models import BusinessReview, ProductReview

from .models import Business
from .verification_dashboard import (
    OPEN_REPORT_FILTER,
    resolve_open_reports_for_business,
    resolve_open_reports_for_product,
)
from .verification import (
    CURRENT_DAYS,
    NEEDS_DAYS,
    OWNER_RESPONSE_GRACE_DAYS,
    REMINDER_INTERVAL_DAYS,
    VerificationLevel,
    FreshnessTier,
    age_days,
    is_trusted_level,
)

EXCEPTIONS_LIMIT = 50


def _site_url(path):
    return f"{settings.WAGTAILADMIN_BASE_URL.rstrip('/')}{path}"


# --- Verifying --------------------------------------------------------------


def mark_verified(obj, *, user=None, level, reference="", when=None, reason=None):
    when = when or timezone.now()
    obj.verified_at = when
    obj.verified_by = user
    obj.verification_level = level
    obj.verification_reference = reference or ""
    log_reason = reason if reason is not None else (reference or "Verification level set")
    with change_context(user=user, reason=log_reason):
        obj.save(
            update_fields=[
                "verified_at",
                "verified_by",
                "verification_level",
                "verification_reference",
            ]
        )
    return when


def owner_confirm_business(business, user):
    when = mark_verified(
        business,
        user=user,
        level=VerificationLevel.VERIFIED_MANUFACTURER,
        reason="Owner confirmed listing",
    )
    with change_context(user=user, reason="Owner confirmed listing"):
        business.verification_reminder_sent_at = None
        business.save(update_fields=["verification_reminder_sent_at"])
    return when


def owner_confirm_products(business, user, products=None):
    when = timezone.now()
    queryset = products if products is not None else business.products.all()
    with change_context(user=user, reason="Owner confirmed listing"):
        count = update_with_history(
            queryset,
            verified_at=when,
            verified_by=user,
            verification_level=VerificationLevel.VERIFIED_MANUFACTURER,
            verification_reference="",
        )
    return count


def staff_set_level(obj, user, level, reference=""):
    when = mark_verified(obj, user=user, level=level, reference=reference)
    if is_trusted_level(level):
        if isinstance(obj, Business):
            resolve_open_reports_for_business(obj, resolved_at=when)
        else:
            resolve_open_reports_for_product(obj, resolved_at=when)
    return when


def staff_verify_business(business, user, *, level=None, reference=""):
    level = level or VerificationLevel.SIMUDZA_CHECKED
    return staff_set_level(business, user, level, reference)


def staff_verify_product(product, user, *, level=None, reference=""):
    level = level or VerificationLevel.SIMUDZA_CHECKED
    return staff_set_level(product, user, level, reference)


def bulk_set_level(objects, user, level, reference=""):
    """Apply staff_set_level to each object (bulk admin edits)."""
    count = 0
    for obj in objects:
        staff_set_level(obj, user, level, reference=reference)
        count += 1
    return count


# --- Owner view -------------------------------------------------------------


def owner_listings(user):
    businesses = list(
        Business.objects.filter(owner=user).prefetch_related("products").order_by("name")
    )
    rows = []
    for business in businesses:
        products = sorted(business.products.all(), key=lambda p: p.name.lower())
        product_rows = []
        for product in products:
            product.business = business
            product_rows.append(
                {
                    "obj": product,
                    "freshness": product.freshness,
                    "level_meta": product.level_meta,
                    "verified_at": product.effective_verified_at,
                    "own_verified_at": product.verified_at,
                    "open_report_count": ProductReview.objects.filter(product=product)
                    .filter(OPEN_REPORT_FILTER)
                    .count(),
                }
            )
        due = [
            row for row in product_rows
            if row["freshness"].tier is not FreshnessTier.CURRENT
        ]
        rows.append(
            {
                "obj": business,
                "freshness": business.freshness,
                "level_meta": business.level_meta,
                "verified_at": business.verified_at,
                "open_report_count": BusinessReview.objects.filter(business=business)
                .filter(OPEN_REPORT_FILTER)
                .count(),
                "products": product_rows,
                "due_product_count": len(due),
                "needs_action": business.freshness.tier is not FreshnessTier.CURRENT
                or bool(due),
            }
        )
    return rows


# --- Monitoring -------------------------------------------------------------


def _due_products(business, *, now):
    cutoff = now - timedelta(days=CURRENT_DAYS)
    return list(
        business.products.filter(Q(verified_at__isnull=True) | Q(verified_at__lt=cutoff))
    )


def _business_is_due(business, *, now):
    if business.verification_level == VerificationLevel.DISCONTINUED:
        return False
    cutoff = now - timedelta(days=CURRENT_DAYS)
    if business.verified_at is None or business.verified_at < cutoff:
        return True
    return bool(_due_products(business, now=now))


def _owner_email(business):
    if business.owner_id and business.owner.email:
        return business.owner.email
    return business.email


def businesses_due_for_reminder(*, now=None):
    now = now or timezone.now()
    resend_before = now - timedelta(days=REMINDER_INTERVAL_DAYS)
    candidates = Business.objects.filter(owner__isnull=False, is_active=True).exclude(
        verification_level=VerificationLevel.DISCONTINUED,
    ).filter(
        Q(verification_reminder_sent_at__isnull=True)
        | Q(verification_reminder_sent_at__lt=resend_before)
    ).select_related("owner")
    return [
        business for business in candidates
        if _owner_email(business) and _business_is_due(business, now=now)
    ]


def send_owner_reminder(business, *, now=None):
    now = now or timezone.now()
    email = _owner_email(business)
    if not email:
        return False
    due_products = _due_products(business, now=now)
    lines = [
        "Hello from Simudza,",
        "",
        f"Please confirm that the listing for {business.name} is still accurate.",
        "Listings that are not confirmed within 12 months are hidden from search.",
        "",
    ]
    if business.freshness.tier is not FreshnessTier.CURRENT:
        lines.append(f"- Company profile (last verified {_fmt(business.verified_at)})")
    for product in due_products:
        lines.append(f"- {product.name} (last verified {_fmt(product.verified_at)})")
    lines += [
        "",
        "Confirm or update everything in one place:",
        _site_url(reverse("accounts:dashboard") + "#my-listings"),
    ]
    send_mail(
        subject=f"Please confirm your Simudza listings for {business.name}",
        message="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
    business.verification_reminder_sent_at = now
    business.save(update_fields=["verification_reminder_sent_at"])
    return True


def notify_owner_of_report(report):
    business = report.product.business if hasattr(report, "product") else report.business
    email = _owner_email(business)
    if not email:
        return False
    listing = report.product.name if hasattr(report, "product") else business.name
    send_mail(
        subject=f"A customer reported outdated information on {listing}",
        message="\n".join(
            [
                "Hello from Simudza,",
                "",
                f'A visitor reported "{report.get_reason_display()}" on {listing}.',
                report.body or "",
                "",
                "If the listing is still correct, confirm it. If not, update it:",
                _site_url(reverse("accounts:dashboard") + "#my-listings"),
            ]
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
    return True


def _fmt(dt):
    return f"{dt.day} {dt:%B %Y}" if dt else "never"


# --- Exceptions for staff ---------------------------------------------------


def verification_exceptions(*, now=None, limit=EXCEPTIONS_LIMIT):
    """Only the listings a human needs to look at."""
    now = now or timezone.now()
    current_cutoff = now - timedelta(days=CURRENT_DAYS)
    stale_cutoff = now - timedelta(days=NEEDS_DAYS)
    grace_cutoff = now - timedelta(days=OWNER_RESPONSE_GRACE_DAYS)
    rows = {}

    def add(key, row):
        existing = rows.get(key)
        if existing is None:
            rows[key] = row
            return
        for reason in row["reasons"]:
            if reason not in existing["reasons"]:
                existing["reasons"].append(reason)
        if row["severity_rank"] < existing["severity_rank"]:
            existing["severity"] = row["severity"]
            existing["severity_rank"] = row["severity_rank"]

    # 1. Customer reports (conflict when owner re-confirmed after the report).
    for report in (
        ProductReview.objects.filter(OPEN_REPORT_FILTER)
        .select_related("product", "product__business")
        .order_by("created_at")
    ):
        product = report.product
        if product.verification_level == VerificationLevel.DISCONTINUED:
            continue
        conflict = (
            product.verification_level == VerificationLevel.VERIFIED_MANUFACTURER
            and product.verified_at
            and product.verified_at > report.created_at
        )
        add(
            ("product", product.pk),
            _exception_row(
                product,
                kind="product",
                severity="high" if conflict else "medium",
                reason=(
                    f"Owner confirmed after a customer reported “{report.get_reason_display()}”"
                    if conflict
                    else f"Customer report: {report.get_reason_display()}"
                ),
            ),
        )
    for report in (
        BusinessReview.objects.filter(OPEN_REPORT_FILTER)
        .select_related("business")
        .order_by("created_at")
    ):
        business = report.business
        if business.verification_level == VerificationLevel.DISCONTINUED:
            continue
        conflict = (
            business.verification_level == VerificationLevel.VERIFIED_MANUFACTURER
            and business.verified_at
            and business.verified_at > report.created_at
        )
        add(
            ("business", business.pk),
            _exception_row(
                business,
                kind="business",
                severity="high" if conflict else "medium",
                reason=(
                    f"Owner confirmed after a customer reported “{report.get_reason_display()}”"
                    if conflict
                    else f"Customer report: {report.get_reason_display()}"
                ),
            ),
        )

    # 2. Due listings with no manufacturer account to confirm them.
    for business in Business.objects.filter(owner__isnull=True).exclude(
        verification_level=VerificationLevel.DISCONTINUED,
    ).filter(
        Q(verified_at__isnull=True) | Q(verified_at__lt=current_cutoff)
    ):
        add(
            ("business", business.pk),
            _exception_row(
                business,
                kind="business",
                severity="medium",
                reason="No manufacturer account, so nobody can self-confirm it",
            ),
        )
    for product in (
        Product.objects.select_related("business")
        .exclude(verification_level=VerificationLevel.DISCONTINUED)
        .exclude(business__verification_level=VerificationLevel.DISCONTINUED)
        .filter(business__owner__isnull=True)
        .annotate(effective_at=Least("verified_at", "business__verified_at"))
        .filter(
            Q(verified_at__isnull=True)
            | Q(business__verified_at__isnull=True)
            | Q(effective_at__lt=current_cutoff)
        )
    ):
        if ("business", product.business_id) in rows:
            continue
        add(
            ("product", product.pk),
            _exception_row(
                product,
                kind="product",
                severity="low",
                reason="No manufacturer account, so nobody can self-confirm it",
            ),
        )

    # 3. Owner was reminded but let it go stale.
    for business in Business.objects.filter(
        owner__isnull=False,
        verification_reminder_sent_at__lt=grace_cutoff,
    ).exclude(
        verification_level=VerificationLevel.DISCONTINUED,
    ).select_related("owner"):
        stale_products = business.products.filter(
            Q(verified_at__isnull=True) | Q(verified_at__lt=stale_cutoff)
        ).count()
        business_stale = business.verified_at is None or business.verified_at < stale_cutoff
        if not (business_stale or stale_products):
            continue
        parts = []
        if business_stale:
            parts.append("company profile")
        if stale_products:
            parts.append(f"{stale_products} product{'s' if stale_products != 1 else ''}")
        add(
            ("business", business.pk),
            _exception_row(
                business,
                kind="business",
                severity="medium",
                reason=(
                    f"Owner reminded {_fmt(business.verification_reminder_sent_at)}, "
                    f"still stale: {', '.join(parts)}"
                ),
            ),
        )

    ordered = sorted(rows.values(), key=lambda row: (row["severity_rank"], row["age_sort"]))
    return ordered[:limit]


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _exception_row(obj, *, kind, severity, reason):
    if kind == "product":
        verified_at = obj.effective_verified_at
        admin_url = f"/admin/product/edit/{obj.pk}/"
        business_name = obj.business.name
        level_meta_obj = obj.level_meta
    else:
        verified_at = obj.verified_at
        admin_url = f"/admin/business/edit/{obj.pk}/"
        business_name = ""
        level_meta_obj = obj.level_meta
    days = age_days(verified_at)
    return {
        "kind": kind,
        "obj": obj,
        "name": obj.name,
        "business_name": business_name,
        "public_url": obj.get_absolute_url(),
        "admin_url": admin_url,
        "freshness": obj.freshness,
        "level_meta": level_meta_obj,
        "verified_at": verified_at,
        "verification_reference": getattr(obj, "verification_reference", "") or "",
        "age_days": days,
        "age_sort": -(days if days is not None else 10**6),
        "severity": severity,
        "severity_rank": SEVERITY_RANK[severity],
        "reasons": [reason],
    }


def monitor(*, now=None, dry_run=False):
    now = now or timezone.now()
    due = businesses_due_for_reminder(now=now)
    sent = 0
    if not dry_run:
        for business in due:
            if send_owner_reminder(business, now=now):
                sent += 1
    return {
        "reminders_due": len(due),
        "reminders_sent": sent,
        "exceptions": len(verification_exceptions(now=now)),
    }
