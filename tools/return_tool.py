"""
tools/return_tool.py — Deterministic product-return tools.

Functions
---------
check_return_eligibility(order_id, db)                      → determine return eligibility
create_return_request(order_id, db, customer_id, reason)    → create Return record (status=REQUESTED)
verify_return(identifier, db)                               → query actual Return record from PostgreSQL

No LLM calls; purely deterministic business logic against PostgreSQL.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.order import Order
from backend.models.return_request import Return


from backend.services.return_service import (
    check_return_eligibility,
    create_return_request,
    verify_return,
)

