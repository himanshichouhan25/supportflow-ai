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


def check_replacement_eligibility(order_id: str, db: Session) -> dict[str, Any]:
    """
    Determine whether an order is eligible for a product replacement.

    Business Rules:
    1. Order must exist in the database.
    2. Customer associated with the order must exist.
    3. Product associated with the order must exist.
    4. Order status must be DELIVERED. (Active or pending or cancelled orders cannot be replaced).

    Returns structured dict with keys:
    - success (bool)
    - eligible (bool)
    - order_id (str)
    - customer_id (str | None)
    - product_id (str | None)
    - order_status (str | None)
    - reason (str)
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to check replacement eligibility."}

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

    product: Product | None = db.query(Product).filter_by(product_id=order.product_id).first()
    if not product:
        return {
            "success": False,
            "eligible": False,
            "order_id": order_id,
            "reason": f"Product record associated with order '{order_id}' was not found.",
        }

    # Status check: Only DELIVERED orders are eligible for replacement
    if order.order_status.upper() != "DELIVERED":
        return {
            "success": True,
            "eligible": False,
            "order_id": order_id,
            "customer_id": order.customer_id,
            "product_id": order.product_id,
            "order_status": order.order_status,
            "reason": f"Order status is '{order.order_status}'. Replacements are only eligible for delivered items.",
        }

    return {
        "success": True,
        "eligible": True,
        "order_id": order_id,
        "customer_id": order.customer_id,
        "product_id": order.product_id,
        "order_status": order.order_status,
        "reason": f"Order '{order_id}' is DELIVERED and eligible for a product replacement.",
    }


def create_replacement_request(
    order_id: str,
    db: Session,
    customer_id: str | None = None,
    product_id: str | None = None,
    reason: str = "Customer requested product replacement",
) -> dict[str, Any]:
    """
    Create a new Replacement request record in PostgreSQL.

    Steps:
    1. Verify Order exists.
    2. Ownership & Product Validation:
       - If customer_id provided, verify customer_id == order.customer_id.
       - If product_id provided, verify product_id == order.product_id.
    3. Check eligibility via check_replacement_eligibility().
    4. Duplicate check: Check if an active replacement (REQUESTED, APPROVED, PROCESSING, SHIPPED, DELIVERED)
       already exists for order_id. (CANCELLED replacements may be resubmitted).
    5. Generate unique replacement_id (e.g. REP0001).
    6. Insert Replacement record with status='REQUESTED'.
    7. Commit transaction and return structured dict.
    """
    if not order_id:
        return {"success": False, "message": "Order ID is required to create a replacement request."}

    try:
        order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
        if not order:
            return {"success": False, "created": False, "message": f"Order '{order_id}' not found."}

        # Ownership validation
        if customer_id and customer_id != order.customer_id:
            return {
                "success": False,
                "created": False,
                "message": f"Customer ID '{customer_id}' does not own order '{order_id}'. Ownership verification failed.",
            }

        # Product validation
        if product_id and product_id != order.product_id:
            return {
                "success": False,
                "created": False,
                "message": f"Product ID '{product_id}' does not match product associated with order '{order_id}'. Product validation failed.",
            }

        target_customer_id = customer_id if customer_id else order.customer_id
        target_product_id = product_id if product_id else order.product_id

        customer: Customer | None = db.query(Customer).filter_by(customer_id=target_customer_id).first()
        if not customer:
            return {
                "success": False,
                "created": False,
                "message": f"Customer account '{target_customer_id}' not found.",
            }

        product: Product | None = db.query(Product).filter_by(product_id=target_product_id).first()
        if not product:
            return {
                "success": False,
                "created": False,
                "message": f"Product record '{target_product_id}' not found.",
            }

        # Eligibility check
        eligibility = check_replacement_eligibility(order_id, db)
        if not eligibility.get("success") or not eligibility.get("eligible"):
            return {
                "success": True,
                "created": False,
                "already_exists": False,
                "eligible": False,
                "order_id": order_id,
                "reason": eligibility.get("reason", "Order is not eligible for replacement."),
                "message": eligibility.get("reason", "Order is not eligible for replacement."),
            }

        # Duplicate Replacement Protection
        # Check if an active replacement already exists for the same order
        existing_replacement = (
            db.query(Replacement)
            .filter(
                Replacement.order_id == order_id,
                Replacement.status.in_(["REQUESTED", "APPROVED", "PROCESSING", "SHIPPED", "DELIVERED"]),
            )
            .first()
        )

        if existing_replacement:
            return {
                "success": True,
                "created": False,
                "already_exists": True,
                "replacement_id": existing_replacement.replacement_id,
                "order_id": order_id,
                "customer_id": existing_replacement.customer_id,
                "product_id": existing_replacement.product_id,
                "status": existing_replacement.status,
                "reason": existing_replacement.reason,
                "created_at": existing_replacement.created_at.isoformat() if existing_replacement.created_at else None,
                "updated_at": existing_replacement.updated_at.isoformat() if existing_replacement.updated_at else None,
                "message": f"A replacement request ('{existing_replacement.replacement_id}') already exists for order '{order_id}' with status '{existing_replacement.status}'.",
            }

        # Generate unique business replacement ID: REP0001, REP0002, etc.
        last_rep = db.query(Replacement).order_by(Replacement.id.desc()).first()
        next_num = (last_rep.id + 1) if last_rep else 1
        replacement_id = f"REP{next_num:04d}"

        now = datetime.now(timezone.utc)

        replacement_record = Replacement(
            replacement_id=replacement_id,
            order_id=order.order_id,
            customer_id=target_customer_id,
            product_id=target_product_id,
            reason=reason if reason else "Customer requested product replacement",
            status="REQUESTED",
            created_at=now,
            updated_at=now,
        )

        db.add(replacement_record)
        db.commit()
        db.refresh(replacement_record)

        return {
            "success": True,
            "created": True,
            "already_exists": False,
            "replacement_id": replacement_record.replacement_id,
            "order_id": order.order_id,
            "customer_id": replacement_record.customer_id,
            "product_id": replacement_record.product_id,
            "status": replacement_record.status,
            "reason": replacement_record.reason,
            "created_at": replacement_record.created_at.isoformat() if replacement_record.created_at else None,
            "updated_at": replacement_record.updated_at.isoformat() if replacement_record.updated_at else None,
            "message": f"Replacement request '{replacement_record.replacement_id}' created successfully for order '{order_id}'. Status: REQUESTED.",
        }

    except Exception as exc:
        db.rollback()
        return {"success": False, "message": f"Database error during replacement request creation: {exc}"}


def verify_replacement(identifier: str, db: Session) -> dict[str, Any]:
    """
    Query PostgreSQL for an existing Replacement record by replacement_id or order_id.
    """
    if not identifier:
        return {"success": False, "message": "Replacement ID or Order ID is required for verification."}

    rep: Replacement | None = (
        db.query(Replacement)
        .filter((Replacement.replacement_id == identifier) | (Replacement.order_id == identifier))
        .order_by(Replacement.id.desc())
        .first()
    )

    if not rep:
        return {
            "success": False,
            "message": f"No replacement record found for identifier '{identifier}'.",
        }

    return {
        "success": True,
        "replacement_id": rep.replacement_id,
        "order_id": rep.order_id,
        "customer_id": rep.customer_id,
        "product_id": rep.product_id,
        "reason": rep.reason,
        "status": rep.status,
        "created_at": rep.created_at.isoformat() if rep.created_at else None,
        "updated_at": rep.updated_at.isoformat() if rep.updated_at else None,
    }
