"""
schemas/return_request.py — Pydantic schemas for return requests.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReturnCreate(BaseModel):
    """Payload for creating a product return request."""

    order_id: str = Field(..., min_length=1, description="Unique Order ID (e.g. ORD002)")
    customer_id: Optional[str] = Field(None, description="Customer ID associated with order (optional)")
    reason: Optional[str] = Field("Customer requested product return", description="Reason for the return request")
