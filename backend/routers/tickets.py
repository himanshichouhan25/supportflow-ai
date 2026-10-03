"""
backend/routers/tickets.py — FastAPI Router for Support Tickets.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.support_ticket import SupportTicket

router = APIRouter(prefix="/api/tickets", tags=["Support Tickets"])


@router.get("", response_model=list[dict[str, Any]])
@router.get("/", response_model=list[dict[str, Any]])
def list_support_tickets(
    customer_id: str | None = None,
    order_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List support tickets from PostgreSQL database."""
    query = db.query(SupportTicket)
    if customer_id:
        query = query.filter(SupportTicket.customer_id == customer_id)
    if order_id:
        query = query.filter(SupportTicket.order_id == order_id)

    tickets = query.order_by(SupportTicket.created_at.desc()).all()
    results = []
    for t in tickets:
        results.append({
            "ticket_id": t.ticket_id,
            "customer_id": t.customer_id or "N/A",
            "order_id": t.order_id or "N/A",
            "issue": t.issue,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return results


@router.get("/{ticket_id}", response_model=dict[str, Any])
def get_support_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get support ticket details by ticket_id."""
    t = db.query(SupportTicket).filter_by(ticket_id=ticket_id).first()
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket '{ticket_id}' not found.",
        )
    return {
        "ticket_id": t.ticket_id,
        "customer_id": t.customer_id or "N/A",
        "order_id": t.order_id or "N/A",
        "issue": t.issue,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
