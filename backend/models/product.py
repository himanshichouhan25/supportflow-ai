"""
models/product.py — Product table definition.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Product(Base):
    """Represents a product available in the store."""

    __tablename__ = "products"

    # ------------------------------------------------------------------ columns
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    # Numeric(10, 2) → up to 9,999,999.99; avoids floating-point rounding issues
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(nullable=False, default=0)
    store: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ------------------------------------------------------------------ relationships
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} product_id={self.product_id!r} name={self.name!r}>"
