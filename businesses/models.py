from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from wagtail.images import get_image_model


def unique_business_slug(name, *, exclude_pk=None):
    base = slugify(name) or "business"
    candidate = base
    suffix = 2
    queryset = Business.objects.all()
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


class Business(models.Model):
    class BusinessType(models.TextChoices):
        MANUFACTURER = "manufacturer", "Manufacturer"
        FARMER = "farmer", "Farmer"
        PRODUCER = "producer", "Producer"
        RETAILER = "retailer", "Retailer"
        WHOLESALER = "wholesaler", "Wholesaler"
        SERVICE = "service", "Service"
        BRAND = "brand", "Brand"
        OTHER = "other", "Other"

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=200, db_index=True)

    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
    )

    business_type = models.CharField(
        max_length=30,
        choices=BusinessType.choices,
        default=BusinessType.OTHER,
    )

    description = models.TextField(blank=True)

    logo = models.ForeignKey(
        get_image_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_logos",
    )

    website = models.URLField(blank=True)

    email = models.EmailField(blank=True)

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    address = models.TextField(blank=True)

    town_or_city = models.CharField(
        max_length=100,
        blank=True,
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.VERIFIED,
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        default=timezone.now,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_businesses",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "businesses:detail",
            kwargs={"slug": self.slug},
        )


class RetailLocation(models.Model):
    """Where a business’s products can be bought (stores, markets, depots)."""

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="retail_locations",
    )

    name = models.CharField(
        max_length=200,
        help_text="Store, market, or outlet name.",
    )

    address = models.TextField(blank=True)

    town_or_city = models.CharField(
        max_length=100,
        blank=True,
    )

    phone = models.CharField(
        max_length=50,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
        help_text="Opening hours, stock notes, or other details.",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["town_or_city", "name"]

    def __str__(self):
        if self.town_or_city:
            return f"{self.name} ({self.town_or_city})"
        return self.name


class ManufacturerSubmission(models.Model):
    """
    Manufacturer/business submission for company, product, or retail updates.
    Owner submissions are applied immediately; others stay pending for review.
    """

    class Kind(models.TextChoices):
        COMPANY_PROFILE = "company_profile", "Company profile"
        NEW_PRODUCT = "new_product", "New product"
        PRODUCT_UPDATE = "product_update", "Product update"
        RETAIL_LOCATION = "retail_location", "Retail location"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"

    kind = models.CharField(
        max_length=30,
        choices=Kind.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="manufacturer_submissions",
    )

    business = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )

    retail_location = models.ForeignKey(
        RetailLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )

    company_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(
        max_length=30,
        choices=Business.BusinessType.choices,
        blank=True,
    )
    company_description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    town_or_city = models.CharField(max_length=100, blank=True)
    logo_upload = models.ImageField(
        upload_to="submissions/logos/",
        blank=True,
        null=True,
    )

    product_name = models.CharField(max_length=250, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    product_description = models.TextField(blank=True)
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    origin_type = models.CharField(max_length=30, blank=True)
    brand_name = models.CharField(max_length=200, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    size_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    size_unit = models.CharField(max_length=30, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    product_image_upload = models.ImageField(
        upload_to="submissions/products/",
        blank=True,
        null=True,
    )

    location_name = models.CharField(max_length=200, blank=True)
    location_address = models.TextField(blank=True)
    location_town_or_city = models.CharField(max_length=100, blank=True)
    location_phone = models.CharField(max_length=50, blank=True)
    location_notes = models.TextField(blank=True)

    submitter_notes = models.TextField(
        blank=True,
        help_text="Anything reviewers should know.",
    )
    review_notes = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_manufacturer_submissions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.get_status_display()}"

    def can_auto_apply(self, user=None):
        user = user or self.submitted_by
        if self.kind == self.Kind.COMPANY_PROFILE:
            if self.business_id is None:
                return True
            return self.business.owner_id == user.id
        if self.kind in {self.Kind.NEW_PRODUCT, self.Kind.RETAIL_LOCATION}:
            return bool(
                self.business_id and self.business.owner_id == user.id
            )
        if self.kind == self.Kind.PRODUCT_UPDATE:
            return bool(
                self.product_id
                and self.product.business.owner_id == user.id
            )
        return False
