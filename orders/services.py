"""Order placement: a single atomic transaction (BRD §24, §32)."""

import secrets
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from products.models import Product

from .models import Order, OrderItem


class OrderError(Exception):
    """Raised when an order cannot be placed; message is user facing."""


def generate_order_number():
    """Human friendly, collision-checked order number, e.g. ORD2609261043."""
    now = datetime.now()
    for _ in range(10):
        candidate = f"ORD{now:%y%m%d}{secrets.randbelow(9000) + 1000}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    raise OrderError("Could not generate an order number. Please try again.")


def _address_payload(address):
    """Normalise a saved Address instance or a plain dict into one shape."""
    if address is None or isinstance(address, dict):
        return dict(address or {})
    return {
        "full_name": address.full_name,
        "phone": address.phone,
        "address_line1": address.address_line1,
        "address_line2": address.address_line2,
        "city": address.city,
        "state": address.state,
        "pin_code": address.pin_code,
        "country": address.country,
    }


@transaction.atomic
def place_order(*, user, cart, address, payment_method, notes="", save_address=False):
    """Create an order from a cart, decrement stock and empty the cart.

    ``address`` is either a saved ``accounts.Address`` or a dict of raw address
    fields. Raises :class:`OrderError` with a user facing message when the order
    cannot be created (BR-01, BR-03, BR-06).
    """
    if not user.is_authenticated:
        raise OrderError("You must be signed in to place an order.")  # BR-01

    items = list(cart.items.select_related("product"))
    if not items:  # BR-06
        raise OrderError("Your cart is empty.")

    address_data = _address_payload(address)
    required = ["full_name", "phone", "address_line1", "city", "state", "pin_code", "country"]
    missing = [f for f in required if not str(address_data.get(f) or "").strip()]
    if missing:
        raise OrderError("Please complete the delivery address.")

    if save_address:
        if isinstance(address, dict) or address is None:
            from accounts.models import Address

            address = Address(**address_data)
        if not address.pk:
            address.user = user
            address.save()

    # Lock the product rows so two concurrent checkouts cannot oversell.
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[item.product_id for item in items]
        )
    }

    # BR-03: validate every line against the fresh stock numbers.
    problems = []
    for item in items:
        product = locked_products.get(item.product_id)
        if product is None or not product.is_active:
            problems.append(f"{item.product.name} is no longer available.")
        elif item.quantity > product.stock_quantity:
            problems.append(
                f"Only {product.stock_quantity} units of {product.name} are available."
            )
    if problems:
        raise OrderError(" ".join(problems))

    subtotal = sum((item.product.price * item.quantity for item in items), start=0)
    shipping = calculate_shipping(subtotal)
    total = subtotal + shipping

    order = Order.objects.create(
        order_number=generate_order_number(),
        user=user,
        payment_method=payment_method,
        subtotal=subtotal,
        shipping_amount=shipping,
        total_amount=total,
        shipping_full_name=address_data["full_name"],
        shipping_phone=address_data["phone"],
        shipping_address_line1=address_data["address_line1"],
        shipping_address_line2=address_data.get("address_line2", ""),
        shipping_city=address_data["city"],
        shipping_state=address_data["state"],
        shipping_pin_code=address_data["pin_code"],
        shipping_country=address_data["country"],
        notes=notes or "",
        placed_at=timezone.now(),
    )

    order_items = []
    for item in items:
        product = locked_products[item.product_id]
        # BR-07: the price is frozen on the order line.
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                unit_price=product.price,
                quantity=item.quantity,
            )
        )
        # BR-24: reduce inventory.
        product.stock_quantity -= item.quantity
        product.save(update_fields=["stock_quantity", "updated_at"])

    OrderItem.objects.bulk_create(order_items)

    # Every order gets a payment record: PENDING for COD, filled in by the
    # simulated gateway for online payment.
    from payments.models import Payment

    Payment.objects.create(
        order=order,
        method=payment_method,
        status=Payment.Status.PENDING,
        amount=total,
    )

    order.status_logs.create(
        from_status="", to_status=Order.Status.PENDING, note="Order placed by customer"
    )

    cart.clear()  # the cart is emptied only because the transaction succeeded
    return order


def calculate_shipping(subtotal):
    """BRD §12: flat fee, free above the configured threshold."""
    threshold = settings.FREE_SHIPPING_THRESHOLD
    if subtotal <= 0:
        return 0
    if threshold and subtotal >= threshold:
        return 0
    return settings.SHIPPING_FEE
