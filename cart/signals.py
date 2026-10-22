"""Cart signals: merge the guest cart into the user's cart on login."""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def merge_guest_cart(sender, request, user, **kwargs):
    from .services import get_or_create_cart

    # The request that fires this signal is not guaranteed to have a session
    # (programmatic logins such as the test client's force_login).
    if not hasattr(request, "session"):
        return

    cart = get_or_create_cart(request, user=user)
    if cart:
        cart.user = user
        cart.save(update_fields=["user", "updated_at"])
