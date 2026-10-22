"""Order status rules and stock restoration (BRD §19, §23, §24, BR-10).

Kept free of HTTP concerns so it can be unit tested and reused from admin,
customer views and management commands.
"""

from django.db import transaction
from django.utils import timezone

from .models import ALLOWED_TRANSITIONS, Order


class InvalidStatusTransition(Exception):
    """Raised when a status change is not allowed (BR-10)."""


def can_transition(order, new_status):
    return new_status in ALLOWED_TRANSITIONS.get(order.status, set())


@transaction.atomic
def transition_order(order, new_status, user=None, note="", reason=""):
    """Move an order to ``new_status`` and log the change.

    Restores stock when the order is cancelled before it shipped (BRD §24).
    """
    if new_status not in Order.Status.values:
        raise InvalidStatusTransition(f"Unknown status '{new_status}'.")
    if not can_transition(order, new_status):
        raise InvalidStatusTransition(
            f"Cannot change status from {order.get_status_display()} to "
            f"{dict(Order.Status.choices)[new_status]}."
        )

    previous = order.status
    order.status = new_status
    fields = ["status", "updated_at"]

    if new_status == Order.Status.CANCELLED:
        order.cancelled_at = timezone.now()
        order.cancel_reason = reason or note
        fields += ["cancelled_at", "cancel_reason"]
        if order.payment_status == Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.REFUNDED
            fields.append("payment_status")
        reverse_stock_for(order)

    if new_status == Order.Status.DELIVERED and order.payment_method == Order.PaymentMethod.COD:
        order.payment_status = Order.PaymentStatus.PAID
        fields.append("payment_status")

    order.save(update_fields=fields)
    order.status_logs.create(
        from_status=previous, to_status=new_status, note=note, changed_by=user
    )
    return order


@transaction.atomic
def reverse_stock_for(order):
    """Give the reserved units back to inventory exactly once (BRD §24)."""
    if order.stock_reversed:
        return 0
    restored = 0
    for item in order.items.select_related("product"):
        if item.product_id:
            product = item.product
            product.stock_quantity += item.quantity
            product.save(update_fields=["stock_quantity", "updated_at"])
            restored += item.quantity
    order.stock_reversed = True
    order.save(update_fields=["stock_reversed"])
    return restored


@transaction.atomic
def cancel_order(order, user=None, reason=""):
    """BR-10: only Pending / Confirmed / Processing orders can be cancelled."""
    if not order.is_cancellable:
        raise InvalidStatusTransition(
            f"Order {order.order_number} cannot be cancelled because it is "
            f"{order.get_status_display().lower()}."
        )
    if not order.can_be_cancelled_by(user):
        raise InvalidStatusTransition("You are not allowed to cancel this order.")
    return transition_order(order, Order.Status.CANCELLED, user=user, reason=reason)
