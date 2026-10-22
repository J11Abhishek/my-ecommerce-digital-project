"""Presentation helpers used across the templates."""

from decimal import Decimal

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter(name="currency")
def currency(value, symbol="₹"):
    """Format a number as money, e.g. 1299.5 -> ₹1,299.50."""
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return f"{symbol}0.00"
    return f"{symbol}{amount:,.2f}"


@register.filter(name="compact_currency")
def compact_currency(value, symbol="₹"):
    """Short form for dashboards: 1250000 -> ₹12.5L / 25000 -> ₹25K."""
    try:
        amount = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return f"{symbol}0"
    amount = float(amount)
    if amount >= 10_000_000:
        return f"{symbol}{amount / 10_000_000:.2f}Cr"
    if amount >= 100_000:
        return f"{symbol}{amount / 100_000:.2f}L"
    if amount >= 1_000:
        return f"{symbol}{amount / 1_000:.1f}K"
    return f"{symbol}{amount:,.0f}"


@register.filter(name="status_tone")
def status_tone(value):
    tones = {
        "PENDING": "badge-warning",
        "CONFIRMED": "badge-info",
        "PROCESSING": "badge-info",
        "SHIPPED": "badge-primary",
        "DELIVERED": "badge-success",
        "CANCELLED": "badge-danger",
        "PAID": "badge-success",
        "FAILED": "badge-danger",
        "REFUNDED": "badge-muted",
    }
    return tones.get(value, "badge-muted")


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Rebuild the query string, overriding the given keys.

    Keeps filters and page numbers linked correctly in the listing views.
    """
    request = context["request"]
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    query = params.urlencode() if hasattr(params, "urlencode") else ""
    return format_html("?{}", query) if query else ""


@register.filter(name="percent_of")
def percent_of(value, total):
    try:
        total = float(total)
        if total <= 0:
            return 0
        return round(float(value) / total * 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
