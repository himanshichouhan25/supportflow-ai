"""
agents/order_agent.py -- OrderAgent specialist.

Responsibilities
----------------
- Understand order-related support tasks.
- Select either check_order or cancel_order.
- Execute the tool deterministically against PostgreSQL.
- Generate a concise human-readable response (via LLM if configured).

Allowed tools: check_order, cancel_order
No other database access.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.order_tool import cancel_order, check_order

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "OrderAgent"

_CANCEL_KEYWORDS = {"cancel", "cancellation", "cancelling", "cancelled"}
_CHECK_KEYWORDS = {"status", "check", "where", "track", "find", "what", "show", "details"}


def _extract_order_id(task: str) -> str | None:
    """Pull the first ORD-prefixed token from the task string."""
    match = re.search(r"\bORD\d+\w*\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _pick_action(task: str) -> str:
    """
    Keyword-based action selection.

    Returns 'cancel_order' or 'check_order'.
    Used as a deterministic fallback (and as the primary selector when no
    LLM is configured so the tool is always called correctly).
    """
    lower = task.lower()
    if any(kw in lower for kw in _CANCEL_KEYWORDS):
        return "cancel_order"
    return "check_order"


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute an order-support task and return a structured result.

    Parameters
    ----------
    task : str
        Free-text customer support request (e.g. "Cancel order ORD001").
    db : Session
        Active SQLAlchemy session -- injected by the caller or test.

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
                "I need an order ID to help you. "
                "Please share your order ID (e.g. ORD001) and I will look it up."
            ),
        }

    # 2. Select action (deterministic keyword match)
    action = _pick_action(task)

    # 3. Execute the appropriate tool
    if action == "cancel_order":
        tool_result = cancel_order(order_id, db)
    else:
        tool_result = check_order(order_id, db)

    # 4. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart. "
            f"A customer said: '{task}'\n"
            f"The tool returned this result: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response. "
            f"Do NOT invent any information not in the tool result."
        )
        response = llm.call(prompt)
    else:
        # Deterministic stub response
        if tool_result.get("success"):
            if action == "cancel_order":
                response = (
                    f"Your order {order_id} has been successfully cancelled. "
                    f"Current status: {tool_result.get('status')}."
                )
            else:
                response = (
                    f"Order {order_id} status: {tool_result.get('status')}. "
                    f"Quantity: {tool_result.get('quantity')}, "
                    f"Total: INR {tool_result.get('total_amount')}."
                )
        else:
            response = tool_result.get("message", "Could not process your request.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
