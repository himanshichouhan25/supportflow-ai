"""
tools/replacement_tool.py — Deterministic product-replacement tools.

Functions
---------
check_replacement_eligibility(order_id, db)                              → determine replacement eligibility
create_replacement_request(order_id, db, customer_id, product_id, reason) → create Replacement record (status=REQUESTED)
verify_replacement(identifier, db)                                        → query actual Replacement record from PostgreSQL

No LLM calls; purely deterministic business logic against PostgreSQL.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.order import Order
from backend.models.product import Product
from backend.models.replacement import Replacement


from backend.services.replacement_service import (
    check_replacement_eligibility,
    create_replacement_request,
    verify_replacement,
)

