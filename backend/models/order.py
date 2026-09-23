"""
models/order.py — Order table definition.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Order(Base):
    """Represents a customer order for a product."""

    __tablename__ = "orders"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # FK → customers.customer_id (the business key, not the surrogate PK)
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

    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    order_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ------------------------------------------------------------------ relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    product: Mapped["Product"] = relationship("Product", back_populates="orders")
    payment: Mapped["Payment"] = relationship("Payment", back_populates="order", uselist=False)
    delivery: Mapped["Delivery"] = relationship("Delivery", back_populates="order", uselist=False)

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_id={self.order_id!r} status={self.order_status!r}>"
