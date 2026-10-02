from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class DuplicateFlagQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=DuplicateFlag.Status.OPEN)

    def for_object(self, obj):
        if obj._meta.label == "businesses.Business":
            return self.filter(Q(business_a=obj) | Q(business_b=obj))
        return self.filter(Q(product_a=obj) | Q(product_b=obj))


class DuplicateFlag(models.Model):
    """
    A pair of listings that may describe the same real-world entity.

    Flags are never acted on automatically: a reviewer decides whether the
    pair is a duplicate. "Not a duplicate" decisions are kept so re-scans do
    not raise the same pair again.
    """

    class Kind(models.TextChoices):
        BUSINESS = "business", "Business"
        PRODUCT = "product", "Product"

    class Status(models.TextChoices):
        OPEN = "open", "Needs review"
        DUPLICATE = "duplicate", "Confirmed duplicate"
        DISTINCT = "distinct", "Not a duplicate"

    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True)

    # Pairs are stored with the lower primary key in the "a" slot.
    business_a = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    business_b = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    product_a = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    product_b = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )

    score = models.PositiveSmallIntegerField(
        help_text="Detection confidence, 0–100.",
    )
    reasons = models.JSONField(
        default=list,
        blank=True,
        help_text="Signals that matched, e.g. similar name or same barcode.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        help_text=(
            "Reviewing never changes or deletes either listing. Archive or "
            "edit the extra listing yourself if this is a duplicate."
        ),
    )
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_signal_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="Signals present at review time; new strong signals reopen the flag.",
    )

    detected_at = models.DateTimeField(auto_now_add=True)
    last_detected_at = models.DateTimeField(default=timezone.now)

    objects = DuplicateFlagQuerySet.as_manager()

    class Meta:
        ordering = ["-score", "-last_detected_at"]
        verbose_name = "possible duplicate"
        verbose_name_plural = "possible duplicates"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="business",
                        business_a__isnull=False,
                        business_b__isnull=False,
                        product_a__isnull=True,
                        product_b__isnull=True,
                        business_a__lt=F("business_b"),
                    )
                    | Q(
                        kind="product",
                        product_a__isnull=False,
                        product_b__isnull=False,
                        business_a__isnull=True,
                        business_b__isnull=True,
                        product_a__lt=F("product_b"),
                    )
                ),
                name="duplicateflag_ordered_pair_matches_kind",
            ),
            models.UniqueConstraint(
                fields=["business_a", "business_b"],
                condition=Q(kind="business"),
                name="unique_duplicateflag_business_pair",
            ),
            models.UniqueConstraint(
                fields=["product_a", "product_b"],
                condition=Q(kind="product"),
                name="unique_duplicateflag_product_pair",
            ),
        ]

    def __str__(self):
        return f"{self.left} ↔ {self.right}"

    @property
    def left(self):
        return self.business_a if self.kind == self.Kind.BUSINESS else self.product_a

    @property
    def right(self):
        return self.business_b if self.kind == self.Kind.BUSINESS else self.product_b

    def other(self, obj):
        return self.right if self.left == obj else self.left

    @property
    def reason_summary(self):
        parts = []
        for reason in self.reasons or []:
            detail = reason.get("detail")
            label = reason.get("label", "")
            parts.append(f"{label} ({detail})" if detail else label)
        return "; ".join(parts)
