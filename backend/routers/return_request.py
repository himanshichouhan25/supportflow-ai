"""
routers/return_request.py — FastAPI router for Product Return endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.return_request import ReturnCreate
from backend.services.return_service import (
    check_return_eligibility,
    create_return_request,
    verify_return,
)


router = APIRouter(prefix="/api/returns", tags=["Returns"])


@router.get("/eligibility/{order_id}")
def get_return_eligibility(order_id: str, db: Session = Depends(get_db)):
    """
    Check whether an order is eligible for a product return.
    """
    result = check_return_eligibility(order_id, db)
    if not result.get("success") and "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message"),
        )
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_return(payload: ReturnCreate, db: Session = Depends(get_db)):
    """
    Create a new product return request.
    """
    result = create_return_request(
        order_id=payload.order_id,
        db=db,
        customer_id=payload.customer_id,
        reason=payload.reason or "Customer requested product return",
    )
    if not result.get("success"):
        if "not found" in result.get("message", "").lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("message"),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Return creation failed"),
        )
    return result


@router.get("/{identifier}")
def get_return_status(identifier: str, db: Session = Depends(get_db)):
    """
    Verify and return the actual return record state from PostgreSQL.
    """
    result = verify_return(identifier, db)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", f"No return record found for '{identifier}'"),
        )
    return result
