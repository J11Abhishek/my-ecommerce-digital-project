"""Cart operations: the business rules from BRD §12 and §13.

Every mutating function returns ``(ok, message)`` so views can surface the
result through Django messages instead of raising exceptions.
"""

from django.db import transaction

from .models import Cart, CartItem, max_allowed_quantity

MAX_INPUT_QUANTITY = 99
_UNSET = object()


def get_or_create_cart(request, user=_UNSET):
    """Return the cart for the current session/user, creating it if needed.

    ``user`` can be passed explicitly (login signal) because the request that
    triggers the signal is not guaranteed to have ``request.user`` attached.
    """
    if user is _UNSET:
        candidate = getattr(request, "user", None)
        user = candidate if getattr(candidate, "is_authenticated", False) else None

    if user is not None:
        cart = Cart.objects.filter(user=user).first()
        if cart:
            return merge_guest_cart_on_login(request, cart)
        # Adopt a guest cart created before the user signed in.
        guest_cart = _guest_cart(request)
        if guest_cart:
            return merge_carts(guest_cart, cart=Cart.objects.create(user=user))
        return Cart.objects.create(user=user)

    cart = _guest_cart(request)
    if cart:
        return cart
    if not request.session.session_key:
        request.session.save()  # a persistent key is required to find the cart
    # Mirrored in the session so template context processors can find the cart.
    request.session["cart_session_key"] = request.session.session_key
    return Cart.objects.create(session_key=request.session.session_key)


def _guest_cart(request):
    # The session key is cycled on login, so prefer the key stored with the cart.
    key = request.session.get("cart_session_key") or request.session.session_key
    if not key:
        return None
    return Cart.objects.filter(session_key=key, user__isnull=True).first()


def merge_guest_cart_on_login(request, cart):
    """Called on every authenticated request: fold any guest items in."""
    guest_cart = _guest_cart(request)
    if guest_cart and guest_cart.pk != cart.pk:
        merge_carts(guest_cart, cart=cart)
    return cart


@transaction.atomic
def merge_carts(source, cart):
    """Move guest items into the signed-in user's cart."""
    for item in list(source.items.select_related("product")):
        existing = cart.items.filter(product=item.product).first()
        if existing:
            existing.quantity = min(
                existing.quantity + item.quantity, max_allowed_quantity(item.product)
            )
            existing.save()
        else:
            item.cart = cart
            item.quantity = min(item.quantity, max_allowed_quantity(item.product))
            item.save()
    source.delete()
    return cart


def _clean_quantity(quantity):
    try:
        value = int(quantity)
    except (TypeError, ValueError):
        return None
    if value < 1 or value > MAX_INPUT_QUANTITY:
        return None
    return value


def add_to_cart(request, product, quantity=1):
    """BR-03: never allow the cart to hold more units than the stock."""
    cart = get_or_create_cart(request)

    if not product.is_active:
        return False, "This product is no longer available."
    if product.is_out_of_stock:
        return False, f"{product.name} is out of stock."

    quantity = _clean_quantity(quantity)
    if quantity is None:
        return False, "Please enter a valid quantity between 1 and 99."

    item = cart.items.filter(product=product).first()
    requested = (item.quantity if item else 0) + quantity
    allowed = max_allowed_quantity(product)

    if requested > allowed:
        if allowed == 0:
            if item:
                item.delete()
            return False, f"{product.name} is out of stock."
        return False, f"Only {allowed} units of {product.name} are available."

    if item:
        item.quantity = requested
        item.save(update_fields=["quantity", "updated_at"])
    else:
        CartItem.objects.create(cart=cart, product=product, quantity=requested)

    return True, f"{product.name} added to your cart."


def set_item_quantity(cart_item, quantity):
    """Increase / decrease a line, rejecting quantities above the stock (BR-03)."""
    quantity = _clean_quantity(quantity)
    product = cart_item.product

    if quantity is None:
        return False, "Please enter a valid quantity between 1 and 99.", cart_item
    if product.is_out_of_stock:
        return False, f"{product.name} is out of stock.", cart_item
    if quantity > product.stock_quantity:
        return (
            False,
            f"Only {product.stock_quantity} units of {product.name} are available.",
            cart_item,
        )

    cart_item.quantity = min(quantity, max_allowed_quantity(product))
    cart_item.save()
    return True, f"Updated quantity for {product.name}.", cart_item


def remove_item(cart_item):
    name = cart_item.product.name
    cart_item.delete()
    return True, f"{name} removed from your cart."


def clear_cart(cart):
    cart.clear()
    return True, "Cart cleared."
