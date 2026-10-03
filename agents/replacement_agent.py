"""
agents/replacement_agent.py -- ReplacementAgent specialist.

Responsibilities
----------------
- Understand replacement-related support tasks.
- Select check_replacement_eligibility, create_replacement_request, or verify_replacement.
- Execute tools deterministically against PostgreSQL.
- Generate concise customer-facing response (via LLM if configured).

Allowed tools: check_replacement_eligibility, create_replacement_request, verify_replacement
No other database access. Replacement rules remain entirely deterministic.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.replacement_tool import (
    check_replacement_eligibility,
    create_replacement_request,
    verify_replacement,
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "ReplacementAgent"

_REPLACEMENT_KEYWORDS = {"replace", "replacement", "exchange", "substitute"}
_CHECK_ELIGIBILITY_KEYWORDS = {"eligible", "eligibility", "can i replace", "am i eligible", "policy"}


def _extract_order_id(task: str) -> str | None:
    """Pull the first ORD-prefixed token from the task string."""
    match = re.search(r"\bORD\d+\w*\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_customer_id(task: str) -> str | None:
    """Pull the first C-prefixed customer ID token from the task string if present."""
    match = re.search(r"\bC\d+\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_product_id(task: str) -> str | None:
    """Pull the first P-prefixed product ID token from the task string if present."""
    match = re.search(r"\bP\d+\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _pick_action(task: str) -> str:
    """
    Keyword-based action selection.

    Returns 'create_replacement_request', 'check_replacement_eligibility', or 'verify_replacement'.
    """
    lower = task.lower()
    if any(kw in lower for kw in _REPLACEMENT_KEYWORDS):
        if any(kw in lower for kw in _CHECK_ELIGIBILITY_KEYWORDS):
            return "check_replacement_eligibility"
        return "create_replacement_request"
    return "check_replacement_eligibility"


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute a replacement-support task and return a structured result.

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

    # 1. Extract IDs
    order_id = _extract_order_id(task)
    customer_id = _extract_customer_id(task)
    product_id = _extract_product_id(task)

    if not order_id:
        return {
            "agent": AGENT_NAME,
            "action": None,
            "tool": None,
            "tool_result": None,
            "response": (
                "I need an order ID to process a replacement request. "
                "Please share your order ID (e.g. ORD002)."
            ),
        }

    # 2. Select action
    action = _pick_action(task)

    # 3. Execute tool deterministically
    if action == "create_replacement_request":
        eligibility = check_replacement_eligibility(order_id, db)
        if eligibility.get("success") and eligibility.get("eligible"):
            tool_result = create_replacement_request(
                order_id=order_id,
                db=db,
                customer_id=customer_id,
                product_id=product_id,
                reason=task,
            )
            action = "create_replacement_request"
        else:
            # Check if an existing active replacement record exists for reporting duplicate state
            verified = verify_replacement(order_id, db)
            if verified.get("success"):
                tool_result = {
                    "success": True,
                    "created": False,
                    "already_exists": True,
                    "eligible": False,
                    "order_id": order_id,
                    "replacement_id": verified.get("replacement_id"),
                    "status": verified.get("status"),
                    "reason": "A replacement request has already been registered for this order.",
                    "verification": verified,
                }
                action = "verify_replacement"
            else:
                tool_result = eligibility
                action = "check_replacement_eligibility"

    elif action == "check_replacement_eligibility":
        tool_result = check_replacement_eligibility(order_id, db)
    else:
        tool_result = verify_replacement(order_id, db)

    # 4. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart.\n"
            f"A customer said: '{task}'\n"
            f"The tool returned: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response.\n"
            f"Do NOT invent replacement details not present in the tool result."
        )
        response = llm.call(prompt)
    else:
        if tool_result.get("success"):
            if action == "create_replacement_request":
                rep_id = tool_result.get("replacement_id", "")
                status = tool_result.get("status", "REQUESTED")
                response = (
                    f"Replacement request for order {order_id} has been successfully registered. "
                    f"(Replacement ID: {rep_id}, Status: {status})."
                )
            elif action == "verify_replacement":
                rep_id = tool_result.get("replacement_id") or tool_result.get("verification", {}).get("replacement_id", "")
                status = tool_result.get("status") or tool_result.get("verification", {}).get("status", "")
                response = (
                    f"A replacement request for order {order_id} already exists. "
                    f"(Replacement ID: {rep_id}, Status: {status})."
                )
            elif action == "check_replacement_eligibility":
                eligible = tool_result.get("eligible")
                reason = tool_result.get("reason", "")
                response = (
                    f"Replacement {'is' if eligible else 'is not'} eligible for order {order_id}. "
                    f"{reason}"
                )
            else:
                rep_id = tool_result.get("replacement_id", "")
                status = tool_result.get("status", "")
                response = f"Replacement status for order {order_id}: Replacement ID {rep_id}, Status {status}."
        else:
            response = tool_result.get("message", "Could not process replacement request.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
