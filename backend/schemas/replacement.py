"""
schemas/replacement.py — Pydantic schemas for replacement requests.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReplacementCreate(BaseModel):
    """Payload for creating a product replacement request."""

    order_id: str = Field(..., min_length=1, description="Unique Order ID (e.g. ORD002)")
    customer_id: Optional[str] = Field(None, description="Customer ID associated with order (optional)")
    product_id: Optional[str] = Field(None, description="Product ID associated with order (optional)")
    reason: Optional[str] = Field("Customer requested product replacement", description="Reason for the replacement request")
