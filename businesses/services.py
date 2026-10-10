"""Saves businesses and products submitted through the Simudza owner dashboard."""

from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model

from products.forms import save_product_with_unique_slug
from products.models import Product
from products.services import upsert_default_variant
from simudza.utils.collections import business_logo_collection

from .models import Business, save_business_with_unique_slug
from .verification.levels import VerificationLevel, is_trusted_level
from .verification.workflow import notify_superusers_of_owner_edit


def _apply_listing_trust(listing, business, *, user):
    """
    Set verification fields on a business or product after an owner write.
    Owners never grant Simudza Verified: a confirmed owner's edit counts as
    Information source checked. Returns True when the edit took a Simudza
    Verified listing down, so a superuser must re-verify it.
    """
    was_simudza_verified = (
        listing.pk is not None
        and listing.verification_level == VerificationLevel.SIMUDZA_VERIFIED
    )
    if business.is_confirmed_owner(user):
        listing.verified_at = timezone.now()
        listing.verified_by = user
        listing.verification_level = VerificationLevel.SOURCE_VERIFIED
        listing.verification_reference = ""
        if isinstance(listing, Business):
            listing.verification_reminder_sent_at = None
    elif is_trusted_level(listing.verification_level):
        listing.verification_level = VerificationLevel.COMMUNITY_REPORTED
    return was_simudza_verified


def _notify_superusers_after_commit(listing, user):
    transaction.on_commit(lambda: notify_superusers_of_owner_edit(listing, user))


def _wagtail_image_from_upload(upload, *, title, user, collection=None):
    if not upload:
        return None
    Image = get_image_model()
    image = Image(title=(title or upload.name)[:255], uploaded_by_user=user)
    if collection is not None:
        image.collection = collection
    upload.seek(0)
    image.file = upload
    image._set_image_file_metadata()
    image.save()
    return image


def _require_business_owner(business, user):
    if business.owner_id != user.pk:
        raise PermissionError("You can only edit companies you own.")


def _require_product_owner(product, user):
    if product.business.owner_id != user.pk:
        raise PermissionError("You can only edit products you own.")


@transaction.atomic
def owner_save_company(user, data, *, business=None, logo_upload=None):
    """
    Create or update a Business from owner dashboard data.
    ``data`` is a dict of Business field values (from a form's cleaned_data).
    """
    from history.context import change_context
    from history.models import ChangeLog

    creating = business is None
    if not creating:
        _require_business_owner(business, user)

    with change_context(user=user, source=ChangeLog.Source.SUBMISSION):
        if creating:
            business = Business(
                owner=user,
                verification_level=VerificationLevel.UNVERIFIED,
                verified_at=None,
                is_active=False,
            )
        business.name = data.get("name") or business.name
        if data.get("business_type"):
            business.business_type = data["business_type"]
        if "description" in data:
            business.description = data.get("description") or ""
        if "website" in data:
            business.website = data.get("website") or ""
        if "email" in data:
            business.email = data.get("email") or ""
        if "phone" in data:
            business.phone = data.get("phone") or ""
        if "address" in data:
            business.address = data.get("address") or ""
        if "town_or_city" in data:
            business.town_or_city = data.get("town_or_city") or ""
        logo = _wagtail_image_from_upload(
            logo_upload,
            title=f"{business.name} logo",
            user=user,
            collection=business_logo_collection() if logo_upload else None,
        )
        if logo:
            business.logo = logo
        needs_reverification = _apply_listing_trust(business, business, user=user)
        if creating or not business.slug:
            save_business_with_unique_slug(business)
        else:
            business.save()
    if needs_reverification:
        _notify_superusers_after_commit(business, user)
    return business


@transaction.atomic
def owner_save_product(user, business, data, *, product=None, image_upload=None):
    """
    Create or update a Product (and default variant) for an owned business.
    """
    from history.context import change_context
    from history.models import ChangeLog

    _require_business_owner(business, user)
    creating = product is None
    if not creating:
        _require_product_owner(product, user)
        if product.business_id != business.pk:
            raise PermissionError("That product does not belong to the selected company.")

    with change_context(user=user, source=ChangeLog.Source.SUBMISSION):
        if creating:
            if not data.get("category"):
                raise ValueError("New products require a category.")
            product = Product(
                business=business,
                name=data["name"],
                short_description=data.get("short_description") or "",
                description=data.get("description") or "",
                category=data["category"],
                origin_type=data.get("origin_type") or Product.OriginType.MADE_IN_ZIMBABWE,
                brand_name=data.get("brand_name") or "",
                status=Product.ProductStatus.PENDING,
            )
        else:
            if data.get("name"):
                product.name = data["name"]
            if "short_description" in data:
                product.short_description = data.get("short_description") or ""
            if "description" in data:
                product.description = data.get("description") or ""
            if data.get("category"):
                product.category = data["category"]
            if data.get("origin_type"):
                product.origin_type = data["origin_type"]
            if "brand_name" in data:
                product.brand_name = data.get("brand_name") or ""

        image = _wagtail_image_from_upload(
            image_upload,
            title=product.name,
            user=user,
        )
        if image:
            product.image = image
        needs_reverification = _apply_listing_trust(product, business, user=user)
        if creating:
            save_product_with_unique_slug(product)
        else:
            product.save()
        upsert_default_variant(
            product,
            sku=data.get("sku") or "",
            barcode=data.get("barcode") or "",
            size_value=data.get("size_value"),
            size_unit=data.get("size_unit") or "",
            price=data.get("price"),
        )
    if needs_reverification:
        _notify_superusers_after_commit(product, user)
    return product
