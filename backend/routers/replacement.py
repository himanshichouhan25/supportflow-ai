"""
routers/replacement.py — FastAPI router for Product Replacement endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.replacement import ReplacementCreate
from tools.replacement_tool import (
    check_replacement_eligibility,
    create_replacement_request,
    verify_replacement,
)

router = APIRouter(prefix="/api/replacements", tags=["Replacements"])


@router.get("/eligibility/{order_id}")
def get_replacement_eligibility(order_id: str, db: Session = Depends(get_db)):
    """
    Check whether an order is eligible for a product replacement.
    """
    result = check_replacement_eligibility(order_id, db)
    if not result.get("success") and "not found" in result.get("message", "").lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message"),
        )
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_replacement(payload: ReplacementCreate, db: Session = Depends(get_db)):
    """
    Create a new product replacement request.
    """
    result = create_replacement_request(
        order_id=payload.order_id,
        db=db,
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        reason=payload.reason or "Customer requested product replacement",
    )
    if not result.get("success"):
        if "not found" in result.get("message", "").lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("message"),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Replacement creation failed"),
        )
    return result


@router.get("/{identifier}")
def get_replacement_status(identifier: str, db: Session = Depends(get_db)):
    """
    Verify and return the actual replacement record state from PostgreSQL.
    """
    result = verify_replacement(identifier, db)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("message", f"No replacement record found for '{identifier}'"),
        )
    return result
