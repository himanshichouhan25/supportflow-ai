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


def process_refund(order_id: str, db: Session, reason: str = "Customer requested refund") -> dict[str, Any]:
    """
    Process a simulated refund for an order.

    Steps:
    1. Check order/payment existence.
    2. Check eligibility (must be eligible).
    3. Duplicate safety: check if completed Refund already exists.
    4. Create Refund record (status=COMPLETED).
    5. Update Payment.payment_status = 'REFUNDED'.
    6. Commit safely and return structured result.
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to process a refund."}

    try:
        # Check eligibility first
        eligibility = check_refund_eligibility(order_id, db)
        if not eligibility.get("success"):
            return eligibility

        # If payment is already REFUNDED or not eligible
        if not eligibility.get("eligible"):
            # Check if a completed refund record already exists for duplicate safety reporting
            existing_refund = db.query(Refund).filter_by(order_id=order_id, status="COMPLETED").first()
            if existing_refund:
                return {
                    "success": True,
                    "processed": False,
                    "already_refunded": True,
                    "refund_id": existing_refund.refund_id,
                    "order_id": order_id,
                    "payment_id": existing_refund.payment_id,
                    "amount": str(existing_refund.amount),
                    "status": existing_refund.status,
                    "reason": existing_refund.reason,
                    "created_at": existing_refund.created_at.isoformat() if existing_refund.created_at else None,
                    "processed_at": existing_refund.processed_at.isoformat() if existing_refund.processed_at else None,
                    "message": f"Refund for order '{order_id}' has already been processed.",
                }
            return {
                "success": False,
                "processed": False,
                "order_id": order_id,
                "message": eligibility.get("reason", "Order is not eligible for a refund."),
            }

        order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
        payment: Payment | None = db.query(Payment).filter_by(order_id=order_id).first()

        if not order or not payment:
            return {"success": False, "message": f"Order or payment record for '{order_id}' not found."}

        # Check duplicate refund record in DB before creating
        existing = db.query(Refund).filter_by(order_id=order_id, status="COMPLETED").first()
        if existing:
            return {
                "success": True,
                "processed": False,
                "already_refunded": True,
                "refund_id": existing.refund_id,
                "order_id": order_id,
                "payment_id": existing.payment_id,
                "amount": str(existing.amount),
                "status": existing.status,
                "reason": existing.reason,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
                "processed_at": existing.processed_at.isoformat() if existing.processed_at else None,
                "message": f"Refund for order '{order_id}' has already been processed.",
            }

        # Generate unique refund ID (e.g. RFD1001 or RFD_<order_id>)
        last_refund = db.query(Refund).order_by(Refund.id.desc()).first()
        next_num = (last_refund.id + 1) if last_refund else 1
        refund_id = f"RFD{next_num:04d}"

        now = datetime.now(timezone.utc)

        # Create Refund record
        refund_record = Refund(
            refund_id=refund_id,
            payment_id=payment.payment_id,
            order_id=order.order_id,
            amount=payment.amount,
            status="COMPLETED",
            reason=reason,
            created_at=now,
            processed_at=now,
        )

        # Update Payment status
        payment.payment_status = "REFUNDED"

        db.add(refund_record)
        db.commit()
        db.refresh(refund_record)
        db.refresh(payment)

        return {
            "success": True,
            "processed": True,
            "already_refunded": False,
            "refund_id": refund_record.refund_id,
            "order_id": order.order_id,
            "payment_id": payment.payment_id,
            "amount": str(refund_record.amount),
            "status": refund_record.status,
            "reason": refund_record.reason,
            "created_at": refund_record.created_at.isoformat() if refund_record.created_at else None,
            "processed_at": refund_record.processed_at.isoformat() if refund_record.processed_at else None,
            "message": f"Refund of INR {refund_record.amount} for order '{order_id}' processed successfully.",
        }

    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"Database error during refund processing: {exc}"}


def verify_refund(order_id: str, db: Session) -> dict[str, Any]:
    """
    Query the Refund table and return the actual current refund state from PostgreSQL.
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to verify refund."}

    refund: Refund | None = db.query(Refund).filter_by(order_id=order_id).order_by(Refund.id.desc()).first()

    if not refund:
        return {
            "success": False,
            "order_id": order_id,
            "message": f"No refund record found for order '{order_id}'.",
        }

    return {
        "success": True,
        "refund_id": refund.refund_id,
        "order_id": refund.order_id,
        "payment_id": refund.payment_id,
        "amount": str(refund.amount),
        "status": refund.status,
        "reason": refund.reason,
        "created_at": refund.created_at.isoformat() if refund.created_at else None,
        "processed_at": refund.processed_at.isoformat() if refund.processed_at else None,
    }

