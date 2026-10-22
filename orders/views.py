"""Customer order views: checkout, history, details, cancellation.

Covers BRD §14, §16-§19 and BRD BR-01/BR-09/BR-10.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cart import services as cart_services

from .business import InvalidStatusTransition, cancel_order
from .forms import CheckoutForm
from .models import Order
from .services import OrderError, place_order

ORDER_STATUS_FILTERS = {
    "all": None,
    "active": ["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED"],
    "cancelled": ["CANCELLED"],
    "delivered": ["DELIVERED"],
}


def _get_order_for_user(request, order_number):
    """BR-09: customers only ever see their own orders."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_logs"),
        order_number=order_number,
    )
    if order.user_id != request.user.pk and not request.user.is_staff:
        raise Http404("Order not found.")
    return order


@login_required
def checkout(request):
    """BRD §14/§15: confirm customer info, address and payment method."""
    cart = cart_services.get_or_create_cart(request)
    if not cart.items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart:view")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            address = form.cleaned_data.get("saved_address")
            save_address = bool(form.cleaned_data.get("save_address"))
            if address is None:
                address = form.new_address_data()

            try:
                order = place_order(
                    user=request.user,
                    cart=cart,
                    address=address,
                    payment_method=form.cleaned_data["payment_method"],
                    notes=form.cleaned_data.get("notes", ""),
                    save_address=save_address,
                )
            except OrderError as exc:
                messages.error(request, str(exc))
                return redirect("cart:view")

            if order.payment_method == Order.PaymentMethod.ONLINE:
                return redirect("payments:process", order_number=order.order_number)
            return redirect("orders:success", order_number=order.order_number)
    else:
        form = CheckoutForm(user=request.user)

    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "cart": cart,
            "items": cart.items_list,
            "subtotal": cart.subtotal,
            "shipping": cart.shipping,
            "discount": cart.discount,
            "total": cart.total,
            "free_shipping_remaining": cart.free_shipping_remaining,
        },
    )


@login_required
def order_success(request, order_number):
    """BRD §31: order confirmation page."""
    order = _get_order_for_user(request, order_number)
    return render(request, "orders/order_success.html", {"order": order})


@login_required
def order_list(request):
    """BRD §18: order history with status filter and pagination."""
    orders = Order.objects.filter(user=request.user)
    selected = request.GET.get("status", "all")
    statuses = ORDER_STATUS_FILTERS.get(selected, None)
    if statuses:
        orders = orders.filter(status__in=statuses)
    if term := request.GET.get("q", "").strip():
        orders = orders.filter(
            Q(order_number__icontains=term) | Q(shipping_full_name__icontains=term)
        )

    paginator = Paginator(orders, 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "orders/order_list.html",
        {"page_obj": page, "orders": page.object_list, "selected_status": selected, "q": term},
    )


@login_required
def order_detail(request, order_number):
    """BRD §18: a single order with its items and status timeline."""
    order = _get_order_for_user(request, order_number)
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def order_cancel(request, order_number):
    """BRD §19: cancel before shipment, restoring stock."""
    order = _get_order_for_user(request, order_number)
    reason = (request.POST.get("reason") or "").strip()
    try:
        cancel_order(order, user=request.user, reason=reason)
    except InvalidStatusTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order {order.order_number} has been cancelled.")
    return redirect("orders:detail", order_number=order.order_number)


@login_required
def order_invoice(request, order_number):
    """Printable invoice view (BRD §33 future enhancement #7, HTML only)."""
    order = _get_order_for_user(request, order_number)
    return render(request, "orders/invoice.html", {"order": order})
