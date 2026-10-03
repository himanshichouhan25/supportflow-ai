"""
models/refund.py — Refund table definition.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Refund(Base):
    """Represents a refund record associated with a payment and an order."""

    __tablename__ = "refunds"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    refund_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # FK → payments.payment_id
    payment_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("payments.payment_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # FK → orders.order_id
    order_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("orders.order_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Status: PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    reason: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ------------------------------------------------------------------ relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")
    order: Mapped["Order"] = relationship("Order", back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund id={self.id} refund_id={self.refund_id!r} status={self.status!r}>"
