"""Template context available on every page (nav categories, cart badge)."""

from django.conf import settings

from cart.models import Cart
from products.models import Category


def _cart_item_count(request):
    """Cart badge count for the current user or guest session."""
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    elif key := request.session.get("cart_session_key"):
        cart = Cart.objects.filter(session_key=key, user__isnull=True).first()
    else:
        return 0
    return cart.total_items if cart else 0


def storefront(request):
    """Expose a small amount of shared state to all templates."""
    if request.path.startswith("/admin/"):
        return {"currency": settings.CURRENCY_SYMBOL}

    return {
        "nav_categories": Category.objects.filter(is_active=True)[:8],
        "cart_item_count": _cart_item_count(request),
        "currency": settings.CURRENCY_SYMBOL,
        "shipping_fee": settings.SHIPPING_FEE,
        "free_shipping_threshold": settings.FREE_SHIPPING_THRESHOLD,
        "wishlist_count": len(request.session.get("wishlist", [])),
    }
