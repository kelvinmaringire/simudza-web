from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ProductReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_reviews",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_user_product_review",
            ),
        ]

    def __str__(self):
        return f"{self.user} on {self.product} ({self.rating}/5)"

    def clean(self):
        super().clean()
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})


class BusinessReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="business_reviews",
    )
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business"],
                name="unique_user_business_review",
            ),
        ]

    def __str__(self):
        return f"{self.user} on {self.business} ({self.rating}/5)"

    def clean(self):
        super().clean()
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})
