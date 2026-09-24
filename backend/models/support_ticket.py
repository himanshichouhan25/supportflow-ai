"""
models/support_ticket.py — Support ticket table definition.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SupportTicket(Base):
    """
    Stores customer support escalation tickets.

    A ticket can optionally be linked to a customer and/or order.
    """

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    ticket_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    order_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    issue: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<SupportTicket "
            f"ticket_id={self.ticket_id!r} "
            f"status={self.status!r}>"
        )