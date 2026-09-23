"""
tools/account_tool.py — Deterministic customer account lookup tool.

Functions
---------
check_account(customer_id)  → retrieve safe customer profile information

No passwords, tokens, or sensitive auth data are returned.
No LLM calls; purely deterministic database logic.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.models.customer import Customer


def check_account(customer_id: str, db: Session) -> dict[str, Any]:
    """
    Retrieve safe customer profile information by customer_id.

    Only non-sensitive fields are returned:
        customer_id, name, email, phone, account_status, created_at

    Returns {'success': False, 'message': '...'} when the customer
    does not exist.
    """
    customer: Customer | None = db.query(Customer).filter_by(customer_id=customer_id).first()

    if not customer:
        return {"success": False, "message": f"Customer '{customer_id}' not found."}

    return {
        "success": True,
        "customer_id": customer.customer_id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "account_status": customer.account_status,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }
