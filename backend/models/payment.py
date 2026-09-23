"""
models/payment.py — Payment table definition.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Payment(Base):
    """Represents a payment record associated with an order."""

    __tablename__ = "payments"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # FK → orders.order_id
    order_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("orders.order_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Numeric(12, 2) → up to 9,999,999,999.99
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    payment_method: Mapped[str] = mapped_column(String(100), nullable=True)
    transaction_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True, index=True)
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ------------------------------------------------------------------ relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} payment_id={self.payment_id!r} status={self.payment_status!r}>"
