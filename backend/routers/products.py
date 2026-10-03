"""
backend/routers/products.py — FastAPI Router for Product Catalog.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.product import Product

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("", response_model=list[dict[str, Any]])
@router.get("/", response_model=list[dict[str, Any]])
def list_products(
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List products from PostgreSQL catalog."""
    query = db.query(Product)
    if category:
        query = query.filter(Product.category.ilike(f"%{category}%"))

    products = query.all()
    results = []
    for p in products:
        results.append({
            "product_id": p.product_id,
            "name": p.name,
            "category": p.category,
            "price": float(p.price) if p.price else 0.0,
            "stock": p.stock,
            "store": p.store,
        })
    return results


@router.get("/{product_id}", response_model=dict[str, Any])
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve details for a single product by product_id."""
    p = db.query(Product).filter_by(product_id=product_id).first()
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found.",
        )
    return {
        "product_id": p.product_id,
        "name": p.name,
        "category": p.category,
        "price": float(p.price) if p.price else 0.0,
        "stock": p.stock,
        "store": p.store,
    }
