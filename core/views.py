"""Home page and the administrator dashboard (BRD §22, §23, §31)."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from cart.models import Cart
from orders.business import InvalidStatusTransition, transition_order
from orders.models import Order, OrderItem
from payments.models import Payment
from products.models import Category, Product

from .services import dashboard_stats, low_stock_products, revenue_series, top_products


def home(request):
    """Landing page: featured products, latest arrivals, categories."""
    featured = (
        Product.objects.active()
        .filter(is_featured=True)
        .select_related("category")[:8]
    )
    latest = (
        Product.objects.active()
        .select_related("category")
        .order_by("-created_at")[:8]
    )
    categories = (
        Category.objects.filter(is_active=True)
        .annotate(product_count=Count("products", filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)[:6]
    )
    return render(
        request,
        "core/home.html",
        {
            "featured_products": featured,
            "latest_products": latest,
            "categories": categories,
        },
    )


def about(request):
    return render(request, "core/about.html")


def contact(request):
    """Simple contact form that echoes a thank-you message."""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        message = (request.POST.get("message") or "").strip()
        if name and email and message:
            messages.success(request, "Thanks! We have received your message.")
            return redirect("core:contact")
        messages.error(request, "Please fill in your name, email and message.")
    return render(request, "core/contact.html")


# --------------------------------------------------------------------------
# Admin dashboard
# --------------------------------------------------------------------------
@staff_member_required
def dashboard(request):
    """BRD §22: headline numbers, revenue trend, low stock, recent orders."""
    return render(
        request,
        "core/dashboard.html",
        {
            "stats": dashboard_stats(),
            "revenue_series": revenue_series(days=14),
            "top_products": top_products(limit=5),
            "low_stock_products": low_stock_products(limit=10),
            "recent_orders": Order.objects.select_related("user")[:10],
            "abandoned_carts": Cart.objects.filter(user__isnull=True).count(),
            "total_customers": User.objects.filter(is_staff=False).count(),
        },
    )


@staff_member_required
def dashboard_products(request):
    """BRD §22: product management table with inline stock/price editing."""
    products = Product.objects.select_related("category").all()
    term = (request.GET.get("q") or "").strip()
    if term:
        products = products.filter(
            Q(name__icontains=term) | Q(sku__icontains=term) | Q(category__name__icontains=term)
        )
    status = request.GET.get("status", "")
    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)
    elif status == "low":
        products = products.filter(is_active=True, stock_quantity__lte=5)
    elif status == "out":
        products = products.filter(stock_quantity=0)

    paginator = Paginator(products, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "core/dashboard_products.html",
        {
            "page_obj": page,
            "products": page.object_list,
            "q": term,
            "status": status,
            "categories": Category.objects.all(),
        },
    )


@staff_member_required
@require_POST
def dashboard_product_save(request, pk):
    """Inline update of price / stock / active flag (BRD §22, §24)."""
    product = get_object_or_404(Product, pk=pk)
    changed = []
    if "price" in request.POST:
        try:
            price = float(request.POST["price"])
        except ValueError:
            messages.error(request, "Invalid price.")
            return redirect(request.POST.get("next") or "core:dashboard_products")
        if price < 0:
            messages.error(request, "Price cannot be negative (BR-04).")
            return redirect(request.POST.get("next") or "core:dashboard_products")
        product.price = price
        changed.append("price")
    if "stock_quantity" in request.POST:
        try:
            stock = int(request.POST["stock_quantity"])
        except ValueError:
            messages.error(request, "Invalid stock quantity.")
            return redirect(request.POST.get("next") or "core:dashboard_products")
        if stock < 0:
            messages.error(request, "Stock cannot be negative (BR-05).")
            return redirect(request.POST.get("next") or "core:dashboard_products")
        product.stock_quantity = stock
        changed.append("stock")
    if "is_active" in request.POST:
        is_active = request.POST.get("is_active") in {"1", "on", "true"}
        if is_active != product.is_active:
            product.is_active = is_active
            changed.append("visibility")
    if changed:
        product.save()
        messages.success(request, f"Updated {product.name} ({', '.join(changed)}).")
    return redirect(request.POST.get("next") or "core:dashboard_products")


@staff_member_required
def dashboard_categories(request):
    categories = Category.objects.annotate(
        total=Count("products"), active_products=Count("products", filter=Q(products__is_active=True))
    )
    return render(request, "core/dashboard_categories.html", {"categories": categories})


@staff_member_required
def dashboard_customers(request):
    """BRD §22: customer list with spend and order counts."""
    customers = User.objects.filter(is_staff=False).annotate(
        order_count=Count("orders", distinct=True),
        total_spent=Sum("orders__total_amount", filter=Q(orders__payment_status="PAID")),
    )
    term = (request.GET.get("q") or "").strip()
    if term:
        customers = customers.filter(
            Q(email__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(phone__icontains=term)
        )
    paginator = Paginator(customers.order_by("-date_joined"), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/dashboard_customers.html", {"page_obj": page, "customers": page.object_list, "q": term})


@staff_member_required
def dashboard_orders(request):
    """BRD §23: all orders, searchable and filterable by status."""
    orders = Order.objects.select_related("user")
    term = (request.GET.get("q") or "").strip()
    if term:
        orders = orders.filter(
            Q(order_number__icontains=term)
            | Q(user__email__icontains=term)
            | Q(shipping_full_name__icontains=term)
        )
    status = request.GET.get("status", "")
    if status:
        orders = orders.filter(status=status)
    paginator = Paginator(orders, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "core/dashboard_orders.html",
        {
            "page_obj": page,
            "orders": page.object_list,
            "q": term,
            "status": status,
            "status_choices": Order.Status.choices,
        },
    )


@staff_member_required
def dashboard_order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_logs__changed_by", "status_logs"),
        order_number=order_number,
    )
    from .forms import OrderStatusForm

    form = OrderStatusForm(
        initial={
            "status": order.status,
            "next_statuses": [s for s, _ in Order.Status.choices if s != order.status],
        }
    )
    return render(
        request,
        "core/dashboard_order_detail.html",
        {"order": order, "form": form, "payment": getattr(order, "payment", None)},
    )


@staff_member_required
@require_POST
def dashboard_order_status(request, order_number):
    """BRD §23: update the order status through the validated state machine."""
    order = get_object_or_404(Order, order_number=order_number)
    new_status = request.POST.get("status", "")
    note = (request.POST.get("note") or "").strip()
    try:
        transition_order(order, new_status, user=request.user, note=note)
    except InvalidStatusTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order {order.order_number} is now {order.get_status_display()}.")
    return redirect("core:dashboard_order_detail", order_number=order.order_number)


@staff_member_required
def dashboard_payments(request):
    payments = Payment.objects.select_related("order", "order__user")
    paginator = Paginator(payments, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "core/dashboard_payments.html", {"page_obj": page, "payments": page.object_list})


@staff_member_required
def dashboard_sales(request):
    """Simple sales report: revenue by day and by category."""
    today = timezone.now().date()
    range_days = int(request.GET.get("days", 30) or 30)
    range_days = max(min(range_days, 365), 7)
    start = today - timedelta(days=range_days - 1)

    paid = Order.objects.filter(payment_status=Order.PaymentStatus.PAID, placed_at__date__gte=start)
    total = paid.aggregate(total=Sum("total_amount"))["total"] or 0

    by_category = (
        OrderItem.objects.filter(
            order__payment_status=Order.PaymentStatus.PAID, order__placed_at__date__gte=start
        )
        .values("product__category__name")
        .annotate(revenue=Sum(F("unit_price") * F("quantity")), units=Sum("quantity"))
        .order_by("-revenue")[:10]
    )
    by_status = Order.objects.filter(placed_at__date__gte=start).values("status").annotate(count=Count("id"))

    return render(
        request,
        "core/dashboard_sales.html",
        {
            "range_days": range_days,
            "series": revenue_series(days=range_days),
            "total_revenue": total,
            "by_category": by_category,
            "by_status": by_status,
            "paid_orders": paid.count(),
        },
    )
