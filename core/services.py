"""Reporting queries for the admin dashboard (BRD §22, §23)."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import User
from orders.models import Order, OrderItem
from products.models import Category, Product


def dashboard_stats():
    """Headline counters shown at the top of the dashboard."""
    revenue = (
        Order.objects.filter(payment_status=Order.PaymentStatus.PAID).aggregate(
            total=Sum("total_amount")
        )["total"]
        or Decimal("0.00")
    )
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_this_month = (
        Order.objects.filter(payment_status=Order.PaymentStatus.PAID, placed_at__gte=month_start)
        .aggregate(total=Sum("total_amount"))["total"]
        or Decimal("0.00")
    )
    cod_pending = (
        Order.objects.filter(
            payment_method=Order.PaymentMethod.COD,
            payment_status=Order.PaymentStatus.PENDING,
        ).aggregate(total=Sum("total_amount"))["total"]
        or Decimal("0.00")
    )
    return {
        "total_products": Product.objects.count(),
        "active_products": Product.objects.filter(is_active=True).count(),
        "out_of_stock": Product.objects.filter(is_active=True, stock_quantity=0).count(),
        "total_categories": Category.objects.count(),
        "total_customers": User.objects.filter(is_staff=False).count(),
        "total_orders": Order.objects.count(),
        "pending_orders": Order.objects.filter(
            status__in=[Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PROCESSING]
        ).count(),
        "shipped_orders": Order.objects.filter(status=Order.Status.SHIPPED).count(),
        "delivered_orders": Order.objects.filter(status=Order.Status.DELIVERED).count(),
        "cancelled_orders": Order.objects.filter(status=Order.Status.CANCELLED).count(),
        "revenue": revenue,
        "revenue_this_month": revenue_this_month,
        "cod_pending_amount": cod_pending,
    }


def revenue_series(days=14):
    """Daily paid revenue for the last ``days`` days, oldest first."""
    start = timezone.now().date() - timedelta(days=days - 1)
    rows = (
        Order.objects.filter(payment_status=Order.PaymentStatus.PAID, placed_at__date__gte=start)
        .annotate(day=TruncDate("placed_at"))
        .values("day")
        .annotate(total=Sum("total_amount"), orders=Count("id"))
        .order_by("day")
    )
    by_day = {row["day"]: row for row in rows}

    series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = by_day.get(day)
        series.append(
            {
                "day": day,
                "label": day.strftime("%d %b"),
                "total": row["total"] if row else Decimal("0.00"),
                "orders": row["orders"] if row else 0,
            }
        )

    # Percentage of the peak, so the template can size the bars without maths.
    peak = max((Decimal(str(point["total"])) for point in series), default=Decimal("0"))
    for point in series:
        total = Decimal(str(point["total"]))
        point["pct"] = int(total / peak * 100) if peak > 0 else 0
    return series


def top_products(limit=5):
    """Best sellers by revenue, using the historical order item prices (BR-07)."""
    return (
        OrderItem.objects.values("product_id", "product_name")
        .annotate(
            units=Sum("quantity"),
            revenue=Sum(F("unit_price") * F("quantity")),
        )
        .order_by("-revenue")[:limit]
    )


def low_stock_products(limit=10, threshold=5):
    return list(
        Product.objects.filter(is_active=True, stock_quantity__lte=threshold)
        .select_related("category")
        .order_by("stock_quantity")[:limit]
    )
