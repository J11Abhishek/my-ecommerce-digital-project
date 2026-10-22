"""Mock payment model (BRD §15, §16, §25)."""

from django.db import models
from django.utils import timezone

from orders.models import Order


class Payment(models.Model):
    """A simulated payment attempt. No real gateway is contacted."""

    class Method(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        ONLINE = "ONLINE", "Online Payment (mock)"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    provider = models.CharField(max_length=50, default="MockPay")
    transaction_id = models.CharField(max_length=40, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "payments"

    def __str__(self):
        return f"{self.order.order_number} - {self.get_status_display()}"

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    def mark_paid(self, transaction_id="", card_last4=""):
        self.status = self.Status.PAID
        self.transaction_id = transaction_id
        self.card_last4 = card_last4
        self.paid_at = timezone.now()
        self.failure_reason = ""
        self.save()

    def mark_failed(self, reason):
        self.status = self.Status.FAILED
        self.failure_reason = reason
        self.save()
