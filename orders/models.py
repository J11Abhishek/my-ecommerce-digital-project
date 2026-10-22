"""Order and order-item models (BRD §16-§19, §25)."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from products.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PROCESSING = "PROCESSING", "Processing"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        ONLINE = "ONLINE", "Online Payment (mock)"

    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.COD
    )

    # Money snapshot (BR-07)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Delivery address snapshot, so history survives address edits
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone = models.CharField(max_length=20)
    shipping_address_line1 = models.CharField(max_length=200)
    shipping_address_line2 = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pin_code = models.CharField(max_length=10)
    shipping_country = models.CharField(max_length=100, default="India")

    notes = models.TextField(blank=True, max_length=500)
    cancel_reason = models.CharField(max_length=255, blank=True)
    stock_reversed = models.BooleanField(
        default=False, help_text="Set once cancelled stock has been returned."
    )
    placed_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-placed_at"]
        indexes = [
            models.Index(fields=["user", "-placed_at"]),
            models.Index(fields=["status", "-placed_at"]),
        ]

    def __str__(self):
        return self.order_number

    def get_absolute_url(self):
        return reverse("orders:detail", args=[self.order_number])

    # -- helpers ----------------------------------------------------------
    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def unique_item_count(self):
        return self.items.count()

    @property
    def shipping_address(self):
        parts = [
            self.shipping_full_name,
            self.shipping_phone,
            self.shipping_address_line1,
            self.shipping_address_line2,
            self.shipping_city,
            self.shipping_state,
            self.shipping_pin_code,
            self.shipping_country,
        ]
        return ", ".join(p for p in parts if p)

    @property
    def is_cancellable(self):
        """BR-10: cancellation is only allowed before shipment."""
        return self.status in CANCELLABLE_STATUSES

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def status_tone(self):
        return ORDER_STATUS_TONES.get(self.status, "muted")

    def can_be_cancelled_by(self, user):
        if not self.is_cancellable:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return self.user_id == user.pk


class OrderItem(models.Model):
    """Line item storing the price at purchase time (BR-07)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="order_item_quantity_gte_1"
            )
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class OrderStatusLog(models.Model):
    """Audit trail of status changes, shown on the admin order page."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_logs")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "status logs"

    def __str__(self):
        return f"{self.order_id}: {self.from_status or 'new'} -> {self.to_status}"


#: Statuses a customer may still cancel (BRD §19, BR-10).
CANCELLABLE_STATUSES = {Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PROCESSING}

#: Allowed status transitions, enforced in orders.business.transition_order.
ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.PROCESSING, Order.Status.CANCELLED},
    Order.Status.PROCESSING: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),
    Order.Status.CANCELLED: set(),
}

#: Bootstrap-style CSS tone per status, used by templates.
ORDER_STATUS_TONES = {
    Order.Status.PENDING: "warning",
    Order.Status.CONFIRMED: "info",
    Order.Status.PROCESSING: "info",
    Order.Status.SHIPPED: "primary",
    Order.Status.DELIVERED: "success",
    Order.Status.CANCELLED: "danger",
}
