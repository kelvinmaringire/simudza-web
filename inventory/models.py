from django.core.exceptions import ValidationError
from django.db import models


class Inventory(models.Model):
    """
    Stock record for a product. One row per product, auto-created on product save.
    """

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="inventory",
    )

    quantity = models.PositiveIntegerField(
        default=0,
    )

    reserved_quantity = models.PositiveIntegerField(
        default=0,
    )

    low_stock_threshold = models.PositiveIntegerField(
        default=5,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["product__name"]
        verbose_name_plural = "inventory"

    def __str__(self):
        return f"{self.product.name} ({self.available_quantity} available)"

    @property
    def available_quantity(self):
        return max(self.quantity - self.reserved_quantity, 0)

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold

    def clean(self):
        super().clean()
        if self.reserved_quantity > self.quantity:
            raise ValidationError(
                {
                    "reserved_quantity": (
                        "Reserved quantity cannot exceed total quantity."
                    ),
                }
            )
