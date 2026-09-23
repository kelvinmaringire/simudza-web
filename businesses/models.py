from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from wagtail.images import get_image_model


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

    name = models.CharField(max_length=200)

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

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    province = models.CharField(
        max_length=100,
        blank=True,
    )

    country = models.CharField(
        max_length=100,
        default="Zimbabwe",
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