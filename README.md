# ShopSphere

A Django e-commerce practice project built from the Business Requirements Document
(BRD). It implements the full customer purchase workflow plus staff management
screens, with SQLite for development and a simulated (mock) payment gateway.

## Tech stack

| Layer     | Choice                                              |
| --------- | --------------------------------------------------- |
| Framework | Django 6.1 (Python 3.12)                             |
| Database  | SQLite by default, PostgreSQL supported via `.env`  |
| Auth      | Custom `User` model, email + password, no username  |
| Payments  | COD and a simulated card gateway (no real gateway)  |
| Static    | WhiteNoise in production, plain static files locally |
| Config    | `python-decouple` (`.env`)                           |

## Quick start

```bat
:: 1. Create and activate the virtual environment
python -m venv .venv
.venv\Scripts\activate

:: 2. Install dependencies
pip install -r requirements.txt

:: 3. Configure the environment
copy .env.example .env

:: 4. Create the database
python manage.py migrate

:: 5. Load demo data (optional but recommended)
python manage.py seed_data --reset

:: 6. Run the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

### Demo logins

| Role    | Email                      | Password      |
| ------- | -------------------------- | ------------- |
| Admin   | `admin@shopsphere.local`   | `Admin@123`   |
| Customer| `vikram@example.com`       | `Passw0rd!`   |
| Customer| `sneha@example.com`        | `Passw0rd!`   |

Any seeded customer can be used. The admin account also reaches the custom staff
dashboard at `/dashboard/`.

## Tests

```bat
.venv\Scripts\python.exe manage.py test
```

92 tests covering products, cart, checkout, orders, payments, accounts and the
staff dashboard. Use `--keepdb` to speed up repeat runs.

## Business rules implemented

| Rule | Behaviour |
| ---- | --------- |
| BR-01 Stock | Every add/update is validated against `Product.stock_quantity`. |
| BR-02 Cart   | Guest carts are stored by session and merged into the user cart on login. |
| BR-03 Limits | A request exceeding available stock is rejected with a message showing the available quantity. |
| BR-04 Pricing | Product prices are snapshotted onto `OrderItem.unit_price` at purchase time. |
| BR-05/06 Checkout | Address can be reused from the address book or typed in; COD and online payment are both supported. |
| BR-07 Reports  | Sales, top products and category revenue come from historical order items, not live prices. |
| BR-08 Payments | COD stays `PENDING`; online payments use a simulated gateway and mark the order `PAID` on success. |
| BR-09/10 Orders | Status flow `PENDING -> CONFIRMED -> SHIPPED -> DELIVERED` plus `CANCELLED`; every transition is logged in `OrderStatusLog`. |
| BR-11 Cancel   | Customers may cancel their own pending orders; stock is restored exactly once. |
| BR-12 Stock on cancel | Restoration is guarded by `stock_reversed` and runs inside the same transaction. |
| BR-13 Security | Staff-only dashboard, staff-only order transitions, customers only see their own orders. |
| BR-14/15 Cart UX | Quantity edit, remove, clear, and live totals via the JSON cart endpoint. |
| BR-16 Addresses | Address book with one default address; used to prefill checkout. |
| BR-17 Admin    | Django admin plus a custom dashboard for products, categories, customers, orders, payments and sales. |

## Project layout

```
ecommerce/          project settings and root URLs
core/               homepage, dashboard, reports, context processors, seed command
accounts/           custom User, Profile, Address, auth and profile views
products/           Category, Product, catalogue search/filter/sort/pagination
cart/               Cart, CartItem, guest-cart merge, JSON quantity updates
orders/             checkout, order placement service, status machine, invoices
payments/           COD and simulated online payment processing
templates/          base template and shared partials
static/             CSS and JavaScript
media/              uploaded product images
```

## Environment variables (`.env`)

See `.env.example` for the full list.

| Variable | Purpose |
| -------- | ------- |
| `SECRET_KEY` | Django secret key. |
| `DEBUG` | `True` for local development. |
| `ALLOWED_HOSTS` | Comma-separated host list. |
| `DB_ENGINE` | `sqlite` (default) or `postgresql`. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Used when `DB_ENGINE=postgresql`. |
| `CURRENCY_SYMBOL` | Display symbol. |
| `FREE_SHIPPING_THRESHOLD`, `STANDARD_SHIPPING_COST` | Shipping rules. |

## Notes

- Product images are generated locally on seed, so no network access is needed.
- `python manage.py check --deploy` reports the expected warnings for a local
  project (`DEBUG=True`, development secret key, no HTTPS-only cookies). Set
  `DEBUG=False` and a long random `SECRET_KEY` before deploying anywhere real.
- Online payments are intentionally simulated: any card details are accepted and
  no money moves. Do not reuse this code for real payments.
