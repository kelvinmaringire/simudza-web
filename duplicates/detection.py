"""
Duplicate scoring for businesses and products.

Pure comparison logic: build a profile from a record, compare two profiles,
get back a score and the signals that matched. No writes happen here; see
`duplicates.services` for flag persistence.

Context signals (same manufacturer, brand, category, size, image) add
confidence but never flag a pair on their own: a pair needs a close name match
or a hard identifier (barcode, SKU, website, phone, email). That keeps
"Mazoe Raspberry" and "Mazoe Blackberry" apart while still catching
"Coca-Cola" vs "Coca Cola 500ml".
"""

from dataclasses import dataclass, field

from django.db.models import Q

from businesses.models import Business
from products.models import Product

from .normalize import (
    business_name_key,
    canonical_size,
    email_domain,
    fold,
    name_similarity,
    normalize_barcode,
    normalize_phones,
    normalize_sku,
    product_name_key,
    website_key,
)

FLAG_THRESHOLD = 60

SAME_NAME = 1.0
VERY_SIMILAR_NAME = 0.9
SIMILAR_NAME = 0.75


@dataclass(frozen=True)
class Signal:
    code: str
    label: str
    points: int
    detail: str = ""
    identifier: bool = False

    def as_dict(self):
        return {
            "code": self.code,
            "label": self.label,
            "points": self.points,
            "detail": self.detail,
            "identifier": self.identifier,
        }


@dataclass
class Match:
    other_pk: int
    signals: list[Signal]

    @property
    def score(self):
        return min(100, sum(signal.points for signal in self.signals))

    @property
    def is_flaggable(self):
        strong_name = any(
            s.code in {"same_name", "same_name_except_size", "very_similar_name"}
            for s in self.signals
        )
        has_identifier = any(s.identifier for s in self.signals)
        return (strong_name or has_identifier) and self.score >= FLAG_THRESHOLD


@dataclass(frozen=True)
class ProductProfile:
    pk: int | None
    name: str
    tokens: tuple
    name_sizes: frozenset
    business_id: int | None
    brand: str
    category_id: int | None
    barcodes: frozenset = field(default_factory=frozenset)
    skus: frozenset = field(default_factory=frozenset)
    variant_sizes: frozenset = field(default_factory=frozenset)
    image_hashes: frozenset = field(default_factory=frozenset)

    @property
    def sizes(self):
        return self.name_sizes | self.variant_sizes


@dataclass(frozen=True)
class BusinessProfile:
    pk: int | None
    name: str
    core_tokens: tuple
    all_tokens: tuple
    website: str
    email: str
    email_domain: str
    phones: frozenset
    town: str
    business_type: str
    logo_hash: str


def _image_hash(image):
    return (getattr(image, "file_hash", "") or "") if image else ""


def product_profile(product):
    tokens, name_sizes = product_name_key(product.name)
    variants = list(product.variants.all())
    image_hashes = {_image_hash(product.image)}
    image_hashes.update(_image_hash(item.image) for item in product.images.all())
    image_hashes.discard("")
    return ProductProfile(
        pk=product.pk,
        name=product.name,
        tokens=tokens,
        name_sizes=name_sizes,
        business_id=product.business_id,
        brand=" ".join(fold(product.brand_name).split()),
        category_id=product.category_id,
        barcodes=frozenset(
            filter(None, (normalize_barcode(v.barcode) for v in variants))
        ),
        skus=frozenset(filter(None, (normalize_sku(v.sku) for v in variants))),
        variant_sizes=frozenset(
            filter(None, (canonical_size(v.size_value, v.size_unit) for v in variants))
        ),
        image_hashes=frozenset(image_hashes),
    )


def business_profile(business):
    core_tokens, all_tokens = business_name_key(business.name)
    business_type = business.business_type
    if business_type == Business.BusinessType.OTHER:
        business_type = ""
    return BusinessProfile(
        pk=business.pk,
        name=business.name,
        core_tokens=core_tokens,
        all_tokens=all_tokens,
        website=website_key(business.website),
        email=(business.email or "").strip().lower(),
        email_domain=email_domain(business.email),
        phones=frozenset(normalize_phones(business.phone)),
        town=" ".join(fold(business.town_or_city).split()),
        business_type=business_type or "",
        logo_hash=_image_hash(business.logo),
    )


def _name_signal(similarity, contained, *, same_points, detail=""):
    if similarity >= SAME_NAME:
        return Signal("same_name", "Same name", same_points, detail)
    if similarity >= VERY_SIMILAR_NAME:
        return Signal("very_similar_name", "Very similar names", 45, detail)
    if similarity >= SIMILAR_NAME or contained:
        return Signal("similar_name", "Similar names", 20, detail)
    return None


def compare_products(a: ProductProfile, b: ProductProfile) -> Match:
    signals = []
    similarity, contained = name_similarity(a.tokens, b.tokens)
    names = f"“{a.name}” / “{b.name}”"

    if similarity >= SAME_NAME and a.name_sizes != b.name_sizes:
        sizes = ", ".join(sorted(a.name_sizes ^ b.name_sizes))
        signals.append(
            Signal(
                "same_name_except_size",
                "Same name apart from size — may be a size variant of one product",
                55,
                sizes,
            )
        )
    else:
        name_signal = _name_signal(similarity, contained, same_points=55, detail=names)
        if name_signal:
            signals.append(name_signal)

    shared_barcodes = a.barcodes & b.barcodes
    if shared_barcodes:
        signals.append(
            Signal(
                "same_barcode",
                "Same barcode",
                60,
                ", ".join(sorted(shared_barcodes)),
                identifier=True,
            )
        )

    same_business = a.business_id is not None and a.business_id == b.business_id
    if same_business:
        signals.append(Signal("same_business", "Same manufacturer / business", 15))
        shared_skus = a.skus & b.skus
        if shared_skus:
            signals.append(
                Signal(
                    "same_sku",
                    "Same SKU at the same business",
                    40,
                    ", ".join(sorted(shared_skus)),
                    identifier=True,
                )
            )

    if a.brand and a.brand == b.brand:
        signals.append(Signal("same_brand", "Same brand", 10, a.brand))

    if a.category_id is not None and a.category_id == b.category_id:
        signals.append(Signal("same_category", "Same category", 5))

    shared_sizes = a.sizes & b.sizes
    if shared_sizes:
        signals.append(
            Signal("same_size", "Same pack size", 10, ", ".join(sorted(shared_sizes)))
        )

    if a.image_hashes & b.image_hashes:
        signals.append(Signal("same_image", "Same image file", 30))

    return Match(other_pk=b.pk, signals=signals)


def compare_businesses(a: BusinessProfile, b: BusinessProfile) -> Match:
    signals = []
    similarity, contained = name_similarity(a.core_tokens, b.core_tokens)
    detail = f"“{a.name}” / “{b.name}”"
    if similarity >= SAME_NAME and a.all_tokens != b.all_tokens:
        detail += " — ignoring legal suffixes and country words"
    name_signal = _name_signal(similarity, contained, same_points=60, detail=detail)
    if name_signal:
        signals.append(name_signal)

    same_website = bool(a.website) and a.website == b.website
    if same_website:
        signals.append(
            Signal("same_website", "Same website", 60, a.website, identifier=True)
        )
    if a.email and a.email == b.email:
        signals.append(Signal("same_email", "Same email", 60, a.email, identifier=True))
    elif not same_website:
        shared_domains = ({a.website, a.email_domain} & {b.website, b.email_domain}) - {""}
        if shared_domains:
            signals.append(
                Signal(
                    "same_domain",
                    "Same web / email domain",
                    30,
                    ", ".join(sorted(shared_domains)),
                    identifier=True,
                )
            )

    shared_phones = a.phones & b.phones
    if shared_phones:
        signals.append(
            Signal(
                "same_phone",
                "Same phone number",
                60,
                ", ".join(sorted(shared_phones)),
                identifier=True,
            )
        )

    if a.logo_hash and a.logo_hash == b.logo_hash:
        signals.append(Signal("same_logo", "Same logo file", 30))
    if a.town and a.town == b.town:
        signals.append(Signal("same_town", "Same town / city", 5, a.town))
    if a.business_type and a.business_type == b.business_type:
        signals.append(Signal("same_type", "Same business type", 5))

    return Match(other_pk=b.pk, signals=signals)


def _prefix_filters(field_name, tokens):
    query = Q()
    for token in tokens:
        if token.isdigit() or len(token) < 3:
            continue
        query |= Q(**{f"{field_name}__icontains": token[:4]})
    return query


def product_candidates(product, profile, *, extra_pks=()):
    """Cheap database prefilter: only these rows are scored in Python."""
    query = Q(business_id=product.business_id) | _prefix_filters("name", profile.tokens)
    if product.brand_name:
        query |= Q(brand_name__iexact=product.brand_name.strip())
    raw_barcodes = [v.barcode for v in product.variants.all() if v.barcode]
    if raw_barcodes:
        query |= Q(variants__barcode__in=raw_barcodes)
    for barcode in profile.barcodes:
        query |= Q(variants__barcode__endswith=barcode)
    if profile.image_hashes:
        query |= Q(image__file_hash__in=list(profile.image_hashes))
    if extra_pks:
        query |= Q(pk__in=list(extra_pks))
    ids = (
        Product.objects.filter(query)
        .exclude(pk=product.pk)
        .exclude(status=Product.ProductStatus.ARCHIVED)
        .values_list("pk", flat=True)
        .distinct()
    )
    return (
        Product.objects.filter(pk__in=list(ids))
        .select_related("image")
        .prefetch_related("variants", "images__image")
    )


def business_candidates(business, profile, *, extra_pks=()):
    query = _prefix_filters("name", profile.core_tokens)
    if profile.website:
        query |= Q(website__icontains=profile.website)
    if profile.email_domain:
        query |= Q(email__iendswith=profile.email_domain)
        query |= Q(website__icontains=profile.email_domain)
    if business.email:
        query |= Q(email__iexact=business.email.strip())
    for phone in profile.phones:
        query |= Q(phone__contains=phone[-6:])
    if profile.logo_hash:
        query |= Q(logo__file_hash=profile.logo_hash)
    if extra_pks:
        query |= Q(pk__in=list(extra_pks))
    if not query:
        return Business.objects.none()
    return (
        Business.objects.filter(query, is_active=True)
        .exclude(pk=business.pk)
        .select_related("logo")
    )


def find_product_matches(product, *, extra_pks=()):
    """Matches worth flagging for `product`, strongest first."""
    profile = product_profile(product)
    matches = [
        compare_products(profile, product_profile(other))
        for other in product_candidates(product, profile, extra_pks=extra_pks)
    ]
    return sorted(
        (m for m in matches if m.is_flaggable), key=lambda m: m.score, reverse=True
    )


def find_business_matches(business, *, extra_pks=()):
    profile = business_profile(business)
    matches = [
        compare_businesses(profile, business_profile(other))
        for other in business_candidates(business, profile, extra_pks=extra_pks)
    ]
    return sorted(
        (m for m in matches if m.is_flaggable), key=lambda m: m.score, reverse=True
    )
