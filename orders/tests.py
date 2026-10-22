"""Order tests: placement, stock, snapshots, cancellation (BRD §16-§19, §24)."""

from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Address, User
from cart.models import Cart, CartItem
from products.models import Category, Product

from .business import InvalidStatusTransition, cancel_order, transition_order
from .models import Order, OrderItem
from .services import OrderError, generate_order_number, place_order


@override_settings(SHIPPING_FEE=50, FREE_SHIPPING_THRESHOLD=1000)
class OrderTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.laptop = Product.objects.create(
            name="Laptop", sku="SKU-1", category=self.category,
            price=Decimal("50000"), stock_quantity=10,
        )
        self.mouse = Product.objects.create(
            name="Mouse", sku="SKU-2", category=self.category,
            price=Decimal("1000"), stock_quantity=10,
        )
        self.user = User.objects.create_user(
            email="buyer@example.com", password="Passw0rd!", first_name="Rahul", last_name="S"
        )
        self.address = Address.objects.create(
            user=self.user, label="Home", full_name="Rahul S", phone="9876543210",
            address_line1="12 MG Road", city="Bengaluru", state="Karnataka",
            pin_code="560001", country="India", is_default=True,
        )
        self.cart = Cart.objects.create(user=self.user)

    def fill_cart(self, laptop_qty=1, mouse_qty=2):
        CartItem.objects.create(cart=self.cart, product=self.laptop, quantity=laptop_qty)
        CartItem.objects.create(cart=self.cart, product=self.mouse, quantity=mouse_qty)

    def place(self, **kwargs):
        return place_order(
            user=self.user,
            cart=self.cart,
            address=kwargs.pop("address", self.address),
            payment_method=kwargs.pop("payment_method", Order.PaymentMethod.COD),
            **kwargs,
        )


class OrderPlacementTests(OrderTestCase):
    def test_place_order_creates_order_items_and_clears_cart(self):
        """BRD §32 acceptance criteria"""
        self.fill_cart()
        order = self.place()

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.subtotal, Decimal("52000"))
        self.assertEqual(order.total_amount, Decimal("52000"))  # free shipping
        self.assertFalse(CartItem.objects.exists())
        self.assertTrue(order.order_number.startswith("ORD"))

    def test_stock_is_reduced(self):
        """BRD §24"""
        self.fill_cart(laptop_qty=2)
        self.place()
        self.laptop.refresh_from_db()
        self.mouse.refresh_from_db()
        self.assertEqual(self.laptop.stock_quantity, 8)
        self.assertEqual(self.mouse.stock_quantity, 8)

    @override_settings(FREE_SHIPPING_THRESHOLD=5000)
    def test_shipping_fee_applied_below_threshold(self):
        CartItem.objects.create(cart=self.cart, product=self.mouse, quantity=1)
        order = self.place()
        self.assertEqual(order.shipping_amount, Decimal("50"))
        self.assertEqual(order.total_amount, Decimal("1050"))

    def test_price_snapshot_survives_product_price_change(self):
        """BR-07"""
        self.fill_cart()
        order = self.place()
        self.laptop.price = Decimal("1")
        self.laptop.save()
        item = order.items.get(product=self.laptop)
        self.assertEqual(item.unit_price, Decimal("50000"))

    def test_empty_cart_is_rejected(self):
        """BR-06"""
        with self.assertRaisesMessage(OrderError, "cart is empty"):
            self.place()

    def test_anonymous_user_is_rejected(self):
        """BR-01"""
        from django.contrib.auth.models import AnonymousUser

        self.fill_cart()
        with self.assertRaisesMessage(OrderError, "signed in"):
            place_order(
                user=AnonymousUser(), cart=self.cart, address=self.address,
                payment_method=Order.PaymentMethod.COD,
            )

    def test_insufficient_stock_rolls_back(self):
        """BR-03: nothing is written when a line exceeds stock"""
        self.fill_cart(laptop_qty=9)
        self.laptop.stock_quantity = 3
        self.laptop.save()

        with self.assertRaisesMessage(OrderError, "Only 3 units"):
            self.place()

        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.exists())
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock_quantity, 3)

    def test_incomplete_address_is_rejected(self):
        self.fill_cart()
        with self.assertRaisesMessage(OrderError, "delivery address"):
            self.place(address={"full_name": "Rahul"})

    def test_new_address_can_be_saved(self):
        self.fill_cart(mouse_qty=0, laptop_qty=1)
        address = {
            "full_name": "Rahul S", "phone": "9876543210", "address_line1": "5 Park Street",
            "address_line2": "", "city": "Mumbai", "state": "Maharashtra",
            "pin_code": "400001", "country": "India",
        }
        order = self.place(address=address, save_address=True)
        self.assertEqual(order.shipping_city, "Mumbai")
        self.assertEqual(self.user.addresses.count(), 2)

    def test_order_number_is_unique(self):
        numbers = {generate_order_number() for _ in range(20)}
        self.assertEqual(len(numbers), 20)


class OrderStatusTests(OrderTestCase):
    def make_order(self, **kwargs):
        self.fill_cart(laptop_qty=1, mouse_qty=0)
        return self.place(**kwargs)

    def test_happy_path_transitions(self):
        order = self.make_order()
        for status in [Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED]:
            transition_order(order, status, user=self.user)
            order.refresh_from_db()
            self.assertEqual(order.status, status)

    def test_invalid_transition_is_rejected(self):
        order = self.make_order()
        with self.assertRaises(InvalidStatusTransition):
            transition_order(order, Order.Status.DELIVERED, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_cancel_before_shipping_restores_stock(self):
        """BRD §19 + §24"""
        order = self.make_order()
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock_quantity, 9)

        cancel_order(order, user=self.user, reason="changed my mind")
        order.refresh_from_db()
        self.laptop.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertTrue(order.stock_reversed)
        self.assertEqual(self.laptop.stock_quantity, 10)

    def test_cancel_after_shipping_is_blocked(self):
        """BR-10"""
        order = self.make_order()
        transition_order(order, Order.Status.CONFIRMED, user=self.user)
        transition_order(order, Order.Status.PROCESSING, user=self.user)
        transition_order(order, Order.Status.SHIPPED, user=self.user)
        order.refresh_from_db()

        with self.assertRaises(InvalidStatusTransition):
            cancel_order(order, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)

    def test_stock_is_restored_only_once(self):
        order = self.make_order()
        cancel_order(order, user=self.user)
        from .business import reverse_stock_for

        reverse_stock_for(order)
        self.laptop.refresh_from_db()
        self.assertEqual(self.laptop.stock_quantity, 10)

    def test_cod_order_is_marked_paid_on_delivery(self):
        order = self.make_order()
        for status in [Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED]:
            transition_order(order, status, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_cancelling_paid_order_refunds(self):
        order = self.make_order()
        order.payment_status = Order.PaymentStatus.PAID
        order.save()
        transition_order(order, Order.Status.CANCELLED, user=self.user)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.REFUNDED)

    def test_status_log_is_recorded(self):
        order = self.make_order()
        transition_order(order, Order.Status.CONFIRMED, user=self.user, note="stock ready")
        self.assertEqual(order.status_logs.count(), 2)
        self.assertTrue(order.status_logs.filter(note="stock ready", to_status=Order.Status.CONFIRMED).exists())


class OrderViewTests(OrderTestCase):
    def test_checkout_requires_login(self):
        self.fill_cart()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_checkout_with_empty_cart_redirects(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("cart:view"))

    def test_full_cod_checkout_flow(self):
        self.client.force_login(self.user)
        self.fill_cart(laptop_qty=1, mouse_qty=2)
        response = self.client.post(
            reverse("orders:checkout"),
            {"saved_address": self.address.pk, "payment_method": Order.PaymentMethod.COD},
        )
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:success", args=[order.order_number]))
        self.assertEqual(order.shipping_full_name, "Rahul S")
        self.assertFalse(CartItem.objects.exists())

    def test_checkout_without_address_uses_typed_address(self):
        self.client.force_login(self.user)
        self.fill_cart(laptop_qty=1, mouse_qty=0)
        response = self.client.post(
            reverse("orders:checkout"),
            {
                "payment_method": Order.PaymentMethod.COD,
                "new_full_name": "Rahul S",
                "new_phone": "9876543210",
                "new_address_line1": "9 Residency Road",
                "new_city": "Bengaluru",
                "new_state": "Karnataka",
                "new_pin_code": "560025",
                "new_country": "India",
            },
        )
        order = Order.objects.get()
        self.assertEqual(order.shipping_address_line1, "9 Residency Road")
        self.assertEqual(response.status_code, 302)

    def test_online_payment_redirects_to_gateway(self):
        self.client.force_login(self.user)
        self.fill_cart(laptop_qty=1, mouse_qty=0)
        response = self.client.post(
            reverse("orders:checkout"),
            {"saved_address": self.address.pk, "payment_method": Order.PaymentMethod.ONLINE},
        )
        order = Order.objects.get()
        self.assertRedirects(response, reverse("payments:process", args=[order.order_number]))

    def test_customer_cannot_view_other_customers_order(self):
        """BR-09"""
        order = self.make_order_helper()
        other = User.objects.create_user(email="other@example.com", password="Passw0rd!")
        self.client.force_login(other)
        response = self.client.get(reverse("orders:detail", args=[order.order_number]))
        self.assertEqual(response.status_code, 404)

    def make_order_helper(self):
        CartItem.objects.create(cart=self.cart, product=self.laptop, quantity=1)
        return self.place()

    def test_order_cancel_view(self):
        order = self.make_order_helper()
        self.client.force_login(self.user)
        self.client.post(reverse("orders:cancel", args=[order.order_number]), {"reason": "test"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_order_history_only_shows_own_orders(self):
        mine = self.make_order_helper()
        other = User.objects.create_user(email="other@example.com", password="Passw0rd!")
        other_cart = Cart.objects.create(user=other)
        CartItem.objects.create(cart=other_cart, product=self.mouse, quantity=1)
        place_order(user=other, cart=other_cart, address=self.address, payment_method=Order.PaymentMethod.COD)

        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:list"))
        self.assertContains(response, mine.order_number)
        self.assertEqual(len(response.context["orders"]), 1)

    def test_invoice_renders(self):
        order = self.make_order_helper()
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:invoice", args=[order.order_number]))
        self.assertContains(response, "Invoice")
