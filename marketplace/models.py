import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page

from marketplace.cart_lifecycle import CartStatus, lifecycle_status_for_cart


class CartQuerySet(models.QuerySet):
    def open(self):
        return self.filter(
            converted_at__isnull=True,
            merged_into__isnull=True,
        )

    def with_value(self):
        return self.annotate(
            cart_value=Coalesce(
                Sum(
                    F("items__quantity") * F("items__price_snapshot"),
                    filter=Q(items__removed_at__isnull=True),
                ),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

    def with_lifecycle(self, *, now=None):
        from marketplace.cart_lifecycle import annotate_lifecycle

        return annotate_lifecycle(self, now=now)


class Cart(ClusterableModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
    )
    token = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    last_activity_at = models.DateTimeField(default=timezone.now)
    converted_at = models.DateTimeField(null=True, blank=True)
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_from",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CartQuerySet.as_manager()

    class Meta:
        ordering = ["-last_activity_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(
                    converted_at__isnull=True,
                    merged_into__isnull=True,
                    user__isnull=False,
                ),
                name="unique_open_cart_per_user",
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"Cart for {self.user}"
        return f"Guest cart {self.token}"

    @property
    def item_count(self):
        return sum(
            item.quantity
            for item in self.items.filter(removed_at__isnull=True)
        )

    @property
    def lifecycle_status(self) -> CartStatus:
        annotated = self.__dict__.get("lifecycle_status_code")
        if isinstance(annotated, str):
            return CartStatus(annotated)
        return lifecycle_status_for_cart(
            last_activity_at=self.last_activity_at,
            converted_at=self.converted_at,
            merged_into_id=self.merged_into_id,
        )


class CartItem(Orderable):
    cart = ParentalKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.PROTECT,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    price_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    added_at = models.DateTimeField(default=timezone.now)
    removed_at = models.DateTimeField(null=True, blank=True)

    panels = [
        FieldPanel("variant"),
        FieldPanel("quantity"),
        FieldPanel("price_snapshot"),
        FieldPanel("added_at"),
        FieldPanel("removed_at"),
    ]

    class Meta(Orderable.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_cart_variant",
            ),
        ]

    def __str__(self):
        return f"{self.variant} × {self.quantity}"

    @property
    def is_live(self):
        return self.removed_at is None


class CartEvent(models.Model):
    class Kind(models.TextChoices):
        ADDED = "added", "Added"
        QUANTITY_CHANGED = "quantity_changed", "Quantity changed"
        REMOVED = "removed", "Removed"
        MERGED = "merged", "Merged"
        CONVERTED = "converted", "Converted"

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="events",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_events",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    quantity = models.PositiveIntegerField(default=0)
    quantity_delta = models.IntegerField(default=0)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self):
        return f"{self.cart_id} {self.kind}"


class Order(ClusterableModel):
    class OrderStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus,
        default=OrderStatus.PENDING,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk}"


class OrderItem(Orderable):
    order = ParentalKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=250)
    variant_label = models.CharField(max_length=200, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    panels = [
        FieldPanel("product"),
        FieldPanel("variant"),
        FieldPanel("product_name"),
        FieldPanel("variant_label"),
        FieldPanel("unit_price"),
        FieldPanel("quantity"),
    ]

    class Meta(Orderable.Meta):
        pass

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Checkout(models.Model):
    class CheckoutStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkouts",
    )
    cart = models.ForeignKey(
        Cart,
        on_delete=models.PROTECT,
        related_name="checkouts",
    )
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=CheckoutStatus,
        default=CheckoutStatus.PENDING,
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Checkout #{self.pk} ({self.get_status_display()})"

    @transaction.atomic
    def complete(self):
        if self.status == self.CheckoutStatus.COMPLETED:
            raise ValidationError("Checkout is already completed.")
        if self.order_id:
            raise ValidationError("Checkout already has an order.")

        from marketplace.cart_workflow import mark_cart_converted

        cart_items = list(
            self.cart.items.filter(removed_at__isnull=True).select_related(
                "variant",
                "variant__product",
            )
        )
        if not cart_items:
            raise ValidationError("Cart is empty.")

        subtotal = Decimal("0")
        order_items_data = []
        for item in cart_items:
            price = item.price_snapshot
            if price is None:
                price = item.variant.price
            if price is None:
                raise ValidationError(
                    f"Variant '{item.variant.label}' for "
                    f"'{item.variant.product.name}' has no price set."
                )
            subtotal += price * item.quantity
            order_items_data.append(
                {
                    "product": item.variant.product,
                    "variant": item.variant,
                    "product_name": item.variant.product.name,
                    "variant_label": item.variant.label,
                    "unit_price": price,
                    "quantity": item.quantity,
                }
            )

        delivery_fee = self.delivery_fee or Decimal("0")
        total = subtotal + delivery_fee

        order = Order.objects.create(
            user=self.user,
            status=Order.OrderStatus.PENDING,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
        )

        for data in order_items_data:
            OrderItem.objects.create(order=order, **data)

        self.order = order
        self.status = self.CheckoutStatus.COMPLETED
        self.save(update_fields=["order", "status", "updated_at"])

        mark_cart_converted(self.cart, order=order)

        return order


class MarketplacePage(Page):
    """CMS page for the public marketplace shop."""

    intro = RichTextField(
        blank=True,
        help_text="Optional intro shown above the marketplace search and products.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Marketplace page"

    def serve(self, request, *args, **kwargs):
        from django.shortcuts import redirect

        return redirect("marketplace:index", permanent=False)
