"""
tools/payment_tool.py — Deterministic payment and refund-eligibility tools.

Functions
---------
check_payment(order_id)             → look up payment record for an order
check_refund_eligibility(order_id)  → determine refund eligibility via rules

No LLM calls; purely deterministic business logic.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.refund import Refund


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def check_payment(order_id: str, db: Session) -> dict[str, Any]:
    """
    Retrieve payment information associated with the given order_id.

    Returns a dict with payment details on success, or
    {'success': False, 'message': '...'} when not found.
    """
    # Verify the order exists first
    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
    if not order:
        return {"success": False, "message": f"Order '{order_id}' not found."}

    payment: Payment | None = db.query(Payment).filter_by(order_id=order_id).first()
    if not payment:
        return {
            "success": False,
            "order_id": order_id,
            "message": "No payment record found for this order.",
        }

    return {
        "success": True,
        "order_id": order_id,
        "payment_id": payment.payment_id,
        "transaction_id": payment.transaction_id,
        "amount": str(payment.amount),
        "payment_method": payment.payment_method,
        "status": payment.payment_status,
        "paid_at": payment.payment_date.isoformat() if payment.payment_date else None,
    }


from backend.services.refund_service import (
    check_refund_eligibility,
    process_refund,
    verify_refund,
)


