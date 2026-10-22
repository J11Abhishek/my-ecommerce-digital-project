"""Populate the database with demo categories, products, users and orders.

    python manage.py seed_data            # create anything that is missing
    python manage.py seed_data --reset    # wipe demo rows first
    python manage.py seed_data --orders 25
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem, OrderStatusLog
from payments.models import Payment
from products.models import Category, Product

User = get_user_model()

CATEGORIES = [
    ("Electronics", "Laptops, phones, audio and accessories."),
    ("Clothing", "Everyday wear for men and women."),
    ("Books", "Fiction, technical and self-help titles."),
    ("Shoes", "Sneakers, formal shoes and sandals."),
    ("Home & Kitchen", "Cookware, storage and small appliances."),
]

# (name, sku, category, price, stock, featured, description)
PRODUCTS = [
    ("AeroBook 14 Laptop", "ELEC-1001", "Electronics", "54900", 12, True,
     "14-inch ultrabook with a 12th-gen Core i5, 16GB RAM and a 512GB SSD. "
     "1.4kg magnesium chassis, 10-hour battery and a full HD IPS display."),
    ("AeroBook 15 Pro Laptop", "ELEC-1002", "Electronics", "89900", 7, True,
     "15.6-inch performance laptop with a Ryzen 7 processor, 16GB RAM, dedicated "
     "graphics and a 1TB NVMe drive."),
    ("Pulse ANC Headphones", "ELEC-1003", "Electronics", "8999", 25, True,
     "Over-ear wireless headphones with active noise cancellation, 40mm drivers "
     "and 30 hours of playback."),
    ("Brite Mini LED Monitor 24\"", "ELEC-1004", "Electronics", "12999", 15, False,
     "24-inch IPS panel with 75Hz refresh rate, thin bezels and HDMI/VGA inputs."),
    ("Zap 65W GaN Charger", "ELEC-1005", "Electronics", "2499", 60, False,
     "Compact GaN fast charger with two USB-C and one USB-A port. Charges a "
     "laptop and a phone at the same time."),
    ("Nimbus 65W Wireless Mouse", "ELEC-1006", "Electronics", "1299", 42, False,
     "Silent-click ergonomic mouse with 4000 DPI sensor and USB-C charging."),
    ("KeyCraft Mechanical Keyboard", "ELEC-1007", "Electronics", "4499", 18, False,
     "Compact 75% mechanical keyboard with hot-swappable switches and RGB backlight."),
    ("StreamCam 1080p Webcam", "ELEC-1008", "Electronics", "3499", 0, False,
     "Full HD webcam with a dual microphone array and a privacy shutter."),
    ("Everyday Cotton T-Shirt", "CLTH-2001", "Clothing", "799", 80, True,
     "180 GSM combed cotton t-shirt with a regular fit. Machine washable, colour fast."),
    ("Oxford Button-Down Shirt", "CLTH-2002", "Clothing", "1899", 45, False,
     "Wrinkle-resistant cotton oxford shirt with mother-of-pearl buttons."),
    ("Classic Denim Jeans", "CLTH-2003", "Clothing", "2499", 38, False,
     "Slim-fit stretch denim jeans with a mid rise and five pockets."),
    ("Winter Knit Sweater", "CLTH-2004", "Clothing", "2799", 26, False,
     "Warm lambswool-blend crew neck sweater, ideal for cold weather."),
    ("Running Sports Shoe", "SHOE-3001", "Shoes", "4299", 30, True,
     "Lightweight breathable running shoe with a cushioned foam midsole and rubber outsole."),
    ("Leather Formal Shoes", "SHOE-3002", "Shoes", "5499", 14, False,
     "Genuine leather formal shoes with a leather sole and cushioned insole."),
    ("Canvas Casual Sneakers", "SHOE-3003", "Shoes", "1999", 0, False,
     "Vulcanised canvas sneakers with a padded collar and rubber toe cap."),
    ("The Pragmatic Coder", "BOOK-4001", "Books", "699", 50, True,
     "A practical guide to software craftsmanship: clean code, testing, review and "
     "the habits that keep a codebase healthy."),
    ("Designing Data-Intensive Apps", "BOOK-4002", "Books", "899", 33, False,
     "The big ideas behind reliable, scalable and maintainable systems."),
    ("Django for Beginners", "BOOK-4003", "Books", "599", 41, False,
     "Build and deploy a production-ready Django project step by step."),
    ("The Rust Programming Language", "BOOK-4004", "Books", "749", 20, False,
     "Ownership, borrowing and lifetimes explained with worked examples."),
    ("Stainless Steel Kadhai 3L", "HOME-5001", "Home & Kitchen", "2199", 22, False,
     "Tri-ply stainless steel kadhai with a bakelite handle and a glass lid."),
    ("Mixer Grinder 750W", "HOME-5002", "Home & Kitchen", "3499", 17, False,
     "750W mixer grinder with three stainless steel jars and a pulse function."),
    ("Bamboo Storage Basket Set", "HOME-5003", "Home & Kitchen", "1299", 35, False,
     "Set of four nesting bamboo baskets with a water-resistant lining."),
    ("Air Fryer 4.5L", "HOME-5004", "Home & Kitchen", "4999", 9, True,
     "Digital air fryer with eight presets, a non-stick basket and a 4.5 litre capacity."),
    ("Ceramic Dinner Set (16 pc)", "HOME-5005", "Home & Kitchen", "2799", 0, False,
     "Sixteen piece vitrified ceramic dinner set, dishwasher safe."),
]

CUSTOMERS = [
    ("Rahul", "Sharma", "rahul@example.com", "9876543210"),
    ("Priya", "Nair", "priya@example.com", "9876500011"),
    ("Amit", "Patel", "amit@example.com", "9822003344"),
    ("Sneha", "Iyer", "sneha@example.com", "9769112233"),
    ("Vikram", "Singh", "vikram@example.com", "9811223344"),
]

CITIES = [
    ("Bengaluru", "Karnataka", "560001"),
    ("Mumbai", "Maharashtra", "400001"),
    ("Delhi", "Delhi", "110001"),
    ("Pune", "Maharashtra", "411001"),
    ("Chennai", "Tamil Nadu", "600001"),
    ("Hyderabad", "Telangana", "500001"),
]

STATUS_FLOW = [
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.CANCELLED,
]


class Command(BaseCommand):
    help = "Create demo categories, products, customers and orders."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete demo data first.")
        parser.add_argument("--orders", type=int, default=12, help="How many demo orders to create.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        if options["reset"]:
            self.stdout.write("Removing existing demo data...")
            OrderItem.objects.all().delete()
            OrderStatusLog.objects.all().delete()
            Payment.objects.all().delete()
            Order.objects.all().delete()
            CartItem.objects.all().delete()
            Cart.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(email__in=[c[2] for c in CUSTOMERS]).delete()

        categories = self.create_categories()
        products = self.create_products(categories)
        users = self.create_customers()
        self.create_orders(products, users, options["orders"])

        self.stdout.write(self.style.SUCCESS("\nDemo data ready."))
        self.stdout.write(f"  Categories : {Category.objects.count()}")
        self.stdout.write(f"  Products   : {Product.objects.count()}")
        self.stdout.write(f"  Customers  : {User.objects.filter(is_staff=False).count()}")
        self.stdout.write(f"  Orders     : {Order.objects.count()}")
        self.stdout.write("\nCustomer logins (password: Passw0rd!):")
        for user in User.objects.filter(email__in=[c[2] for c in CUSTOMERS]):
            self.stdout.write(f"  {user.email}")
        self.stdout.write("\nAdmin login (password: Admin@123):")
        self.stdout.write("  admin@shopsphere.local")

    # -- pieces -----------------------------------------------------------
    def create_categories(self):
        result = {}
        for name, description in CATEGORIES:
            category, _ = Category.objects.get_or_create(
                name=name, defaults={"description": description, "slug": slugify(name)}
            )
            result[name] = category
        self.stdout.write(f"Categories: {len(result)}")
        return result

    def create_products(self, categories):
        result = []
        for name, sku, category_name, price, stock, featured, description in PRODUCTS:
            product, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "slug": slugify(name),
                    "category": categories[category_name],
                    "price": Decimal(price),
                    "stock_quantity": stock,
                    "is_featured": featured,
                    "is_active": True,
                    "description": description,
                    "short_description": description[:120],
                },
            )
            result.append(product)
        self.stdout.write(f"Products: {len(result)}")
        return result

    def create_customers(self):
        users = []
        for first, last, email, phone in CUSTOMERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "phone": phone,
                    "is_staff": False,
                },
            )
            if created:
                user.set_password("Passw0rd!")
                user.save()
            if not user.addresses.exists():
                city, state, pin = random.choice(CITIES)
                Address.objects.create(
                    user=user,
                    label="Home",
                    full_name=f"{first} {last}",
                    phone=phone,
                    address_line1=f"{random.randint(1, 200)}, {random.choice(['MG Road', 'Park Street', 'Linking Road', 'Anna Salai'])}",
                    address_line2="",
                    city=city,
                    state=state,
                    pin_code=pin,
                    country="India",
                    is_default=True,
                )
            users.append(user)

        # Administrator (BRD §22)
        admin, created = User.objects.get_or_create(
            email="admin@shopsphere.local",
            defaults={
                "first_name": "Store",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("Admin@123")
            admin.save()
        self.stdout.write(f"Customers: {len(users)} (+1 admin)")
        return users

    def create_orders(self, products, users, count):
        in_stock = [p for p in products if p.stock_quantity > 0]
        created = 0
        for index in range(count):
            user = random.choice(users)
            address = user.addresses.first()
            if address is None:
                continue

            lines = random.sample(in_stock, k=min(len(in_stock), random.randint(1, 3)))
            items = [(p, min(random.randint(1, 3), p.stock_quantity)) for p in lines]
            subtotal = sum((p.price * q for p, q in items), start=Decimal("0.00"))
            shipping = Decimal("0.00") if subtotal >= 1000 else Decimal("50.00")
            method = random.choice([Order.PaymentMethod.COD, Order.PaymentMethod.ONLINE])
            status = STATUS_FLOW[index % len(STATUS_FLOW)]
            paid = status in {Order.Status.SHIPPED, Order.Status.DELIVERED} or method == Order.PaymentMethod.COD
            days_ago = (count - index) * 3

            order = Order.objects.create(
                order_number=f"ORD{timezone.now():%y%m%d}{1000 + index}",
                user=user,
                status=status,
                payment_method=method,
                payment_status=(
                    Order.PaymentStatus.PAID
                    if paid
                    else Order.PaymentStatus.PENDING
                ),
                subtotal=subtotal,
                shipping_amount=shipping,
                total_amount=subtotal + shipping,
                shipping_full_name=address.full_name,
                shipping_phone=address.phone,
                shipping_address_line1=address.address_line1,
                shipping_address_line2=address.address_line2,
                shipping_city=address.city,
                shipping_state=address.state,
                shipping_pin_code=address.pin_code,
                shipping_country=address.country,
                placed_at=timezone.now() - timedelta(days=days_ago),
            )
            order.status_logs.create(
                from_status="", to_status=Order.Status.PENDING, note="Order placed by customer"
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=p,
                        product_name=p.name,
                        sku=p.sku,
                        unit_price=p.price,
                        quantity=q,
                    )
                    for p, q in items
                ]
            )
            Payment.objects.create(
                order=order,
                method=method,
                status=Order.PaymentStatus.PAID if paid else Order.PaymentStatus.PENDING,
                amount=order.total_amount,
                transaction_id=f"MP{timezone.now():%Y%m%d}{index:04d}" if paid else "",
                paid_at=timezone.now() - timedelta(days=days_ago) if paid else None,
            )
            created += 1

        self.stdout.write(f"Orders: {created}")
