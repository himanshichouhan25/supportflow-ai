"""
tools/order_tool.py — Deterministic order-management tools.

Functions
---------
check_order(order_id)   → look up order details
cancel_order(order_id)  → cancel a cancellable order

All functions accept a SQLAlchemy Session as the last argument so they
are fully testable without relying on FastAPI's dependency injection.
No LLM calls; purely deterministic database logic.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.models.product import Product


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _order_to_dict(order: Order, product: Product | None) -> dict[str, Any]:
    """Serialize an Order (+ its product price) to a plain dict."""
    unit_price = product.price if product else Decimal("0")
    total_amount = unit_price * order.quantity

    return {
        "success": True,
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "product_id": order.product_id,
        "quantity": order.quantity,
        "total_amount": str(total_amount),
        "status": order.order_status,
        "order_date": order.order_date.isoformat() if order.order_date else None,
    }


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def check_order(order_id: str, db: Session) -> dict[str, Any]:
    """
    Retrieve order details by order_id.

    Returns a dict with order information on success, or
    {'success': False, 'message': '...'} when not found.
    """
    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()

    if not order:
        return {"success": False, "message": f"Order '{order_id}' not found."}

    product: Product | None = db.query(Product).filter_by(product_id=order.product_id).first()
    return _order_to_dict(order, product)


def cancel_order(order_id: str, db: Session) -> dict[str, Any]:
    """
    Cancel an order if it is eligible.

    Rules
    -----
    - Not found            → success=False, message explaining
    - Already CANCELLED    → success=False, already cancelled message
    - DELIVERED            → success=False, cannot cancel delivered orders
    - All other statuses   → update to CANCELLED, commit, return updated status

    Note: payment refund eligibility is handled separately in payment_tool.py.
    """
    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()

    if not order:
        return {"success": False, "message": f"Order '{order_id}' not found."}

    if order.order_status == "CANCELLED":
        return {
            "success": False,
            "order_id": order_id,
            "message": "Order is already cancelled.",
            "status": "CANCELLED",
        }

    if order.order_status == "DELIVERED":
        return {
            "success": False,
            "order_id": order_id,
            "message": "Delivered orders cannot be cancelled.",
            "status": "DELIVERED",
        }

    # Eligible for cancellation
    order.order_status = "CANCELLED"
    db.commit()
    db.refresh(order)

    return {
        "success": True,
        "order_id": order_id,
        "message": "Order has been successfully cancelled.",
        "status": order.order_status,
    }
