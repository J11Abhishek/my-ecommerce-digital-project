"""Search, filtering, sorting and pagination for the product catalogue.

Implements BRD §8 (listing), §9 (search), §10 (filtering) and §8 (pagination).
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Max, Min, Q

from .models import Category, Product

#: Allowed sort keys mapped to ORM orderings (prevents invalid query injection).
SORT_OPTIONS = {
    "newest": "-created_at",
    "oldest": "created_at",
    "price_asc": "price",
    "price_desc": "-price",
    "name_asc": "name",
    "name_desc": "-name",
    "popular": "-is_featured",
}

SORT_CHOICES = [
    ("newest", "Newest first"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("name_asc", "Name: A to Z"),
    ("name_desc", "Name: Z to A"),
    ("popular", "Featured"),
]

AVAILABILITY_CHOICES = [
    ("all", "All products"),
    ("in_stock", "In stock"),
    ("out_of_stock", "Out of stock"),
]


def _to_decimal(value):
    """Parse a min/max price, ignoring anything that is not a number."""
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return amount if amount >= 0 else None


def build_filters(params):
    """Turn raw GET parameters into a validated filter dict."""
    sort = params.get("sort") or "newest"
    return {
        "q": (params.get("q") or "").strip(),
        "category": params.get("category") or "",
        "min_price": _to_decimal(params.get("min_price")),
        "max_price": _to_decimal(params.get("max_price")),
        "availability": params.get("availability") or "all",
        "sort": sort if sort in SORT_OPTIONS else "newest",
    }


def apply_filters(queryset, filters):
    """Apply the validated filter dict to a product queryset."""
    if filters["q"]:
        queryset = queryset.search(filters["q"])

    if filters["category"]:
        queryset = queryset.filter(category__slug=filters["category"])

    if filters["min_price"] is not None:
        queryset = queryset.filter(price__gte=filters["min_price"])
    if filters["max_price"] is not None:
        queryset = queryset.filter(price__lte=filters["max_price"])

    availability = filters["availability"]
    if availability == "in_stock":
        queryset = queryset.in_stock()
    elif availability == "out_of_stock":
        queryset = queryset.filter(stock_quantity=0)

    return queryset.order_by(SORT_OPTIONS[filters["sort"]], "-id")


def active_categories():
    return Category.objects.filter(is_active=True).annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    )


def get_product_page(params, per_page=None):
    """Return ``(page, filters, categories)`` for the product listing view."""
    filters = build_filters(params)
    per_page = per_page or settings.PRODUCTS_PER_PAGE

    queryset = apply_filters(Product.objects.active().select_related("category"), filters)
    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(params.get("page"))

    return page, filters, active_categories()


def price_range():
    """Min/max price in the catalogue, used to bound the filter inputs."""
    bounds = Product.objects.active().aggregate(low=Min("price"), high=Max("price"))
    return bounds["low"] or Decimal("0"), bounds["high"] or Decimal("0")
