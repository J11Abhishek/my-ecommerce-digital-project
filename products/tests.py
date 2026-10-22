"""Products app tests: search, filtering, sorting, pagination (BRD §8-§11)."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Product
from .services import apply_filters, build_filters


class ProductFactoryMixin:
    def setUp(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.books = Category.objects.create(name="Books")
        self.laptop = Product.objects.create(
            name="Pro Laptop 15", sku="SKU-1", category=self.electronics,
            price=Decimal("50000"), stock_quantity=5, is_active=True,
        )
        self.mouse = Product.objects.create(
            name="Wireless Mouse", sku="SKU-2", category=self.electronics,
            price=Decimal("1000"), stock_quantity=0, is_active=True,
        )
        self.book = Product.objects.create(
            name="Django Handbook", sku="SKU-3", category=self.books,
            price=Decimal("500"), stock_quantity=10, is_active=True,
        )
        self.hidden = Product.objects.create(
            name="Secret Gadget", sku="SKU-4", category=self.electronics,
            price=Decimal("9999"), stock_quantity=3, is_active=False,
        )


class ProductQueryTests(ProductFactoryMixin, TestCase):
    def test_active_hides_inactive_products(self):
        """BR-02"""
        names = list(Product.objects.active().values_list("name", flat=True))
        self.assertNotIn("Secret Gadget", names)
        self.assertIn("Pro Laptop 15", names)

    def test_search_matches_name_description_and_sku(self):
        self.assertIn(self.laptop, Product.objects.active().search("laptop"))
        self.assertIn(self.book, Product.objects.active().search("django"))
        self.assertIn(self.mouse, Product.objects.active().search("sku-2"))

    def test_stock_helpers(self):
        self.assertTrue(self.laptop.in_stock)
        self.assertTrue(self.mouse.is_out_of_stock)
        self.assertEqual(self.mouse.stock_label, "Out of Stock")
        self.assertEqual(self.book.stock_label, "In Stock")


class FilterServiceTests(ProductFactoryMixin, TestCase):
    def test_price_range_filter(self):
        filters = build_filters({"min_price": "1000", "max_price": "60000"})
        result = apply_filters(Product.objects.active(), filters)
        self.assertIn(self.laptop, result)
        self.assertNotIn(self.book, result)

    def test_invalid_price_is_ignored(self):
        filters = build_filters({"min_price": "abc", "max_price": "-5"})
        self.assertIsNone(filters["min_price"])
        self.assertIsNone(filters["max_price"])

    def test_availability_filter(self):
        out_of_stock = apply_filters(Product.objects.active(), build_filters({"availability": "out_of_stock"}))
        self.assertEqual([p.pk for p in out_of_stock], [self.mouse.pk])

    def test_category_and_sort(self):
        filters = build_filters({"category": self.books.slug, "sort": "price_asc"})
        result = apply_filters(Product.objects.active(), filters)
        self.assertEqual([p.pk for p in result], [self.book.pk])

    def test_unknown_sort_falls_back(self):
        self.assertEqual(build_filters({"sort": "'; DROP TABLE"})["sort"], "newest")


class ProductViewTests(ProductFactoryMixin, TestCase):
    def test_list_shows_only_active_products(self):
        response = self.client.get(reverse("products:list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Secret Gadget")
        self.assertContains(response, "Pro Laptop 15")

    def test_search_view(self):
        response = self.client.get(reverse("products:search"), {"q": "laptop"})
        self.assertContains(response, "Pro Laptop 15")
        self.assertNotContains(response, "Django Handbook")

    def test_detail_page_hides_out_of_stock_cta(self):
        response = self.client.get(self.mouse.get_absolute_url())
        self.assertContains(response, "Out of Stock")
        self.assertContains(response, "disabled")

    def test_inactive_product_detail_is_404(self):
        response = self.client.get(self.hidden.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_pagination(self):
        for index in range(15):
            Product.objects.create(
                name=f"Bulk {index}", sku=f"BULK-{index}", category=self.books,
                price=Decimal("100"), stock_quantity=1,
            )
        response = self.client.get(reverse("products:list"))
        self.assertEqual(len(response.context["products"]), 12)
        self.assertTrue(response.context["page_obj"].has_next())

        page_two = self.client.get(reverse("products:list"), {"page": 2})
        self.assertEqual(page_two.status_code, 200)
        self.assertEqual(len(page_two.context["products"]), 6)
        self.assertFalse(page_two.context["page_obj"].has_next())

    def test_pagination_out_of_range_falls_back_to_last_page(self):
        response = self.client.get(reverse("products:list"), {"page": 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 1)
