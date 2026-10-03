"""
routers/refund.py — FastAPI router for Refund resolution endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.refund import RefundCreate
from tools.payment_tool import (
    check_refund_eligibility,
    process_refund,
    verify_refund,
)

router = APIRouter(prefix="/api/refunds", tags=["Refunds"])


@router.get("/eligibility/{order_id}")
def get_refund_eligibility(order_id: str, db: Session = Depends(get_db)):
    """
    Check whether an order is eligible for a refund.
    """
    result = check_refund_eligibility(order_id, db)
    if not result.get("success") and "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message"),
        )
    return result


@router.post("", status_code=status.HTTP_200_OK)
def create_refund(payload: RefundCreate, db: Session = Depends(get_db)):
    """
    Process a simulated refund for an order.
    """
    result = process_refund(
        order_id=payload.order_id,
        db=db,
        reason=payload.reason or "Customer requested refund",
    )
    if not result.get("success"):
        if "not found" in result.get("message", "").lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("message"),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Refund processing failed"),
        )
    return result


@router.get("/{identifier}")
def get_refund_status(identifier: str, db: Session = Depends(get_db)):
    """
    Verify and return the actual refund record state from PostgreSQL.
    """
    result = verify_refund(identifier, db)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", f"No refund record found for '{identifier}'"),
        )
    return result
