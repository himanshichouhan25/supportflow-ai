"""
backend/routers/orders.py — FastAPI Router for Orders and Product Data.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.order import Order
from tools.order_tool import find_orders_by_email

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.get("", response_model=Any)
@router.get("/", response_model=Any)
def list_orders(
    customer_id: str | None = None,
    email: str | None = None,
    db: Session = Depends(get_db),
) -> Any:
    """List customer orders from PostgreSQL database."""
    if email:
        return find_orders_by_email(email, db)

    query = db.query(Order)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)

    orders = query.all()
    results = []
    for ord_obj in orders:
        p_obj = ord_obj.product
        pmt = ord_obj.payment
        deliv = ord_obj.delivery
        unit_price = float(p_obj.price) if p_obj and p_obj.price is not None else 0.0
        total_amount = unit_price * ord_obj.quantity

        results.append({
            "order_id": ord_obj.order_id,
            "customer_id": ord_obj.customer_id,
            "product_id": ord_obj.product_id,
            "product_name": p_obj.name if p_obj else "Unknown Product",
            "quantity": ord_obj.quantity,
            "status": ord_obj.order_status,
            "total_amount": total_amount,
            "order_status": ord_obj.order_status,
            "order_date": ord_obj.order_date.strftime("%d %b %Y") if ord_obj.order_date else "",
            "payment_status": pmt.payment_status if pmt else "N/A",
            "delivery_status": deliv.delivery_status if deliv else "N/A",
            "tracking_number": deliv.tracking_number if deliv else None,
            "courier": deliv.courier if deliv else None,
        })
    return results


@router.get("/{order_id}", response_model=dict[str, Any])
def get_order_details(
    order_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve detailed order record by order_id."""
    ord_obj = db.query(Order).filter_by(order_id=order_id).first()
    if not ord_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )

    p_obj = ord_obj.product
    pmt = ord_obj.payment
    deliv = ord_obj.delivery

    return {
        "order_id": ord_obj.order_id,
        "customer_id": ord_obj.customer_id,
        "product_id": ord_obj.product_id,
        "product_name": p_obj.name if p_obj else "Unknown Product",
        "quantity": ord_obj.quantity,
        "status": ord_obj.order_status,
        "order_status": ord_obj.order_status,
        "order_date": ord_obj.order_date.strftime("%d %b %Y") if ord_obj.order_date else "",
        "payment_status": pmt.payment_status if pmt else "N/A",
        "delivery_status": deliv.delivery_status if deliv else "N/A",
        "tracking_number": deliv.tracking_number if deliv else None,
        "courier": deliv.courier if deliv else None,
    }

