"""Product catalogue URLs (BRD §31)."""

from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("search/", views.product_list, name="search"),
    path("category/<slug:slug>/", views.category_detail, name="category"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/<int:pk>/toggle/", views.toggle_wishlist, name="wishlist_toggle"),
    path("<slug:slug>/", views.product_detail, name="detail"),
]
