from django.db import models
from django.urls import reverse
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel
from wagtail.images import get_image_model
from wagtail.models import Orderable


class Product(ClusterableModel):
    class ProductStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class OriginType(models.TextChoices):
        MADE_IN_ZIMBABWE = (
            "made_in_zimbabwe",
            "Made in Zimbabwe",
        )
        GROWN_IN_ZIMBABWE = (
            "grown_in_zimbabwe",
            "Grown in Zimbabwe",
        )
        PACKAGED_IN_ZIMBABWE = (
            "packaged_in_zimbabwe",
            "Packaged in Zimbabwe",
        )
        BRANDED_IN_ZIMBABWE = (
            "branded_in_zimbabwe",
            "Branded in Zimbabwe",
        )
        SUPPORT_IMAGE_OF_ZIMBABWE = (
            "support_image_of_zimbabwe",
            "Support Image of Zimbabwe",
        )
        OTHER = "other", "Other"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(
        max_length=250,
    )

    slug = models.SlugField(
        max_length=280,
        unique=True,
    )

    short_description = models.CharField(
        max_length=300,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.PROTECT,
        related_name="products",
    )

    origin_type = models.CharField(
        max_length=30,
        choices=OriginType,
        default=OriginType.MADE_IN_ZIMBABWE,
    )

    country_of_origin = models.CharField(
        max_length=100,
        default="Zimbabwe",
    )

    brand_name = models.CharField(
        max_length=200,
        blank=True,
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
    )

    barcode = models.CharField(
        max_length=100,
        blank=True,
    )

    size_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    size_unit = models.CharField(
        max_length=30,
        blank=True,
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ProductStatus,
        default=ProductStatus.PUBLISHED,
    )

    featured = models.BooleanField(
        default=False,
    )

    image = models.ForeignKey(
        get_image_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_main_images",
    )

    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        default=timezone.now,
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
            "products:detail",
            kwargs={"slug": self.slug},
        )


class ProductImage(Orderable):
    product = ParentalKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ForeignKey(
        get_image_model(),
        on_delete=models.CASCADE,
        related_name="product_gallery_images",
    )

    alt_text = models.CharField(
        max_length=200,
        blank=True,
    )

    is_primary = models.BooleanField(
        default=False,
    )

    panels = [
        FieldPanel("image"),
        FieldPanel("alt_text"),
        FieldPanel("is_primary"),
    ]

    class Meta(Orderable.Meta):
        pass
