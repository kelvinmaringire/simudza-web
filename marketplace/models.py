from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page


class Cart(ClusterableModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Cart for {self.user}"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(Orderable):
    cart = ParentalKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)

    panels = [
        FieldPanel("product"),
        FieldPanel("quantity"),
    ]

    class Meta(Orderable.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_cart_product",
            ),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"


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
    product_name = models.CharField(max_length=250)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    panels = [
        FieldPanel("product"),
        FieldPanel("product_name"),
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

        cart_items = list(self.cart.items.select_related("product").all())
        if not cart_items:
            raise ValidationError("Cart is empty.")

        subtotal = Decimal("0")
        order_items_data = []
        for item in cart_items:
            price = item.product.price
            if price is None:
                raise ValidationError(
                    f"Product '{item.product.name}' has no price set."
                )
            subtotal += price * item.quantity
            order_items_data.append(
                {
                    "product": item.product,
                    "product_name": item.product.name,
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
