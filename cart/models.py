"""Shopping cart models and totals (BRD §12, §13, §24)."""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from products.models import Product


class Cart(models.Model):
    """One cart per signed-in user; guests get a session-key cart."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Cart #{self.pk} ({self.user or 'guest'})"

    # -- totals -----------------------------------------------------------
    @property
    def items_list(self):
        return list(self.items.select_related("product", "product__category"))

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), start=0)

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def unique_items(self):
        return self.items.count()

    @property
    def discount(self):
        """Placeholder for BRD §33 future enhancement (coupons)."""
        return 0

    @property
    def shipping(self):
        if self.subtotal <= 0:
            return 0
        if settings.FREE_SHIPPING_THRESHOLD and self.subtotal >= settings.FREE_SHIPPING_THRESHOLD:
            return 0
        return settings.SHIPPING_FEE

    @property
    def total(self):
        return self.subtotal + self.shipping - self.discount

    @property
    def free_shipping_remaining(self):
        threshold = settings.FREE_SHIPPING_THRESHOLD
        if not threshold or self.subtotal >= threshold:
            return 0
        return threshold - self.subtotal

    @property
    def has_stock_issues(self):
        """Items whose quantity now exceeds available stock (BR-03)."""
        return [i for i in self.items.select_related("product") if i.quantity > i.product.stock_quantity]

    def add_product(self, product, quantity=1):
        """Add to cart, clamped to the available stock (BR-03)."""
        item, _created = self.items.get_or_create(product=product, defaults={"quantity": 0})
        item.quantity = min(item.quantity + quantity, max_allowed_quantity(product))
        item.save()
        return item, item.quantity

    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_product_per_cart"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def unit_price(self):
        """Always the live catalogue price while the item is in the cart."""
        return self.product.price

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def max_quantity(self):
        return max_allowed_quantity(self.product)

    @property
    def exceeds_stock(self):
        return self.quantity > self.product.stock_quantity

    def save(self, *args, **kwargs):
        self.quantity = max(int(self.quantity), 1)
        super().save(*args, **kwargs)


def max_allowed_quantity(product):
    """Most units a customer may hold of one product (BR-03, §13)."""
    stock_cap = product.stock_quantity
    configured_cap = getattr(settings, "MAX_QUANTITY_PER_ITEM", 10)
    return max(min(stock_cap, configured_cap), 0)
