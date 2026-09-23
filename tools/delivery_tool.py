"""
tools/delivery_tool.py — Deterministic delivery tracking tool.

Functions
---------
check_delivery(order_id)  → retrieve delivery record for an order

No LLM calls; purely deterministic database logic.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.models.delivery import Delivery
from backend.models.order import Order


def check_delivery(order_id: str, db: Session) -> dict[str, Any]:
    """
    Retrieve delivery/shipping information for the given order_id.

    Returns structured delivery details on success.
    Returns {'success': False, 'message': '...'} when the order or
    delivery record does not exist.

    Note: 'carrier' is not stored in the current schema; a placeholder
    value is returned so the agent response remains consistent.
    """
    order: Order | None = db.query(Order).filter_by(order_id=order_id).first()
    if not order:
        return {"success": False, "message": f"Order '{order_id}' not found."}

    delivery: Delivery | None = db.query(Delivery).filter_by(order_id=order_id).first()
    if not delivery:
        return {
            "success": False,
            "order_id": order_id,
            "message": (
                "No delivery record found for this order. "
                "This may be because the order was cancelled or payment failed."
            ),
        }

    return {
        "success": True,
        "order_id": order_id,
        "delivery_id": delivery.delivery_id,
        "tracking_id": delivery.tracking_id,
        "carrier": "ShopKart Logistics",   # fixed for demo; no carrier column in schema
        "status": delivery.delivery_status,
        "expected_date": delivery.expected_date.isoformat() if delivery.expected_date else None,
    }
