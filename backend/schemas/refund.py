"""
schemas/refund.py — Pydantic schemas for refund requests.
"""

from typing import Optional
from pydantic import BaseModel, Field


class RefundCreate(BaseModel):
    """Payload for processing a simulated refund."""

    order_id: str = Field(..., min_length=1, description="Unique Order ID (e.g. ORD003)")
    reason: Optional[str] = Field("Customer requested refund", description="Reason for the refund request")
