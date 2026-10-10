from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Q
from django.urls import reverse
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.images import get_image_model

from simudza.utils.slugs import save_with_unique_slug, unique_slug

from .videos import BusinessVideoKind, VideoLink
from .verification.levels import (
    LifecycleStatus,
    VerificationLevel,
    freshness_for,
    is_trusted_level,
    level_meta,
    searchable_q,
)


def unique_business_slug(name, *, exclude_pk=None):
    return unique_slug(Business, name, fallback="business", exclude_pk=exclude_pk)


def save_business_with_unique_slug(business, *, name=None, save=None):
    return save_with_unique_slug(
        business, name or business.name, fallback="business", save=save
    )


def business_served_q(prefix=""):
    """Record state: is_active=False takes the listing (and its products) offline."""
    return Q(**{f"{prefix}is_active": True})


def business_searchable_q(prefix=""):
    return business_served_q(prefix) & searchable_q(prefix)


class BusinessQuerySet(models.QuerySet):
    def served(self):
        return self.filter(business_served_q())

    def visible_in_search(self):
        return self.filter(business_searchable_q())


class Business(ClusterableModel):
    class BusinessType(models.TextChoices):
        MANUFACTURER = "manufacturer", "Manufacturer"
        SERVICE_PROVIDER = "service_provider", "Service Provider"
        OTHER = "other", "Other"

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

    verification_level = models.CharField(
        max_length=30,
        choices=VerificationLevel.choices,
        default=VerificationLevel.UNVERIFIED,
        db_index=True,
    )

    verification_reference = models.CharField(
        max_length=300,
        blank=True,
        help_text="Source name or URL when level is Information source checked.",
    )

    lifecycle_status = models.CharField(
        max_length=20,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.ACTIVE,
        db_index=True,
        help_text=(
            "Discontinued keeps the page online with a notice but removes the "
            "business and its products from search."
        ),
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    verification_reminder_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time the owner was emailed to re-confirm listings.",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_businesses",
    )

    confirmed_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text=(
            "User whose ownership staff confirmed. A confirmed owner's edits "
            "count as Information source checked; only superusers grant "
            "Simudza Verified."
        ),
    )

    owner_confirmed_at = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Untick to take this listing and its products offline (pages return "
            "404). To record that the company has stopped trading, set the "
            "lifecycle status to Discontinued instead."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    quality_score = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
    )
    quality_issues = models.JSONField(default=list, blank=True)
    quality_checked_at = models.DateTimeField(null=True, blank=True)

    objects = BusinessQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "business"
        verbose_name_plural = "businesses"
        indexes = [
            GinIndex(
                fields=["quality_issues"],
                name="business_quality_issues_gin",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def freshness(self):
        return freshness_for(self.verified_at)

    @property
    def level_meta(self):
        return level_meta(self.verification_level)

    @property
    def is_trusted(self):
        return is_trusted_level(self.verification_level)

    @property
    def is_discontinued(self):
        return self.lifecycle_status == LifecycleStatus.DISCONTINUED

    @property
    def owner_is_confirmed(self):
        return self.owner_id is not None and self.owner_id == self.confirmed_owner_id

    def is_confirmed_owner(self, user):
        return (
            user is not None
            and user.pk is not None
            and self.owner_is_confirmed
            and self.owner_id == user.pk
        )

    def get_absolute_url(self):
        return reverse(
            "businesses:detail",
            kwargs={"slug": self.slug},
        )


class BusinessVideo(VideoLink):
    business = ParentalKey(
        Business,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    kind = models.CharField(
        max_length=30,
        choices=BusinessVideoKind.choices,
        default=BusinessVideoKind.OTHER,
    )

    class Meta(VideoLink.Meta):
        verbose_name = "business video"
        verbose_name_plural = "business videos"

