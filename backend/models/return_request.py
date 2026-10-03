"""
models/return_request.py — Return table definition.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Return(Base):
    """Represents a product return request associated with an order and customer."""

    __tablename__ = "returns"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    return_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # FK → orders.order_id
    order_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("orders.order_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # FK → customers.customer_id
    customer_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=True)
    # Status: REQUESTED, APPROVED, REJECTED, PICKUP_SCHEDULED, RECEIVED, COMPLETED, CANCELLED
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="REQUESTED")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ------------------------------------------------------------------ relationships
    order: Mapped["Order"] = relationship("Order", back_populates="returns")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="returns")

    def __repr__(self) -> str:
        return f"<Return id={self.id} return_id={self.return_id!r} status={self.status!r}>"
