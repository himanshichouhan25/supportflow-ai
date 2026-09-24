"""
services/support_ticket_service.py

Business logic for creating and retrieving customer support tickets.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.support_ticket import SupportTicket


def _generate_ticket_id(db: Session) -> str:
    """
    Generate the next human-readable ticket ID.

    Example:
        TKT-1001
        TKT-1002
        TKT-1003
    """

    last_ticket_number = db.query(
        func.max(
            func.cast(
                func.replace(SupportTicket.ticket_id, "TKT-", ""),
                __import__("sqlalchemy").Integer,
            )
        )
    ).scalar()

    if last_ticket_number is None:
        next_number = 1001
    else:
        next_number = last_ticket_number + 1

    return f"TKT-{next_number}"


def create_support_ticket(
    db: Session,
    issue: str,
    customer_id: str | None = None,
    order_id: str | None = None,
) -> dict:
    """
    Create a new customer support ticket.

    Args:
        db: SQLAlchemy database session.
        issue: Customer's unresolved issue.
        customer_id: Optional customer ID.
        order_id: Optional order ID related to the issue.

    Returns:
        Dictionary containing the created ticket details.
    """

    cleaned_issue = issue.strip()

    if not cleaned_issue:
        raise ValueError("Support ticket issue cannot be empty.")

    ticket_id = _generate_ticket_id(db)

    ticket = SupportTicket(
        ticket_id=ticket_id,
        customer_id=customer_id,
        order_id=order_id,
        issue=cleaned_issue,
        status="OPEN",
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {
        "ticket_id": ticket.ticket_id,
        "customer_id": ticket.customer_id,
        "order_id": ticket.order_id,
        "issue": ticket.issue,
        "status": ticket.status,
        "created_at": ticket.created_at,
    }


def get_support_ticket(
    db: Session,
    ticket_id: str,
) -> dict | None:
    """
    Retrieve a support ticket using its human-readable ticket ID.
    """

    ticket = (
        db.query(SupportTicket)
        .filter(SupportTicket.ticket_id == ticket_id.strip().upper())
        .first()
    )

    if ticket is None:
        return None

    return {
        "ticket_id": ticket.ticket_id,
        "customer_id": ticket.customer_id,
        "order_id": ticket.order_id,
        "issue": ticket.issue,
        "status": ticket.status,
        "created_at": ticket.created_at,
    }