"""
models/replacement.py — Replacement table definition.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Replacement(Base):
    """Represents an order replacement request."""

    __tablename__ = "replacements"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    replacement_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

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

    # FK → products.product_id
    product_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(Text, nullable=True)
    # Status: REQUESTED, APPROVED, PROCESSING, SHIPPED, DELIVERED, CANCELLED
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
    order: Mapped["Order"] = relationship("Order", back_populates="replacements")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="replacements")
    product: Mapped["Product"] = relationship("Product", back_populates="replacements")

    def __repr__(self) -> str:
        return f"<Replacement id={self.id} replacement_id={self.replacement_id!r} status={self.status!r}>"
