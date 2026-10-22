"""Mock payment processing (BRD §15).

Simulates a gateway: no network calls, no secrets, deterministic outcomes.
A card number ending in ``0000`` is always declined so both paths can be
demonstrated during practice.
"""

import secrets
from datetime import datetime

from orders.models import Order

from .models import Payment

DECLINE_CARD_SUFFIX = "0000"
VALID_TEST_CARDS = {
    "4242424242424242": "Visa",
    "4111111111111111": "Mastercard",
    "5555555555554444": "Amex",
}


def get_or_create_payment(order):
    payment, _created = Payment.objects.get_or_create(
        order=order,
        defaults={
            "method": order.payment_method,
            "amount": order.total_amount,
        },
    )
    return payment


def _transaction_id():
    return f"MP{datetime.now():%Y%m%d}{secrets.token_hex(4).upper()}"


def process_online_payment(order, card_number="", card_name=""):
    """Attempt a mock payment and update order + payment records.

    Returns ``(ok, payment)``; on failure the order stays ``PENDING`` with a
    ``FAILED`` payment so the customer can retry.
    """
    payment = get_or_create_payment(order)
    digits = "".join(ch for ch in (card_number or "") if ch.isdigit())

    if len(digits) < 12:
        payment.mark_failed("Invalid card number.")
        return False, payment

    if digits.endswith(DECLINE_CARD_SUFFIX):
        payment.mark_failed("Card declined by the (mock) issuer.")
        return False, payment

    payment.mark_paid(transaction_id=_transaction_id(), card_last4=digits[-4:])

    order.payment_status = Order.PaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])
    return True, payment


def confirm_cod_payment(order):
    """Cash on delivery: the payment stays pending until the order is delivered."""
    return get_or_create_payment(order)
