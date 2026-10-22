"""Payment tests for the simulated gateway (BRD §15)."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import Address, User
from cart.models import Cart, CartItem
from orders.models import Order
from orders.services import place_order
from products.models import Category, Product

from .models import Payment
from .services import process_online_payment


class PaymentTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Laptop", sku="SKU-1", category=self.category,
            price=Decimal("50000"), stock_quantity=5,
        )
        self.user = User.objects.create_user(email="pay@example.com", password="Passw0rd!")
        self.address = Address.objects.create(
            user=self.user, full_name="Pay User", phone="9876543210",
            address_line1="1 Road", city="Bengaluru", state="Karnataka", pin_code="560001",
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.order = place_order(
            user=self.user, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.ONLINE,
        )

    def test_successful_payment_marks_order_paid(self):
        ok, payment = process_online_payment(self.order, card_number="4242 4242 4242 4242")
        self.assertTrue(ok)
        self.assertTrue(payment.is_paid)
        self.assertEqual(payment.card_last4, "4242")
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_declined_card(self):
        ok, payment = process_online_payment(self.order, card_number="4000 0000 0000 0000")
        self.assertFalse(ok)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_invalid_card_number(self):
        ok, payment = process_online_payment(self.order, card_number="123")
        self.assertFalse(ok)
        self.assertIn("Invalid", payment.failure_reason)

    def test_payment_view_flow(self):
        self.client.force_login(self.user)
        url = reverse("payments:process", args=[self.order.order_number])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            url,
            {
                "card_number": "4242424242424242", "card_name": "PAY USER",
                "expiry": "12/30", "cvv": "123",
            },
        )
        self.assertRedirects(response, reverse("orders:success", args=[self.order.order_number]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_failed_payment_shows_error(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("payments:process", args=[self.order.order_number]),
            {"card_number": "4000000000000000", "card_name": "X", "expiry": "12/30", "cvv": "123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "declined")

    def test_cod_order_skips_the_payment_page(self):
        cart = Cart.objects.get(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        cod_order = place_order(
            user=self.user, cart=cart, address=self.address,
            payment_method=Order.PaymentMethod.COD,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("payments:process", args=[cod_order.order_number]))
        self.assertRedirects(response, reverse("orders:success", args=[cod_order.order_number]))
        self.assertTrue(Payment.objects.filter(order=cod_order).exists())

    def test_other_customers_cannot_pay(self):
        intruder = User.objects.create_user(email="no@example.com", password="Passw0rd!")
        self.client.force_login(intruder)
        response = self.client.get(reverse("payments:process", args=[self.order.order_number]))
        self.assertEqual(response.status_code, 404)
