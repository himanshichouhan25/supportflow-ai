"""
backend/seed_data.py — Realistic demo data seeder for ShopKart.

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.seed_data

Safe to run more than once: each record is inserted only if its unique
business-key ID does not already exist in the database.

Demo Scenarios covered
----------------------
A  Order ORD005  — payment SUCCESS while order status is PENDING
B  Order ORD002  — DELIVERED order with DELIVERED delivery
C  Order ORD007  — CANCELLED order with a REFUNDED payment
D  Order ORD009  — DELIVERED order with a DELAYED delivery record
E  Order ORD010  — PENDING order with a FAILED payment
"""

import sys
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

# Import models so Base.metadata is populated (required for create_all fallback)
from backend.models.customer import Customer
from backend.models.delivery import Delivery
from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.product import Product
from backend.database import SessionLocal


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

CUSTOMERS = [
    {
        "customer_id": "C101",
        "name": "Aarav Sharma",
        "email": "aarav.sharma@example.com",
        "phone": "+91-9876543210",
        "account_status": "active",
        "created_at": _utc(2024, 1, 10),
    },
    {
        "customer_id": "C102",
        "name": "Priya Mehta",
        "email": "priya.mehta@example.com",
        "phone": "+91-9123456780",
        "account_status": "active",
        "created_at": _utc(2024, 2, 14),
    },
    {
        "customer_id": "C103",
        "name": "Rohit Verma",
        "email": "rohit.verma@example.com",
        "phone": "+91-9988776655",
        "account_status": "active",
        "created_at": _utc(2024, 3, 5),
    },
    {
        "customer_id": "C104",
        "name": "Sneha Patil",
        "email": "sneha.patil@example.com",
        "phone": "+91-9845123456",
        "account_status": "suspended",
        "created_at": _utc(2024, 4, 20),
    },
    {
        "customer_id": "C105",
        "name": "Karan Joshi",
        "email": "karan.joshi@example.com",
        "phone": "+91-9001234567",
        "account_status": "active",
        "created_at": _utc(2024, 5, 1),
    },
]

PRODUCTS = [
    {
        "product_id": "P001",
        "name": "Apple iPhone 15",
        "category": "Smartphones",
        "price": "79999.00",
        "stock": 120,
        "store": "ShopKart",
    },
    {
        "product_id": "P002",
        "name": "Samsung Galaxy S24",
        "category": "Smartphones",
        "price": "69999.00",
        "stock": 95,
        "store": "ShopKart",
    },
    {
        "product_id": "P003",
        "name": "ASUS Vivobook 15 Laptop",
        "category": "Laptops",
        "price": "54999.00",
        "stock": 40,
        "store": "ShopKart",
    },
    {
        "product_id": "P004",
        "name": "Sony WH-1000XM5 Headphones",
        "category": "Audio",
        "price": "29999.00",
        "stock": 60,
        "store": "ShopKart",
    },
    {
        "product_id": "P005",
        "name": "Nike Air Max 270",
        "category": "Footwear",
        "price": "8999.00",
        "stock": 200,
        "store": "ShopKart",
    },
    {
        "product_id": "P006",
        "name": "boAt Airdopes 141 Earbuds",
        "category": "Audio",
        "price": "1299.00",
        "stock": 350,
        "store": "ShopKart",
    },
    {
        "product_id": "P007",
        "name": "Philips HD9200 Air Fryer",
        "category": "Kitchen Appliances",
        "price": "6499.00",
        "stock": 75,
        "store": "ShopKart",
    },
    {
        "product_id": "P008",
        "name": "Python Crash Course (3rd Edition)",
        "category": "Books",
        "price": "799.00",
        "stock": 500,
        "store": "ShopKart",
    },
    {
        "product_id": "P009",
        "name": "Logitech MX Master 3 Mouse",
        "category": "Accessories",
        "price": "9999.00",
        "stock": 85,
        "store": "ShopKart",
    },
    {
        "product_id": "P010",
        "name": "Syska LED Smart Bulb 9W",
        "category": "Home & Lighting",
        "price": "349.00",
        "stock": 800,
        "store": "ShopKart",
    },
]

# price lookup (product_id → unit price as string for Decimal conversion)
_PRICE = {p["product_id"]: p["price"] for p in PRODUCTS}


def _amount(product_id: str, qty: int) -> str:
    """Calculate total order amount = unit_price × quantity."""
    from decimal import Decimal
    return str(Decimal(_PRICE[product_id]) * qty)


ORDERS = [
    # ORD001 — normal confirmed order
    {
        "order_id": "ORD001",
        "customer_id": "C101",
        "product_id": "P001",   # iPhone 15 — 79999
        "quantity": 1,
        "order_status": "CONFIRMED",
        "order_date": _utc(2024, 6, 1, 10, 30),
    },
    # ORD002 — Scenario B: DELIVERED order (C102 bought Sony Headphones)
    {
        "order_id": "ORD002",
        "customer_id": "C102",
        "product_id": "P004",   # Sony Headphones — 29999
        "quantity": 1,
        "order_status": "DELIVERED",
        "order_date": _utc(2024, 6, 5, 9, 0),
    },
    # ORD003 — normal CONFIRMED order
    {
        "order_id": "ORD003",
        "customer_id": "C103",
        "product_id": "P003",   # ASUS Laptop — 54999
        "quantity": 1,
        "order_status": "CONFIRMED",
        "order_date": _utc(2024, 6, 8, 14, 0),
    },
    # ORD004 — DELIVERED order for C104
    {
        "order_id": "ORD004",
        "customer_id": "C104",
        "product_id": "P005",   # Nike Shoes — 8999 × 2
        "quantity": 2,
        "order_status": "DELIVERED",
        "order_date": _utc(2024, 6, 10, 11, 0),
    },
    # ORD005 — Scenario A: order is PENDING but payment is SUCCESS
    {
        "order_id": "ORD005",
        "customer_id": "C105",
        "product_id": "P002",   # Samsung Galaxy S24 — 69999
        "quantity": 1,
        "order_status": "PENDING",
        "order_date": _utc(2024, 6, 12, 16, 45),
    },
    # ORD006 — C101 buys earbuds (small order)
    {
        "order_id": "ORD006",
        "customer_id": "C101",
        "product_id": "P006",   # boAt Earbuds — 1299 × 2
        "quantity": 2,
        "order_status": "CONFIRMED",
        "order_date": _utc(2024, 6, 15, 8, 0),
    },
    # ORD007 — Scenario C: CANCELLED order with REFUNDED payment
    {
        "order_id": "ORD007",
        "customer_id": "C102",
        "product_id": "P007",   # Air Fryer — 6499
        "quantity": 1,
        "order_status": "CANCELLED",
        "order_date": _utc(2024, 6, 18, 13, 20),
    },
    # ORD008 — C103 buys a book
    {
        "order_id": "ORD008",
        "customer_id": "C103",
        "product_id": "P008",   # Python Book — 799 × 3
        "quantity": 3,
        "order_status": "DELIVERED",
        "order_date": _utc(2024, 6, 20, 10, 0),
    },
    # ORD009 — Scenario D: DELIVERED order but delivery is DELAYED
    {
        "order_id": "ORD009",
        "customer_id": "C104",
        "product_id": "P009",   # Logitech Mouse — 9999
        "quantity": 1,
        "order_status": "CONFIRMED",
        "order_date": _utc(2024, 6, 22, 17, 0),
    },
    # ORD010 — Scenario E: PENDING order with FAILED payment
    {
        "order_id": "ORD010",
        "customer_id": "C105",
        "product_id": "P010",   # Smart Bulb — 349 × 4
        "quantity": 4,
        "order_status": "PENDING",
        "order_date": _utc(2024, 6, 25, 9, 15),
    },
]

PAYMENTS = [
    # ORD001 — success via UPI
    {
        "payment_id": "PAY001",
        "order_id": "ORD001",
        "amount": _amount("P001", 1),   # 79999
        "payment_status": "SUCCESS",
        "payment_method": "UPI",
        "transaction_id": "TXN-UPI-20240601-001",
        "payment_date": _utc(2024, 6, 1, 10, 32),
    },
    # ORD002 — success via CARD
    {
        "payment_id": "PAY002",
        "order_id": "ORD002",
        "amount": _amount("P004", 1),   # 29999
        "payment_status": "SUCCESS",
        "payment_method": "CARD",
        "transaction_id": "TXN-CARD-20240605-002",
        "payment_date": _utc(2024, 6, 5, 9, 5),
    },
    # ORD003 — success via NET_BANKING
    {
        "payment_id": "PAY003",
        "order_id": "ORD003",
        "amount": _amount("P003", 1),   # 54999
        "payment_status": "SUCCESS",
        "payment_method": "NET_BANKING",
        "transaction_id": "TXN-NB-20240608-003",
        "payment_date": _utc(2024, 6, 8, 14, 3),
    },
    # ORD004 — success via CARD
    {
        "payment_id": "PAY004",
        "order_id": "ORD004",
        "amount": _amount("P005", 2),   # 17998
        "payment_status": "SUCCESS",
        "payment_method": "CARD",
        "transaction_id": "TXN-CARD-20240610-004",
        "payment_date": _utc(2024, 6, 10, 11, 2),
    },
    # ORD005 — Scenario A: payment SUCCESS but order is still PENDING
    {
        "payment_id": "PAY005",
        "order_id": "ORD005",
        "amount": _amount("P002", 1),   # 69999
        "payment_status": "SUCCESS",
        "payment_method": "UPI",
        "transaction_id": "TXN-UPI-20240612-005",
        "payment_date": _utc(2024, 6, 12, 16, 47),
    },
    # ORD006 — success via UPI
    {
        "payment_id": "PAY006",
        "order_id": "ORD006",
        "amount": _amount("P006", 2),   # 2598
        "payment_status": "SUCCESS",
        "payment_method": "UPI",
        "transaction_id": "TXN-UPI-20240615-006",
        "payment_date": _utc(2024, 6, 15, 8, 3),
    },
    # ORD007 — Scenario C: CANCELLED order → payment REFUNDED
    {
        "payment_id": "PAY007",
        "order_id": "ORD007",
        "amount": _amount("P007", 1),   # 6499
        "payment_status": "REFUNDED",
        "payment_method": "NET_BANKING",
        "transaction_id": "TXN-NB-20240618-007",
        "payment_date": _utc(2024, 6, 18, 13, 22),
    },
    # ORD008 — success via CARD
    {
        "payment_id": "PAY008",
        "order_id": "ORD008",
        "amount": _amount("P008", 3),   # 2397
        "payment_status": "SUCCESS",
        "payment_method": "CARD",
        "transaction_id": "TXN-CARD-20240620-008",
        "payment_date": _utc(2024, 6, 20, 10, 2),
    },
    # ORD009 — success via UPI (order confirmed, delivery delayed)
    {
        "payment_id": "PAY009",
        "order_id": "ORD009",
        "amount": _amount("P009", 1),   # 9999
        "payment_status": "SUCCESS",
        "payment_method": "UPI",
        "transaction_id": "TXN-UPI-20240622-009",
        "payment_date": _utc(2024, 6, 22, 17, 2),
    },
    # ORD010 — Scenario E: FAILED payment
    {
        "payment_id": "PAY010",
        "order_id": "ORD010",
        "amount": _amount("P010", 4),   # 1396
        "payment_status": "FAILED",
        "payment_method": "NET_BANKING",
        "transaction_id": "TXN-NB-20240625-010",
        "payment_date": _utc(2024, 6, 25, 9, 17),
    },
]

DELIVERIES = [
    # ORD001 — SHIPPED
    {
        "delivery_id": "DEL001",
        "order_id": "ORD001",
        "tracking_id": "TRACK-SK-20240601-001",
        "delivery_status": "SHIPPED",
        "expected_date": date(2024, 6, 7),
    },
    # ORD002 — Scenario B: fully DELIVERED
    {
        "delivery_id": "DEL002",
        "order_id": "ORD002",
        "tracking_id": "TRACK-SK-20240605-002",
        "delivery_status": "DELIVERED",
        "expected_date": date(2024, 6, 10),
    },
    # ORD003 — OUT_FOR_DELIVERY
    {
        "delivery_id": "DEL003",
        "order_id": "ORD003",
        "tracking_id": "TRACK-SK-20240608-003",
        "delivery_status": "OUT_FOR_DELIVERY",
        "expected_date": date(2024, 6, 14),
    },
    # ORD004 — DELIVERED
    {
        "delivery_id": "DEL004",
        "order_id": "ORD004",
        "tracking_id": "TRACK-SK-20240610-004",
        "delivery_status": "DELIVERED",
        "expected_date": date(2024, 6, 15),
    },
    # ORD005 — PROCESSING (payment done but order still pending)
    {
        "delivery_id": "DEL005",
        "order_id": "ORD005",
        "tracking_id": "TRACK-SK-20240612-005",
        "delivery_status": "PROCESSING",
        "expected_date": date(2024, 6, 19),
    },
    # ORD006 — SHIPPED
    {
        "delivery_id": "DEL006",
        "order_id": "ORD006",
        "tracking_id": "TRACK-SK-20240615-006",
        "delivery_status": "SHIPPED",
        "expected_date": date(2024, 6, 20),
    },
    # ORD008 — DELIVERED
    {
        "delivery_id": "DEL008",
        "order_id": "ORD008",
        "tracking_id": "TRACK-SK-20240620-008",
        "delivery_status": "DELIVERED",
        "expected_date": date(2024, 6, 24),
    },
    # ORD009 — Scenario D: DELAYED delivery
    {
        "delivery_id": "DEL009",
        "order_id": "ORD009",
        "tracking_id": "TRACK-SK-20240622-009",
        "delivery_status": "DELAYED",
        "expected_date": date(2024, 6, 26),   # already past, still delayed
    },
]
# Note: ORD007 (CANCELLED) and ORD010 (FAILED payment) have no delivery records.


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------

def _seed_customers(db: Session) -> int:
    inserted = 0
    for data in CUSTOMERS:
        exists = db.query(Customer).filter_by(customer_id=data["customer_id"]).first()
        if not exists:
            db.add(Customer(**data))
            inserted += 1
    db.commit()
    return inserted


def _seed_products(db: Session) -> int:
    inserted = 0
    for data in PRODUCTS:
        exists = db.query(Product).filter_by(product_id=data["product_id"]).first()
        if not exists:
            db.add(Product(**data))
            inserted += 1
    db.commit()
    return inserted


def _seed_orders(db: Session) -> int:
    inserted = 0
    for data in ORDERS:
        exists = db.query(Order).filter_by(order_id=data["order_id"]).first()
        if not exists:
            db.add(Order(**data))
            inserted += 1
    db.commit()
    return inserted


def _seed_payments(db: Session) -> int:
    inserted = 0
    for data in PAYMENTS:
        exists = db.query(Payment).filter_by(payment_id=data["payment_id"]).first()
        if not exists:
            db.add(Payment(**data))
            inserted += 1
    db.commit()
    return inserted


def _seed_deliveries(db: Session) -> int:
    inserted = 0
    for data in DELIVERIES:
        exists = db.query(Delivery).filter_by(delivery_id=data["delivery_id"]).first()
        if not exists:
            db.add(Delivery(**data))
            inserted += 1
    db.commit()
    return inserted


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------

def _verify(db: Session) -> None:
    print("\n--- Verification ---")

    # Row counts
    for model, label in [
        (Customer, "customers"),
        (Product,  "products"),
        (Order,    "orders"),
        (Payment,  "payments"),
        (Delivery, "deliveries"),
    ]:
        count = db.query(model).count()
        print(f"  {label:<12}: {count} row(s)")

    # Scenario A — payment SUCCESS while order is PENDING
    a_order   = db.query(Order).filter_by(order_id="ORD005").first()
    a_payment = db.query(Payment).filter_by(order_id="ORD005").first()
    a_ok = a_order and a_payment and a_order.order_status == "PENDING" and a_payment.payment_status == "SUCCESS"
    print(f"\n  Scenario A (PENDING order + SUCCESS payment): {'[PASS]' if a_ok else '[FAIL]'}")

    # Scenario B — DELIVERED order with DELIVERED delivery
    b_order    = db.query(Order).filter_by(order_id="ORD002").first()
    b_delivery = db.query(Delivery).filter_by(order_id="ORD002").first()
    b_ok = b_order and b_delivery and b_order.order_status == "DELIVERED" and b_delivery.delivery_status == "DELIVERED"
    print(f"  Scenario B (DELIVERED order + DELIVERED delivery): {'[PASS]' if b_ok else '[FAIL]'}")

    # Scenario C — CANCELLED order with REFUNDED payment
    c_order   = db.query(Order).filter_by(order_id="ORD007").first()
    c_payment = db.query(Payment).filter_by(order_id="ORD007").first()
    c_ok = c_order and c_payment and c_order.order_status == "CANCELLED" and c_payment.payment_status == "REFUNDED"
    print(f"  Scenario C (CANCELLED order + REFUNDED payment): {'[PASS]' if c_ok else '[FAIL]'}")

    # Scenario D — DELAYED delivery
    d_delivery = db.query(Delivery).filter_by(order_id="ORD009").first()
    d_ok = d_delivery and d_delivery.delivery_status == "DELAYED"
    print(f"  Scenario D (DELAYED delivery): {'[PASS]' if d_ok else '[FAIL]'}")

    # Scenario E — FAILED payment
    e_payment = db.query(Payment).filter_by(order_id="ORD010").first()
    e_ok = e_payment and e_payment.payment_status == "FAILED"
    print(f"  Scenario E (FAILED payment): {'[PASS]' if e_ok else '[FAIL]'}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def seed() -> None:
    db: Session = SessionLocal()
    try:
        print("Seeding ShopKart demo data...\n")

        c = _seed_customers(db)
        print(f"  Customers  inserted: {c}")

        p = _seed_products(db)
        print(f"  Products   inserted: {p}")

        o = _seed_orders(db)
        print(f"  Orders     inserted: {o}")

        pay = _seed_payments(db)
        print(f"  Payments   inserted: {pay}")

        d = _seed_deliveries(db)
        print(f"  Deliveries inserted: {d}")

        _verify(db)

        print("\nSeeding complete.")
    except Exception as exc:
        db.rollback()
        print(f"\nERROR during seeding: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
