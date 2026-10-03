"""
frontend/api/data_api.py — Frontend API Client methods for Orders, Products, Tickets, Dashboard.
"""

from typing import Any
from frontend.api.client import api_client


def fetch_products(category: str | None = None) -> list[dict[str, Any]]:
    """Fetch product catalog list from FastAPI backend."""
    params = {"category": category} if category else None
    res = api_client.get("/api/products", params=params)
    return res if isinstance(res, list) else []


def fetch_orders(customer_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch orders list from FastAPI backend."""
    params = {"customer_id": customer_id} if customer_id else None
    res = api_client.get("/api/orders", params=params)
    return res if isinstance(res, list) else []


def fetch_tickets(customer_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch support tickets list from FastAPI backend."""
    params = {"customer_id": customer_id} if customer_id else None
    res = api_client.get("/api/tickets", params=params)
    return res if isinstance(res, list) else []


def fetch_dashboard_metrics() -> dict[str, Any]:
    """Fetch aggregate dashboard metrics from FastAPI backend."""
    res = api_client.get("/api/dashboard/metrics")
    return res if isinstance(res, dict) and "error" not in res else {
        "total_orders": 0,
        "open_tickets": 0,
        "total_tickets": 0,
        "refunds_count": 0,
        "returns_count": 0,
        "replacements_count": 0,
    }
