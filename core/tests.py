"""Core tests: home page, storefront context and the admin dashboard (BRD §22, §23)."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from orders.models import Order
from products.models import Category, Product


class PublicPageTests(TestCase):
    def test_home_page(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ShopSphere")

    def test_about_and_contact(self):
        self.assertEqual(self.client.get(reverse("core:about")).status_code, 200)
        response = self.client.post(
            reverse("core:contact"),
            {"name": "Asha", "email": "a@example.com", "message": "Hello"},
        )
        self.assertRedirects(response, reverse("core:contact"))
        self.assertEqual(self.client.get(reverse("core:contact")).status_code, 200)

    def test_404_page(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="boss@example.com", password="Passw0rd!", is_staff=True
        )
        self.customer = User.objects.create_user(email="cus@example.com", password="Passw0rd!")

    def test_dashboard_requires_staff(self):
        self.client.force_login(self.customer)
        for name in ["dashboard", "dashboard_products", "dashboard_orders",
                     "dashboard_customers", "dashboard_categories", "dashboard_sales",
                     "dashboard_payments"]:
            response = self.client.get(reverse(f"core:{name}"))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("login", response.url)

    def test_staff_can_open_every_dashboard_page(self):
        Product.objects.create(
            name="Item", sku="SKU-1",
            category=Category.objects.create(name="Cat"),
            price=Decimal("10"), stock_quantity=2,
        )
        self.client.force_login(self.staff)
        for name in ["dashboard", "dashboard_products", "dashboard_orders",
                     "dashboard_customers", "dashboard_categories", "dashboard_sales",
                     "dashboard_payments"]:
            response = self.client.get(reverse(f"core:{name}"))
            self.assertEqual(response.status_code, 200, name)


class DashboardActionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="boss@example.com", password="Passw0rd!", is_staff=True
        )
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Laptop", sku="SKU-1", category=self.category,
            price=Decimal("1000"), stock_quantity=5,
        )
        self.client.force_login(self.staff)

    def test_inline_stock_update(self):
        self.client.post(
            reverse("core:dashboard_product_save", args=[self.product.pk]),
            {"stock_quantity": "12"},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 12)

    def test_negative_stock_is_rejected(self):
        """BR-05"""
        self.client.post(
            reverse("core:dashboard_product_save", args=[self.product.pk]),
            {"stock_quantity": "-4"},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_negative_price_is_rejected(self):
        """BR-04"""
        self.client.post(
            reverse("core:dashboard_product_save", args=[self.product.pk]),
            {"price": "-10"},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("1000"))

    def test_toggle_active(self):
        self.client.post(
            reverse("core:dashboard_product_save", args=[self.product.pk]),
            {"is_active": "0"},
        )
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_order_status_update(self):
        user = User.objects.create_user(email="buyer@example.com", password="Passw0rd!")
        order = Order.objects.create(
            order_number="ORDTEST0001", user=user,
            shipping_full_name="Buyer", shipping_phone="9876543210",
            shipping_address_line1="1 Road", shipping_city="Bengaluru",
            shipping_state="Karnataka", shipping_pin_code="560001", shipping_country="India",
            subtotal=100, shipping_amount=50, total_amount=150,
        )
        self.client.post(
            reverse("core:dashboard_order_status", args=[order.order_number]),
            {"status": Order.Status.CONFIRMED, "note": "ready"},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_invalid_status_update_is_rejected(self):
        user = User.objects.create_user(email="buyer2@example.com", password="Passw0rd!")
        order = Order.objects.create(
            order_number="ORDTEST0002", user=user,
            shipping_full_name="Buyer", shipping_phone="9876543210",
            shipping_address_line1="1 Road", shipping_city="Bengaluru",
            shipping_state="Karnataka", shipping_pin_code="560001", shipping_country="India",
        )
        self.client.post(
            reverse("core:dashboard_order_status", args=[order.order_number]),
            {"status": Order.Status.DELIVERED},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
