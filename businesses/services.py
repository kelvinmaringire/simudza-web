from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from wagtail.images import get_image_model

from products.forms import unique_product_slug
from products.models import Product

from .models import (
    Business,
    ManufacturerSubmission,
    RetailLocation,
    unique_business_slug,
)


def _wagtail_image_from_upload(upload, *, title, user):
    if not upload:
        return None
    Image = get_image_model()
    image = Image(title=(title or upload.name)[:255], uploaded_by_user=user)
    upload.seek(0)
    image.file.save(
        upload.name,
        ContentFile(upload.read()),
        save=True,
    )
    return image


@transaction.atomic
def apply_submission(submission, *, reviewer=None):
    """Write a submission onto Business / Product / RetailLocation records."""
    if submission.status == ManufacturerSubmission.Status.APPLIED:
        return submission

    kind = submission.kind
    user = submission.submitted_by

    if kind == ManufacturerSubmission.Kind.COMPANY_PROFILE:
        business = submission.business
        creating = business is None
        if creating:
            business = Business(
                owner=user,
                verification_status=Business.VerificationStatus.PENDING,
                verified_at=None,
                is_active=True,
            )
        business.name = submission.company_name or business.name
        if submission.business_type:
            business.business_type = submission.business_type
        business.description = submission.company_description
        business.website = submission.website
        business.email = submission.email
        business.phone = submission.phone
        business.address = submission.address
        business.town_or_city = submission.town_or_city
        if not business.slug or creating:
            business.slug = unique_business_slug(
                business.name,
                exclude_pk=business.pk,
            )
        if creating and business.owner_id is None:
            business.owner = user
        logo = _wagtail_image_from_upload(
            submission.logo_upload,
            title=f"{business.name} logo",
            user=user,
        )
        if logo:
            business.logo = logo
        business.save()
        submission.business = business

    elif kind == ManufacturerSubmission.Kind.NEW_PRODUCT:
        if submission.business_id is None:
            raise ValueError("New product submissions require a business.")
        if submission.category_id is None:
            raise ValueError("New product submissions require a category.")
        product = Product(
            business=submission.business,
            name=submission.product_name,
            short_description=submission.short_description,
            description=submission.product_description,
            category=submission.category,
            origin_type=(
                submission.origin_type or Product.OriginType.MADE_IN_ZIMBABWE
            ),
            brand_name=submission.brand_name,
            sku=submission.sku,
            barcode=submission.barcode,
            size_value=submission.size_value,
            size_unit=submission.size_unit,
            price=submission.price,
            status=Product.ProductStatus.PENDING,
            slug=unique_product_slug(submission.product_name),
        )
        image = _wagtail_image_from_upload(
            submission.product_image_upload,
            title=submission.product_name,
            user=user,
        )
        if image:
            product.image = image
        product.save()
        submission.product = product

    elif kind == ManufacturerSubmission.Kind.PRODUCT_UPDATE:
        product = submission.product
        if product is None:
            raise ValueError("Product update submissions require a product.")
        if submission.product_name:
            product.name = submission.product_name
        product.short_description = submission.short_description
        product.description = submission.product_description
        if submission.category_id:
            product.category = submission.category
        if submission.origin_type:
            product.origin_type = submission.origin_type
        product.brand_name = submission.brand_name
        product.sku = submission.sku
        product.barcode = submission.barcode
        product.size_value = submission.size_value
        product.size_unit = submission.size_unit
        product.price = submission.price
        image = _wagtail_image_from_upload(
            submission.product_image_upload,
            title=product.name,
            user=user,
        )
        if image:
            product.image = image
        product.save()

    elif kind == ManufacturerSubmission.Kind.RETAIL_LOCATION:
        if submission.business_id is None:
            raise ValueError("Retail location submissions require a business.")
        location = submission.retail_location or RetailLocation(
            business=submission.business,
        )
        location.business = submission.business
        location.name = submission.location_name
        location.address = submission.location_address
        location.town_or_city = submission.location_town_or_city
        location.phone = submission.location_phone
        location.notes = submission.location_notes
        location.is_active = True
        location.save()
        submission.retail_location = location

    else:
        raise ValueError(f"Unsupported submission kind: {kind}")

    submission.status = ManufacturerSubmission.Status.APPLIED
    submission.applied_at = timezone.now()
    if reviewer is not None:
        submission.reviewed_by = reviewer
    submission.save()
    return submission
