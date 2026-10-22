"""Cart views (BRD §12, §13, §31). Supports classic form posts and fetch()."""

import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Product

from . import services
from .models import CartItem


def _wants_json(request):
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _payload(cart):
    """Minimal cart state returned to the front-end after every change."""
    return {
        "count": cart.total_items,
        "subtotal": f"{cart.subtotal:.2f}",
        "shipping": f"{cart.shipping:.2f}",
        "total": f"{cart.total:.2f}",
    }


def cart_view(request):
    cart = services.get_or_create_cart(request)
    return render(
        request,
        "cart/cart.html",
        {
            "cart": cart,
            "items": cart.items_list,
            "subtotal": cart.subtotal,
            "shipping": cart.shipping,
            "discount": cart.discount,
            "total": cart.total,
            "free_shipping_remaining": cart.free_shipping_remaining,
            "stock_issues": cart.has_stock_issues,
        },
    )


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    quantity = request.POST.get("quantity", 1)

    ok, message = services.add_to_cart(request, product, quantity)
    cart = services.get_or_create_cart(request)

    if _wants_json(request):
        return JsonResponse(
            {"ok": ok, "message": message, "cart": _payload(cart)},
            status=200 if ok else 400,
        )

    messages.add_message(request, messages.SUCCESS if ok else messages.WARNING, message)
    return redirect(request.POST.get("next") or "cart:view")


@require_POST
def cart_update(request, pk):
    cart = services.get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=pk, cart=cart)

    if request.POST.get("action") == "remove":
        ok, message = services.remove_item(item)
    else:
        ok, message, _item = services.set_item_quantity(item, request.POST.get("quantity"))

    cart.refresh_from_db()
    if _wants_json(request):
        return JsonResponse(
            {
                "ok": ok,
                "message": message,
                "cart": _payload(cart),
                "item_quantity": item.quantity if ok else None,
                "stock_issues": len(cart.has_stock_issues),
            },
            status=200 if ok else 400,
        )

    messages.add_message(request, messages.SUCCESS if ok else messages.WARNING, message)
    return redirect("cart:view")


@require_POST
def cart_remove(request, pk):
    cart = services.get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=pk, cart=cart)
    ok, message = services.remove_item(item)
    if _wants_json(request):
        return JsonResponse({"ok": ok, "message": message, "cart": _payload(cart)})
    messages.success(request, message)
    return redirect("cart:view")


@require_POST
def cart_clear(request):
    cart = services.get_or_create_cart(request)
    services.clear_cart(cart)
    if _wants_json(request):
        return JsonResponse({"ok": True, "message": "Cart cleared.", "cart": _payload(cart)})
    messages.success(request, "Your cart is now empty.")
    return redirect("cart:view")
