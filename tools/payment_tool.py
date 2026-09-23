"""
tools/payment_tool.py — Deterministic payment and refund-eligibility tools.

Functions
---------
check_payment(order_id)             → look up payment record for an order
check_refund_eligibility(order_id)  → determine refund eligibility via rules

No LLM calls; purely deterministic business logic.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.payment import Payment


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


def check_refund_eligibility(order_id: str, db: Session) -> dict[str, Any]:
    """
    Determine whether a refund is eligible for the given order.

    Deterministic rules
    -------------------
    CANCELLED order + SUCCESS payment   → eligible for refund
    CANCELLED order + REFUNDED payment  → already refunded
    CANCELLED order + FAILED payment    → no refund required (nothing charged)
    CANCELLED order + PENDING payment   → contact support (edge case)
    DELIVERED order                     → not eligible (policy: no refund after delivery)
    CONFIRMED / PENDING order           → not eligible (order still active)
    Missing payment                     → not eligible
    Missing order                       → not found

    No actual refund is processed here; this function only assesses eligibility.
    """
    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
    if not order:
        return {"success": False, "message": f"Order '{order_id}' not found."}

    payment: Payment | None = db.query(Payment).filter_by(order_id=order_id).first()

    order_status = order.order_status
    payment_status = payment.payment_status if payment else None
    amount = str(payment.amount) if payment else None

    # --- Rule evaluation ---
    if order_status == "CANCELLED":
        if payment_status == "SUCCESS":
            return {
                "success": True,
                "eligible": True,
                "order_id": order_id,
                "order_status": order_status,
                "payment_status": payment_status,
                "amount": amount,
                "reason": "Order was cancelled and payment was successful. Refund is eligible.",
            }
        if payment_status == "REFUNDED":
            return {
                "success": True,
                "eligible": False,
                "order_id": order_id,
                "order_status": order_status,
                "payment_status": payment_status,
                "amount": amount,
                "reason": "Refund has already been processed for this order.",
            }
        if payment_status == "FAILED":
            return {
                "success": True,
                "eligible": False,
                "order_id": order_id,
                "order_status": order_status,
                "payment_status": payment_status,
                "amount": amount,
                "reason": "Payment failed; no amount was charged, so no refund is required.",
            }
        if payment_status == "PENDING":
            return {
                "success": True,
                "eligible": False,
                "order_id": order_id,
                "order_status": order_status,
                "payment_status": payment_status,
                "amount": amount,
                "reason": "Payment is still pending. Please contact support.",
            }
        # No payment record at all
        return {
            "success": True,
            "eligible": False,
            "order_id": order_id,
            "order_status": order_status,
            "payment_status": None,
            "amount": None,
            "reason": "Order is cancelled but no payment record exists.",
        }

    if order_status == "DELIVERED":
        return {
            "success": True,
            "eligible": False,
            "order_id": order_id,
            "order_status": order_status,
            "payment_status": payment_status,
            "amount": amount,
            "reason": "Refunds are not available for delivered orders under the current policy.",
        }

    # CONFIRMED, PENDING, or any other active status
    return {
        "success": True,
        "eligible": False,
        "order_id": order_id,
        "order_status": order_status,
        "payment_status": payment_status,
        "amount": amount,
        "reason": f"Order is currently {order_status}. Refund is only applicable to cancelled orders.",
    }
