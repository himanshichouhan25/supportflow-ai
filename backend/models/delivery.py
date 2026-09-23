"""
models/delivery.py — Delivery table definition.
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Delivery(Base):
    """Represents delivery/shipping information for an order."""

    __tablename__ = "deliveries"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # FK → orders.order_id
    order_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("orders.order_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    tracking_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=True, index=True)
    delivery_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    # Date only (no time component needed for expected delivery date)
    expected_date: Mapped[date] = mapped_column(Date, nullable=True)

    # ------------------------------------------------------------------ relationships
    order: Mapped["Order"] = relationship("Order", back_populates="delivery")

    def __repr__(self) -> str:
        return f"<Delivery id={self.id} delivery_id={self.delivery_id!r} status={self.delivery_status!r}>"
