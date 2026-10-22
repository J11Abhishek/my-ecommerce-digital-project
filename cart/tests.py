"""Cart tests: stock rules, totals, guest cart merge (BRD §12, §13, BR-03)."""

from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from products.models import Category, Product

from .models import Cart, CartItem
from .services import add_to_cart, get_or_create_cart, set_item_quantity


@override_settings(FREE_SHIPPING_THRESHOLD=1000, SHIPPING_FEE=50)
class CartTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electronics")
        self.product = Product.objects.create(
            name="Laptop", sku="SKU-1", category=self.category,
            price=Decimal("50000"), stock_quantity=5,
        )
        self.cheap = Product.objects.create(
            name="Cable", sku="SKU-2", category=self.category,
            price=Decimal("100"), stock_quantity=50,
        )
        self.user = User.objects.create_user(
            email="shopper@example.com", password="Passw0rd!", first_name="Asha"
        )


class CartAdditionTests(CartTestCase):
    def test_add_product_creates_item(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("cart:add", args=[self.product.pk]), {"quantity": 2}
        )
        self.assertEqual(response.status_code, 302)
        item = CartItem.objects.get()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal("100000"))

    def test_cannot_exceed_stock(self):
        """BR-03: the second add is rejected, the first quantity is untouched."""
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 4})
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 4})
        self.assertEqual(CartItem.objects.get().quantity, 4)

    def test_rejection_message_reports_the_available_stock(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 4})
        response = self.client.post(
            reverse("cart:add", args=[self.product.pk]), {"quantity": 4}, follow=True
        )
        self.assertContains(response, "Only 5 units")

    def test_out_of_stock_product_is_rejected(self):
        self.product.stock_quantity = 0
        self.product.save()
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 1})
        self.assertFalse(CartItem.objects.exists())

    def test_inactive_product_cannot_be_added(self):
        product = Product.objects.create(
            name="Hidden", sku="SKU-9", category=self.category, price=Decimal("10"),
            stock_quantity=5, is_active=False,
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("cart:add", args=[product.pk]), {"quantity": 1})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(CartItem.objects.exists())


class CartTotalsTests(CartTestCase):
    def test_shipping_and_total(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.cheap, quantity=5)  # 500 subtotal
        self.assertEqual(cart.subtotal, Decimal("500"))
        self.assertEqual(cart.shipping, Decimal("50"))
        self.assertEqual(cart.total, Decimal("550"))

    def test_free_shipping_threshold(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.cheap, quantity=10)  # 1000 subtotal
        self.assertEqual(cart.shipping, Decimal("0"))
        self.assertEqual(cart.total, Decimal("1000"))

    def test_total_items_counts_quantities(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.cheap, quantity=3)
        self.assertEqual(cart.total_items, 3)
        self.assertEqual(cart.unique_items, 1)

    def test_has_stock_issues(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=5)
        self.assertFalse(cart.has_stock_issues)
        self.product.stock_quantity = 2
        self.product.save()
        self.assertEqual(len(cart.has_stock_issues), 1)
        self.assertTrue(item.exceeds_stock)


class CartViewTests(CartTestCase):
    def test_guest_cart_is_kept_after_login(self):
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 2})
        self.assertEqual(Cart.objects.filter(user__isnull=True).count(), 1)

        self.client.login(email="shopper@example.com", password="Passw0rd!")
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.total_items, 2)
        self.assertFalse(Cart.objects.filter(user__isnull=True).exists())

    def test_cart_view_renders(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 1})
        response = self.client.get(reverse("cart:view"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop")

    def test_json_update_returns_totals(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 1})
        item = CartItem.objects.get()
        response = self.client.post(
            reverse("cart:update", args=[item.pk]),
            {"quantity": 3},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cart"]["count"], 3)

    def test_update_rejects_quantity_above_stock(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 2})
        item = CartItem.objects.get()
        self.client.post(reverse("cart:update", args=[item.pk]), {"quantity": 9})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_remove_and_clear(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cart:add", args=[self.product.pk]), {"quantity": 2})
        self.client.post(reverse("cart:add", args=[self.cheap.pk]), {"quantity": 1})
        item = CartItem.objects.get(product=self.product)
        self.client.post(reverse("cart:remove", args=[item.pk]))
        self.assertEqual(CartItem.objects.count(), 1)
        self.client.post(reverse("cart:clear"))
        self.assertFalse(CartItem.objects.exists())

    def test_get_request_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("cart:clear"))
        self.assertEqual(response.status_code, 405)
