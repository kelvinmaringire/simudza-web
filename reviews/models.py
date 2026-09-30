from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ReportReason(models.TextChoices):
    PRODUCT_DISCONTINUED = "product_discontinued", "Product discontinued"
    NOT_MADE_IN_ZIMBABWE = "not_made_in_zimbabwe", "No longer made in Zimbabwe"
    BUSINESS_CLOSED = "business_closed", "Business closed"
    PRICE_INCORRECT = "price_incorrect", "Price incorrect"
    PRODUCT_UNAVAILABLE = "product_unavailable", "Product unavailable"
    WRONG_CONTACT_DETAILS = "wrong_contact_details", "Wrong contact details"
    DUPLICATE_LISTING = "duplicate_listing", "Duplicate listing"


PRODUCT_REPORT_REASONS = tuple(ReportReason.choices)

BUSINESS_REPORT_REASONS = (
    (ReportReason.BUSINESS_CLOSED, ReportReason.BUSINESS_CLOSED.label),
    (ReportReason.WRONG_CONTACT_DETAILS, ReportReason.WRONG_CONTACT_DETAILS.label),
    (ReportReason.DUPLICATE_LISTING, ReportReason.DUPLICATE_LISTING.label),
    (ReportReason.NOT_MADE_IN_ZIMBABWE, ReportReason.NOT_MADE_IN_ZIMBABWE.label),
)


class ReportStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


class ProductReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_reviews",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    reason = models.CharField(
        max_length=40,
        choices=ReportReason.choices,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.OPEN,
    )
    guest_name = models.CharField(max_length=120, blank=True)
    guest_email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                condition=Q(user__isnull=False, reason=""),
                name="unique_user_product_review",
            ),
        ]

    def __str__(self):
        if self.is_report:
            return f"Report on {self.product}: {self.get_reason_display()}"
        rating = self.rating if self.rating is not None else "?"
        return f"{self.reporter_display} on {self.product} ({rating}/5)"

    @property
    def is_report(self):
        return bool(self.reason)

    @property
    def reporter_display(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.get_username()
        if self.guest_name.strip():
            return self.guest_name.strip()
        return "Anonymous"

    def clean(self):
        super().clean()
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})


class BusinessReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_reviews",
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    reason = models.CharField(
        max_length=40,
        choices=ReportReason.choices,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.OPEN,
    )
    guest_name = models.CharField(max_length=120, blank=True)
    guest_email = models.EmailField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business"],
                condition=Q(user__isnull=False, reason=""),
                name="unique_user_business_review",
            ),
        ]

    def __str__(self):
        if self.is_report:
            return f"Report on {self.business}: {self.get_reason_display()}"
        rating = self.rating if self.rating is not None else "?"
        return f"{self.reporter_display} on {self.business} ({rating}/5)"

    @property
    def is_report(self):
        return bool(self.reason)

    @property
    def reporter_display(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.get_username()
        if self.guest_name.strip():
            return self.guest_name.strip()
        return "Anonymous"

    def clean(self):
        super().clean()
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})
