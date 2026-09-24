"""
agents/payment_agent.py -- PaymentAgent specialist.

Responsibilities
----------------
- Understand payment-related support tasks.
- Select either check_payment or check_refund_eligibility.
- Execute the tool deterministically against PostgreSQL.
- Generate a concise human-readable response (via LLM if configured).

Allowed tools: check_payment, check_refund_eligibility
No other database access. Refund rules remain entirely deterministic.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.payment_tool import check_payment, check_refund_eligibility

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "PaymentAgent"

_REFUND_KEYWORDS = {"refund", "refunded", "reimburse", "money back", "return payment", "eligible"}


def _extract_order_id(task: str) -> str | None:
    """Pull the first ORD-prefixed token from the task string."""
    match = re.search(r"\bORD\d+\w*\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _pick_action(task: str) -> str:
    """
    Keyword-based action selection.

    Returns 'check_refund_eligibility' or 'check_payment'.
    """
    lower = task.lower()
    if any(kw in lower for kw in _REFUND_KEYWORDS):
        return "check_refund_eligibility"
    return "check_payment"


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute a payment-support task and return a structured result.

    Parameters
    ----------
    task : str
        Free-text customer support request.
    db : Session
        Active SQLAlchemy session.

    Returns
    -------
    dict with keys:
        agent, action, tool, tool_result, response
    """
    llm = LLMProvider()

    # 1. Extract order ID
    order_id = _extract_order_id(task)
    if not order_id:
        return {
            "agent": AGENT_NAME,
            "action": None,
            "tool": None,
            "tool_result": None,
            "response": (
                "I need an order ID to check payment information. "
                "Please provide your order ID (e.g. ORD005)."
            ),
        }

    # 2. Select action
    action = _pick_action(task)

    # 3. Execute the appropriate tool (deterministic)
    if action == "check_refund_eligibility":
        tool_result = check_refund_eligibility(order_id, db)
    else:
        tool_result = check_payment(order_id, db)

    # 4. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart. "
            f"A customer said: '{task}'\n"
            f"The tool returned: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response. "
            f"Do NOT invent payment details not present in the tool result. "
            f"For refund eligibility, state clearly whether a refund is possible."
        )
        response = llm.call(prompt)
    else:
        if tool_result.get("success"):
            if action == "check_refund_eligibility":
                eligible = tool_result.get("eligible")
                reason = tool_result.get("reason", "")
                response = (
                    f"Refund {'is' if eligible else 'is not'} eligible for order {order_id}. "
                    f"{reason}"
                )
            else:
                status = tool_result.get("status")
                amount = tool_result.get("amount")
                method = tool_result.get("payment_method")
                response = (
                    f"Payment for order {order_id}: status {status}, "
                    f"amount INR {amount}, method {method}."
                )
        else:
            response = tool_result.get("message", "Could not retrieve payment information.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
