"""
frontend/api/support_api.py — Frontend API Client methods for Support Resolution.
"""

from typing import Any
from frontend.api.client import api_client


def resolve_support(
    user_message: str,
    session_id: str = "default_session",
    customer_id: str | None = None,
    order_id: str | None = None,
    product_id: str | None = None,
) -> dict[str, Any]:
    """
    Send user support query to FastAPI backend support resolution endpoint.
    """
    payload = {
        "message": user_message,
        "session_id": session_id,
        "customer_id": customer_id,
        "order_id": order_id,
        "product_id": product_id,
    }
    return api_client.post("/api/support/resolve", json_data=payload)
