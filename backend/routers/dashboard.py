"""
backend/routers/dashboard.py — FastAPI Router for Real Dashboard Metrics.
"""

from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.order import Order
from backend.models.refund import Refund
from backend.models.return_request import Return
from backend.models.replacement import Replacement
from backend.models.support_ticket import SupportTicket

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=dict[str, Any])
def get_dashboard_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieve real aggregate metrics from PostgreSQL database."""
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    open_tickets = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "OPEN").scalar() or 0
    total_tickets = db.query(func.count(SupportTicket.id)).scalar() or 0
    
    refunds_count = db.query(func.count(Refund.id)).scalar() or 0
    returns_count = db.query(func.count(Return.id)).scalar() or 0
    replacements_count = db.query(func.count(Replacement.id)).scalar() or 0

    return {
        "total_orders": total_orders,
        "open_tickets": open_tickets,
        "total_tickets": total_tickets,
        "refunds_count": refunds_count,
        "returns_count": returns_count,
        "replacements_count": replacements_count,
    }
