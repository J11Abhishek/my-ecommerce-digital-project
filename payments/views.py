"""Mock payment views (BRD §15, §31)."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orders.models import Order

from .services import VALID_TEST_CARDS, process_online_payment


class MockPaymentForm(forms.Form):
    """Card form used by the simulated gateway."""

    card_number = forms.CharField(
        max_length=19,
        label="Card number",
        widget=forms.TextInput(attrs={"placeholder": "4242 4242 4242 4242", "inputmode": "numeric"}),
        help_text="Use a test card, e.g. 4242 4242 4242 4242. A number ending in 0000 is declined.",
    )
    card_name = forms.CharField(max_length=100, label="Name on card")
    expiry = forms.CharField(max_length=7, label="Expiry (MM/YY)", initial="12/30")
    cvv = forms.CharField(max_length=4, label="CVV", widget=forms.PasswordInput(render_value=False))


def _get_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    if order.user_id != request.user.pk and not request.user.is_staff:
        raise Http404("Order not found.")
    return order


@login_required
def process_payment(request, order_number):
    """Simulated online payment page shown right after checkout."""
    order = _get_order(request, order_number)

    if order.payment_method != Order.PaymentMethod.ONLINE:
        return redirect("orders:success", order_number=order.order_number)
    if order.payment_status == Order.PaymentStatus.PAID:
        messages.info(request, "This order is already paid.")
        return redirect("orders:success", order_number=order.order_number)

    form = MockPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ok, payment = process_online_payment(
            order,
            card_number=form.cleaned_data["card_number"],
            card_name=form.cleaned_data["card_name"],
        )
        if ok:
            messages.success(request, f"Payment successful. Reference {payment.transaction_id}.")
            return redirect("orders:success", order_number=order.order_number)
        messages.error(request, f"Payment failed: {payment.failure_reason}")

    return render(
        request,
        "payments/process.html",
        {
            "form": form,
            "order": order,
            "test_cards": VALID_TEST_CARDS,
        },
    )


@login_required
@require_POST
def retry_payment(request, order_number):
    order = _get_order(request, order_number)
    if order.payment_status == Order.PaymentStatus.PAID:
        return redirect("orders:success", order_number=order.order_number)
    return redirect("payments:process", order_number=order.order_number)
