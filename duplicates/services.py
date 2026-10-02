"""
Writes for duplicate flags. Detection only ever creates or updates flags;
listings themselves are never changed or deleted here.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from businesses.models import Business
from products.models import Product

from .detection import find_business_matches, find_product_matches
from .models import DuplicateFlag


def _pair_fields(kind, pk_1, pk_2):
    a_pk, b_pk = sorted((pk_1, pk_2))
    if kind == DuplicateFlag.Kind.BUSINESS:
        return {"kind": kind, "business_a_id": a_pk, "business_b_id": b_pk}
    return {"kind": kind, "product_a_id": a_pk, "product_b_id": b_pk}


def _other_pk(flag, pk):
    if flag.kind == DuplicateFlag.Kind.BUSINESS:
        return flag.business_b_id if flag.business_a_id == pk else flag.business_a_id
    return flag.product_b_id if flag.product_a_id == pk else flag.product_a_id


def _upsert_flag(kind, subject_pk, match):
    reasons = [signal.as_dict() for signal in match.signals]
    now = timezone.now()
    flag, created = DuplicateFlag.objects.get_or_create(
        **_pair_fields(kind, subject_pk, match.other_pk),
        defaults={"score": match.score, "reasons": reasons, "last_detected_at": now},
    )
    if created:
        return flag

    flag.score = match.score
    flag.reasons = reasons
    flag.last_detected_at = now
    if flag.status == DuplicateFlag.Status.DISTINCT:
        new_identifiers = {
            s.code for s in match.signals if s.identifier
        } - set(flag.reviewed_signal_codes or [])
        if new_identifiers:
            flag.status = DuplicateFlag.Status.OPEN
    flag.save(update_fields=["score", "reasons", "last_detected_at", "status"])
    return flag


def _sync_flags(kind, subject, *, is_listed, find_matches):
    """
    Upsert flags for current matches and drop unreviewed flags that no longer
    match (e.g. after a name was corrected). Reviewed flags are kept.
    """
    open_flags = list(DuplicateFlag.objects.open().for_object(subject))
    if not is_listed:
        DuplicateFlag.objects.filter(pk__in=[f.pk for f in open_flags]).delete()
        return []

    flagged_pks = {_other_pk(flag, subject.pk) for flag in open_flags}
    matches = find_matches(subject, extra_pks=flagged_pks)
    flags = [_upsert_flag(kind, subject.pk, match) for match in matches]

    matched_pks = {match.other_pk for match in matches}
    stale = [f.pk for f in open_flags if _other_pk(f, subject.pk) not in matched_pks]
    if stale:
        DuplicateFlag.objects.filter(pk__in=stale).delete()
    return flags


@transaction.atomic
def flag_product_duplicates(product):
    """Detect and record possible duplicates of one product. Returns its flags."""
    product = (
        Product.objects.select_related("image")
        .prefetch_related("variants", "images__image")
        .filter(pk=getattr(product, "pk", product))
        .first()
    )
    if product is None:
        return []
    return _sync_flags(
        DuplicateFlag.Kind.PRODUCT,
        product,
        is_listed=product.status != Product.ProductStatus.ARCHIVED,
        find_matches=find_product_matches,
    )


@transaction.atomic
def flag_business_duplicates(business):
    """Detect and record possible duplicates of one business. Returns its flags."""
    business = (
        Business.objects.select_related("logo")
        .filter(pk=getattr(business, "pk", business))
        .first()
    )
    if business is None:
        return []
    return _sync_flags(
        DuplicateFlag.Kind.BUSINESS,
        business,
        is_listed=business.is_active,
        find_matches=find_business_matches,
    )


@dataclass
class ScanResult:
    businesses_checked: int = 0
    products_checked: int = 0
    open_flags: int = 0


def scan_for_duplicates(*, businesses=True, products=True):
    """Re-check every listing. Safe to run repeatedly (e.g. nightly)."""
    result = ScanResult()
    if businesses:
        for pk in Business.objects.values_list("pk", flat=True).iterator():
            flag_business_duplicates(pk)
            result.businesses_checked += 1
    if products:
        for pk in Product.objects.values_list("pk", flat=True).iterator():
            flag_product_duplicates(pk)
            result.products_checked += 1
    result.open_flags = DuplicateFlag.objects.open().count()
    return result


def review_flag(flag, *, status, user=None, notes=""):
    """Record a reviewer's decision. Never edits or deletes the listings."""
    if status not in DuplicateFlag.Status.values:
        raise ValueError(f"Unknown duplicate status: {status}")
    flag.status = status
    flag.review_notes = notes or ""
    if status == DuplicateFlag.Status.OPEN:
        flag.reviewed_by = None
        flag.reviewed_at = None
        flag.reviewed_signal_codes = []
    else:
        flag.reviewed_by = user
        flag.reviewed_at = timezone.now()
        flag.reviewed_signal_codes = [r.get("code") for r in flag.reasons or []]
    flag.save(
        update_fields=[
            "status",
            "review_notes",
            "reviewed_by",
            "reviewed_at",
            "reviewed_signal_codes",
        ]
    )
    return flag
