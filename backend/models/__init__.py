"""
models/__init__.py

Imports all ORM models so that:
  1. SQLAlchemy's Base.metadata is aware of every table.
  2. A single `from backend.models import *` is all you need elsewhere.

Import ORDER matters: Customer and Product have no FK dependencies,
Order depends on both, Payment and Delivery depend on Order.
SupportTicket is independent and can be imported after the existing models.
"""

from backend.models.customer import Customer
from backend.models.product import Product
from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.delivery import Delivery
from backend.models.support_ticket import SupportTicket

__all__ = [
    "Customer",
    "Product",
    "Order",
    "Payment",
    "Delivery",
    "SupportTicket",
]