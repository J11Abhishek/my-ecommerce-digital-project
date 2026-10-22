"""Core URLs: home, static pages and the admin dashboard."""

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    # Admin dashboard (staff only)
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/products/", views.dashboard_products, name="dashboard_products"),
    path("dashboard/products/<int:pk>/save/", views.dashboard_product_save, name="dashboard_product_save"),
    path("dashboard/categories/", views.dashboard_categories, name="dashboard_categories"),
    path("dashboard/customers/", views.dashboard_customers, name="dashboard_customers"),
    path("dashboard/orders/", views.dashboard_orders, name="dashboard_orders"),
    path("dashboard/orders/<str:order_number>/", views.dashboard_order_detail, name="dashboard_order_detail"),
    path(
        "dashboard/orders/<str:order_number>/status/",
        views.dashboard_order_status,
        name="dashboard_order_status",
    ),
    path("dashboard/payments/", views.dashboard_payments, name="dashboard_payments"),
    path("dashboard/sales/", views.dashboard_sales, name="dashboard_sales"),
]
