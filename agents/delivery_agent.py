"""
agents/delivery_agent.py -- DeliveryAgent specialist.

Responsibilities
----------------
- Understand delivery and tracking related support tasks.
- Always calls check_delivery (single allowed tool for this agent).
- Generate a concise human-readable response (via LLM if configured).

Allowed tools: check_delivery
No other database access.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.delivery_tool import check_delivery

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "DeliveryAgent"


def _extract_order_id(task: str) -> str | None:
    """Pull the first ORD-prefixed token from the task string."""
    match = re.search(r"\bORD\d+\w*\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute a delivery-tracking task and return a structured result.

    Parameters
    ----------
    task : str
        Free-text customer support request (e.g. "Track my order ORD009").
    db : Session
        Active SQLAlchemy session.

    Returns
    -------
    dict with keys:
        agent, action, tool, tool_result, response
    """
    llm = LLMProvider()
    action = "check_delivery"

    # 1. Extract order ID
    order_id = _extract_order_id(task)
    if not order_id:
        return {
            "agent": AGENT_NAME,
            "action": None,
            "tool": None,
            "tool_result": None,
            "response": (
                "I need an order ID to track your delivery. "
                "Please provide your order ID (e.g. ORD009)."
            ),
        }

    # 2. Execute tool (deterministic)
    tool_result = check_delivery(order_id, db)

    # 3. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart. "
            f"A customer said: '{task}'\n"
            f"The delivery tool returned: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response about the delivery status. "
            f"If delivery status is DELAYED, acknowledge the inconvenience. "
            f"Do NOT invent tracking or delivery information."
        )
        response = llm.call(prompt)
    else:
        if tool_result.get("success"):
            status = tool_result.get("status")
            tracking = tool_result.get("tracking_id")
            expected = tool_result.get("expected_date")
            base = f"Delivery for order {order_id}: status {status}, tracking ID {tracking}."
            if status == "DELAYED":
                response = (
                    f"{base} We apologise for the delay. "
                    f"Expected date: {expected}."
                )
            elif status == "DELIVERED":
                response = f"{base} Your order has been delivered."
            else:
                response = f"{base} Expected delivery: {expected}."
        else:
            response = tool_result.get("message", "Could not retrieve delivery information.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
