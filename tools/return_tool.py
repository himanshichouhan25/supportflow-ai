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


def check_return_eligibility(order_id: str, db: Session) -> dict[str, Any]:
    """
    Determine whether an order is eligible for a product return.

    Business Rules:
    1. Order must exist in the database.
    2. Customer associated with the order must exist.
    3. Order status must be DELIVERED. (Active or pending or cancelled orders cannot be returned).

    Returns structured dict with keys:
    - success (bool)
    - eligible (bool)
    - order_id (str)
    - customer_id (str | None)
    - order_status (str | None)
    - reason (str)
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to check return eligibility."}

    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
    if not order:
        return {
            "success": False,
            "eligible": False,
            "order_id": order_id,
            "reason": f"Order '{order_id}' was not found in our system.",
        }

    customer: Customer | None = db.query(Customer).filter_by(customer_id=order.customer_id).first()
    if not customer:
        return {
            "success": False,
            "eligible": False,
            "order_id": order_id,
            "reason": f"Customer account associated with order '{order_id}' was not found.",
        }

    # Status check: Only DELIVERED orders are eligible for return
    if order.order_status.upper() != "DELIVERED":
        return {
            "success": True,
            "eligible": False,
            "order_id": order_id,
            "customer_id": order.customer_id,
            "order_status": order.order_status,
            "reason": f"Order status is '{order.order_status}'. Product returns are only eligible for delivered items.",
        }

    return {
        "success": True,
        "eligible": True,
        "order_id": order_id,
        "customer_id": order.customer_id,
        "order_status": order.order_status,
        "reason": f"Order '{order_id}' is DELIVERED and eligible for a product return.",
    }


def create_return_request(
    order_id: str,
    db: Session,
    customer_id: str | None = None,
    reason: str = "Customer requested product return",
) -> dict[str, Any]:
    """
    Create a new Return request record in PostgreSQL.

    Steps:
    1. Verify Order exists.
    2. Verify Customer exists.
    3. Ownership check: If customer_id provided, verify customer_id == order.customer_id.
    4. Check eligibility via check_return_eligibility().
    5. Duplicate check: Check if an active/completed Return record already exists for order_id.
    6. Generate unique return_id (e.g. RET0001).
    7. Insert Return record with status='REQUESTED'.
    8. Commit transaction and return structured dict.
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to create a return request."}

    try:
        order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
        if not order:
            return {"success": False, "created": False, "message": f"Order '{order_id}' not found."}

        # Ownership Check (Step 9)
        if customer_id and customer_id != order.customer_id:
            return {
                "success": False,
                "created": False,
                "message": f"Customer ID '{customer_id}' does not own order '{order_id}'. Ownership verification failed.",
            }

        target_customer_id = customer_id if customer_id else order.customer_id

        customer: Customer | None = db.query(Customer).filter_by(customer_id=target_customer_id).first()
        if not customer:
            return {
                "success": False,
                "created": False,
                "message": f"Customer account '{target_customer_id}' not found.",
            }

        # Eligibility check
        eligibility = check_return_eligibility(order_id, db)
        if not eligibility.get("success") or not eligibility.get("eligible"):
            return {
                "success": True,
                "created": False,
                "already_exists": False,
                "eligible": False,
                "order_id": order_id,
                "reason": eligibility.get("reason", "Order is not eligible for return."),
                "message": eligibility.get("reason", "Order is not eligible for return."),
            }

        # Duplicate Return Protection (Step 4)
        existing_return = (
            db.query(Return)
            .filter(
                Return.order_id == order_id,
                Return.status.in_(["REQUESTED", "APPROVED", "PICKUP_SCHEDULED", "RECEIVED", "COMPLETED"]),
            )
            .first()
        )

        if existing_return:
            return {
                "success": True,
                "created": False,
                "already_exists": True,
                "return_id": existing_return.return_id,
                "order_id": order_id,
                "customer_id": existing_return.customer_id,
                "status": existing_return.status,
                "reason": existing_return.reason,
                "created_at": existing_return.created_at.isoformat() if existing_return.created_at else None,
                "updated_at": existing_return.updated_at.isoformat() if existing_return.updated_at else None,
                "message": f"A return request ('{existing_return.return_id}') already exists for order '{order_id}' with status '{existing_return.status}'.",
            }

        # Generate unique business return ID: RET0001, RET0002, etc.
        last_return = db.query(Return).order_by(Return.id.desc()).first()
        next_num = (last_return.id + 1) if last_return else 1
        return_id = f"RET{next_num:04d}"

        now = datetime.now(timezone.utc)

        return_record = Return(
            return_id=return_id,
            order_id=order.order_id,
            customer_id=target_customer_id,
            reason=reason if reason else "Customer requested product return",
            status="REQUESTED",
            created_at=now,
            updated_at=now,
        )

        db.add(return_record)
        db.commit()
        db.refresh(return_record)

        return {
            "success": True,
            "created": True,
            "already_exists": False,
            "return_id": return_record.return_id,
            "order_id": order.order_id,
            "customer_id": return_record.customer_id,
            "status": return_record.status,
            "reason": return_record.reason,
            "created_at": return_record.created_at.isoformat() if return_record.created_at else None,
            "updated_at": return_record.updated_at.isoformat() if return_record.updated_at else None,
            "message": f"Return request '{return_record.return_id}' created successfully for order '{order_id}'. Status: REQUESTED.",
        }

    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"Database error during return request creation: {exc}"}


def verify_return(identifier: str, db: Session) -> dict[str, Any]:
    """
    Query PostgreSQL for an existing Return record by return_id or order_id.
    """
    if not identifier:
        return {"success": False, "message": "Return ID or Order ID is required for verification."}

    ret: Return | None = (
        db.query(Return)
        .filter((Return.return_id == identifier) | (Return.order_id == identifier))
        .order_by(Return.id.desc())
        .first()
    )

    if not ret:
        return {
            "success": False,
            "message": f"No return record found for identifier '{identifier}'.",
        }

    return {
        "success": True,
        "return_id": ret.return_id,
        "order_id": ret.order_id,
        "customer_id": ret.customer_id,
        "reason": ret.reason,
        "status": ret.status,
        "created_at": ret.created_at.isoformat() if ret.created_at else None,
        "updated_at": ret.updated_at.isoformat() if ret.updated_at else None,
    }
