"""Order URLs (BRD §31)."""

from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("success/<str:order_number>/", views.order_success, name="success"),
    path("my-orders/", views.order_list, name="list"),
    path("<str:order_number>/", views.order_detail, name="detail"),
    path("<str:order_number>/cancel/", views.order_cancel, name="cancel"),
    path("<str:order_number>/invoice/", views.order_invoice, name="invoice"),
]
