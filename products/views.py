"""Catalogue views: listing, search, filters and product detail (BRD §8-§11)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Category, Product
from .services import (
    AVAILABILITY_CHOICES,
    SORT_CHOICES,
    get_product_page,
    price_range,
)


def product_list(request):
    """BRD §8/§9/§10: paginated list with search, filter and sort."""
    page, filters, categories = get_product_page(request.GET)
    return render(
        request,
        "products/product_list.html",
        {
            "page_obj": page,
            "products": page.object_list,
            "filters": filters,
            "categories": categories,
            "sort_choices": SORT_CHOICES,
            "availability_choices": AVAILABILITY_CHOICES,
            "price_bounds": price_range(),
            "is_search": bool(filters["q"]),
        },
    )


def product_detail(request, slug):
    """BRD §11: full product details, related products, stock aware CTA."""
    product = get_object_or_404(
        Product.objects.select_related("category"), slug=slug, is_active=True
    )
    related = (
        Product.objects.active()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .select_related("category")[:4]
    )
    return render(
        request,
        "products/product_detail.html",
        {"product": product, "related_products": related},
    )


def category_detail(request, slug):
    """Redirect a category slug to the filtered product listing."""
    get_object_or_404(Category, slug=slug, is_active=True)
    return redirect(f"{reverse('products:list')}?category={slug}")


@login_required
@require_POST
def toggle_wishlist(request, pk):
    """Lightweight wishlist toggle (BRD §33 future enhancement #2)."""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    wishlist = list(request.session.get("wishlist", []))
    if pk in wishlist:
        wishlist.remove(pk)
    else:
        wishlist.append(pk)
    request.session["wishlist"] = wishlist
    request.session.modified = True
    return redirect(request.POST.get("next") or product.get_absolute_url())


@login_required
def wishlist(request):
    ids = request.session.get("wishlist", [])
    items = Product.objects.filter(pk__in=ids, is_active=True)
    return render(request, "products/wishlist.html", {"products": items})
