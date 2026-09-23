"""
models/customer.py — Customer table definition.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Customer(Base):
    """Represents a customer account."""

    __tablename__ = "customers"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    account_status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ------------------------------------------------------------------ relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer id={self.id} customer_id={self.customer_id!r} email={self.email!r}>"
