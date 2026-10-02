from django.db import models
from django.db.models import Count, F, Min, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from django.conf import settings

from businesses.videos import VideoLink
from businesses.verification import (
    VerificationLevel,
    freshness_for,
    is_trusted_level,
    level_meta,
    older_verified_at,
    search_cutoff,
)
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images import get_image_model
from wagtail.models import Orderable, Page

from .panels import VariantEditLinkPanel
from .streams import ProductClassificationStreamBlock


class ProductVariantQuerySet(models.QuerySet):
    def sellable(self):
        return self.filter(
            is_available=True,
            price__isnull=False,
            inventory__quantity__gt=F("inventory__reserved_quantity"),
        ).distinct()


class ProductQuerySet(models.QuerySet):
    def visible_in_search(self):
        cutoff = search_cutoff()
        return self.filter(
            verified_at__gte=cutoff,
            business__verified_at__gte=cutoff,
        ).exclude(
            verification_level=VerificationLevel.DISCONTINUED,
        ).exclude(
            business__verification_level=VerificationLevel.DISCONTINUED,
        )

    def with_sellable_variants(self):
        sellable_filter = Q(
            variants__is_available=True,
            variants__price__isnull=False,
            variants__inventory__quantity__gt=F(
                "variants__inventory__reserved_quantity"
            ),
        )
        return self.annotate(
            from_price=Min("variants__price", filter=sellable_filter),
            sellable_variant_count=Count(
                "variants",
                filter=sellable_filter,
                distinct=True,
            ),
        ).filter(sellable_variant_count__gt=0)


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
        ASSEMBLED_IN_ZIMBABWE = (
            "assembled_in_zimbabwe",
            "Assembled in Zimbabwe",
        )
        SUPPORTS_ZIMBABWE = (
            "supports_zimbabwe",
            "Supports Zimbabwe",
        )
        OTHER = "other", "Other"

    ORIGIN_TYPE_HELP_TEXT = (
        "Made in Zimbabwe: substantially manufactured/processed in Zimbabwe "
        "(e.g. a biscuit manufactured and finished in Zimbabwe). "
        "Grown in Zimbabwe: the primary agricultural or plant-based raw "
        "material is produced in Zimbabwe (e.g. cotton, maize, tobacco, tea). "
        "Packaged in Zimbabwe: manufactured/produced elsewhere, but the final "
        "packaging operation occurs in Zimbabwe. "
        "Assembled in Zimbabwe: components manufactured elsewhere, final "
        "assembly happens in Zimbabwe. "
        "Supports Zimbabwe: does not meet stronger production criteria, but has "
        "a documented Zimbabwean economic/business connection. "
        "Other: does not fit the defined classifications."
    )

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.PROTECT,
        related_name="products",
    )

    name = models.CharField(
        max_length=250,
        db_index=True,
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
        help_text=ORIGIN_TYPE_HELP_TEXT,
    )

    brand_name = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
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

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
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
        help_text="Source name or URL when level is Verified source.",
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

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def effective_verified_at(self):
        business_at = None
        if self.business_id:
            business_at = self.business.verified_at
        return older_verified_at(self.verified_at, business_at)

    @property
    def freshness(self):
        return freshness_for(self.effective_verified_at)

    @property
    def effective_level(self):
        if self.business_id and (
            self.business.verification_level
            == VerificationLevel.DISCONTINUED
        ):
            return VerificationLevel.DISCONTINUED
        return self.verification_level

    @property
    def level_meta(self):
        return level_meta(self.effective_level)

    @property
    def is_trusted(self):
        return is_trusted_level(self.effective_level)

    @property
    def inherits_business_status(self):
        if not self.business_id:
            return False
        product_at = self.verified_at
        business_at = self.business.verified_at
        effective = older_verified_at(product_at, business_at)
        if effective is None:
            return False
        if business_at is None:
            return False
        if product_at is None:
            return True
        return business_at <= product_at and business_at == effective

    def get_absolute_url(self):
        return reverse(
            "products:detail",
            kwargs={"slug": self.slug},
        )

    def get_marketplace_url(self):
        return reverse(
            "marketplace:product_detail",
            kwargs={"slug": self.slug},
        )

    @property
    def sellable_variants_for_marketplace(self):
        cached = getattr(self, "sellable_variants_list", None)
        if cached is not None:
            return cached
        return list(
            self.variants.sellable()
            .select_related("inventory")
            .order_by("sort_order", "pk")
        )


class ProductVariant(ClusterableModel, Orderable):
    product = ParentalKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )

    name = models.CharField(
        max_length=200,
        blank=True,
        help_text='Optional label, e.g. "330 ml can".',
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

    packaging = models.CharField(
        max_length=200,
        blank=True,
        help_text='e.g. "PET bottle", "Can".',
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    is_available = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = ProductVariantQuerySet.as_manager()

    panels = [
        FieldPanel("name"),
        FieldPanel("size_value"),
        FieldPanel("size_unit"),
        FieldPanel("packaging"),
        FieldPanel("sku"),
        FieldPanel("barcode"),
        FieldPanel("price"),
        FieldPanel("is_available"),
        VariantEditLinkPanel(),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "product variant"
        verbose_name_plural = "product variants"
        constraints = [
            models.UniqueConstraint(
                fields=["barcode"],
                condition=~Q(barcode=""),
                name="unique_productvariant_barcode_nonempty",
            ),
            models.UniqueConstraint(
                fields=["product", "sku"],
                condition=~Q(sku=""),
                name="unique_productvariant_sku_per_product_nonempty",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.label}"

    @property
    def size_display(self):
        if not self.size_value and not self.size_unit:
            return ""
        value = ""
        if self.size_value is not None:
            value = format(self.size_value, "f").rstrip("0").rstrip(".")
        unit = self.size_unit or ""
        return f"{value} {unit}".strip()

    @property
    def label(self):
        if self.name:
            return self.name
        if self.size_display:
            return self.size_display
        return "Standard"

    @property
    def primary_image(self):
        first = self.images.select_related("image").first()
        if first:
            return first.image
        if self.product_id:
            return self.product.image
        return None


class ProductVariantImage(Orderable):
    variant = ParentalKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ForeignKey(
        get_image_model(),
        on_delete=models.CASCADE,
        related_name="product_variant_gallery_images",
    )

    alt_text = models.CharField(
        max_length=200,
        blank=True,
    )

    panels = [
        FieldPanel("image"),
        FieldPanel("alt_text"),
    ]

    class Meta(Orderable.Meta):
        pass


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


class ProductVideo(VideoLink):
    product = ParentalKey(
        Product,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    class Meta(VideoLink.Meta):
        verbose_name = "product video"
        verbose_name_plural = "product videos"


class ProductClassificationPage(Page):
    """
    Public guide explaining how Simudza classifies Zimbabwean products.
    """

    # Presentational metadata keyed by anchor — keeps StreamField content editable
    # while the page layout stays a product experience, not a doc outline.
    CLASSIFICATION_META = {
        "made-in-zimbabwe": {
            "group": "production",
            "group_label": "Production",
            "icon": "made",
            "summary": "Manufactured or substantially processed in Zimbabwe",
        },
        "grown-in-zimbabwe": {
            "group": "production",
            "group_label": "Production",
            "icon": "grown",
            "summary": "Primary agricultural material produced in Zimbabwe",
        },
        "packaged-in-zimbabwe": {
            "group": "finishing",
            "group_label": "Local finishing",
            "icon": "packaged",
            "summary": "Made elsewhere, packaged locally",
        },
        "assembled-in-zimbabwe": {
            "group": "finishing",
            "group_label": "Local finishing",
            "icon": "assembled",
            "summary": "Components made elsewhere, assembled locally",
        },
        "supports-zimbabwe": {
            "group": "economic",
            "group_label": "Economic connection",
            "icon": "supports",
            "summary": "Documented Zimbabwean economic or business connection",
        },
        "other": {
            "group": "unclassified",
            "group_label": "Unclassified",
            "icon": "other",
            "summary": "Does not fit the defined classifications",
        },
    }

    # Curated teaching examples — tags may be broader than the single DB field
    # so the page can show how multiple classifications apply in practice.
    EXAMPLE_SPECS = (
        {
            "slug": "joko",
            "tags": ("Grown in Zimbabwe", "Made in Zimbabwe"),
            "why": (
                "Tea leaf is grown on Zimbabwean estates, then processed and "
                "finished by Tanganda in Zimbabwe — both Grown and Made apply."
            ),
        },
        {
            "slug": "tanganda-tea",
            "tags": ("Grown in Zimbabwe", "Made in Zimbabwe"),
            "why": (
                "Primary agricultural material is Zimbabwean tea; manufacturing "
                "and finishing also happen in Zimbabwe."
            ),
        },
        {
            "slug": "honey",
            "tags": ("Grown in Zimbabwe", "Made in Zimbabwe"),
            "why": (
                "Harvested from Zimbabwean sources and prepared as a finished "
                "food product locally."
            ),
        },
        {
            "slug": "mazoe-orange-crush",
            "tags": ("Made in Zimbabwe",),
            "why": (
                "A finished beverage manufactured and packed in Zimbabwe — "
                "classified for substantial local processing."
            ),
        },
    )

    intro = RichTextField(
        blank=True,
        help_text="Optional intro shown above the classification guide.",
    )

    body = StreamField(
        ProductClassificationStreamBlock(),
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Product classification page"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        classifications = []
        important_note = None
        packaged = None
        assembled = None

        for block in self.body:
            if block.block_type == "important_note":
                important_note = block.value.get("text") or ""
                continue
            if block.block_type != "classification":
                continue

            title = block.value.get("title") or ""
            anchor = (block.value.get("anchor_slug") or "").strip() or slugify(title)
            if not title or not anchor:
                continue

            meta = self.CLASSIFICATION_META.get(
                anchor,
                {
                    "group": "unclassified",
                    "group_label": "Other",
                    "icon": "other",
                    "summary": block.value.get("definition") or "",
                },
            )
            item = {
                "title": title,
                "anchor": anchor,
                "definition": block.value.get("definition") or "",
                "steps": list(block.value.get("steps") or []),
                "examples": list(block.value.get("examples") or []),
                "notes": list(block.value.get("notes") or []),
                **meta,
            }
            classifications.append(item)
            if anchor == "packaged-in-zimbabwe":
                packaged = item
            elif anchor == "assembled-in-zimbabwe":
                assembled = item

        groups = []
        seen_groups = set()
        for item in classifications:
            key = item["group"]
            if key in seen_groups:
                continue
            seen_groups.add(key)
            groups.append(
                {
                    "key": key,
                    "label": item["group_label"],
                    "items": [c for c in classifications if c["group"] == key],
                }
            )

        context["important_note"] = important_note
        context["classifications"] = classifications
        context["classification_groups"] = groups
        context["packaged_classification"] = packaged
        context["assembled_classification"] = assembled
        context["classification_examples"] = self._classification_examples()
        return context

    def _classification_examples(self):
        slugs = [spec["slug"] for spec in self.EXAMPLE_SPECS]
        products = {
            product.slug: product
            for product in Product.objects.filter(
                status=Product.ProductStatus.PUBLISHED,
                slug__in=slugs,
            ).select_related("business", "image", "category")
        }
        examples = []
        for spec in self.EXAMPLE_SPECS:
            product = products.get(spec["slug"])
            if not product:
                continue
            examples.append(
                {
                    "product": product,
                    "tags": list(spec["tags"]),
                    "why": spec["why"],
                }
            )
        return examples

