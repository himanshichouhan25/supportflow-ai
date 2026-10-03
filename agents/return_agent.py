"""
agents/return_agent.py -- ReturnAgent specialist.

Responsibilities
----------------
- Understand return-related support tasks.
- Select check_return_eligibility, create_return_request, or verify_return.
- Execute tools deterministically against PostgreSQL.
- Generate concise customer-facing response (via LLM if configured).

Allowed tools: check_return_eligibility, create_return_request, verify_return
No other database access. Return rules remain entirely deterministic.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.return_tool import (
    check_return_eligibility,
    create_return_request,
    verify_return,
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "ReturnAgent"

_RETURN_KEYWORDS = {"return", "returning", "send back", "send product back", "damaged", "defective", "wrong item"}
_CHECK_ELIGIBILITY_KEYWORDS = {"eligible", "eligibility", "can i return", "am i eligible", "policy"}


def _extract_order_id(task: str) -> str | None:
    """Pull the first ORD-prefixed token from the task string."""
    match = re.search(r"\bORD\d+\w*\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_customer_id(task: str) -> str | None:
    """Pull the first C-prefixed customer ID token from the task string if present."""
    match = re.search(r"\bC\d+\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _pick_action(task: str) -> str:
    """
    Keyword-based action selection.

    Returns 'create_return_request', 'check_return_eligibility', or 'verify_return'.
    """
    lower = task.lower()
    if any(kw in lower for kw in _RETURN_KEYWORDS):
        if any(kw in lower for kw in _CHECK_ELIGIBILITY_KEYWORDS):
            return "check_return_eligibility"
        return "create_return_request"
    return "check_return_eligibility"


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute a return-support task and return a structured result.

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
    customer_id = _extract_customer_id(task)

    if not order_id:
        return {
            "agent": AGENT_NAME,
            "action": None,
            "tool": None,
            "tool_result": None,
            "response": (
                "I need an order ID to process a return request. "
                "Please share your order ID (e.g. ORD002)."
            ),
        }

    # 2. Select action
    action = _pick_action(task)

    # 3. Execute tool deterministically
    if action == "create_return_request":
        eligibility = check_return_eligibility(order_id, db)
        if eligibility.get("success") and eligibility.get("eligible"):
            tool_result = create_return_request(
                order_id=order_id,
                db=db,
                customer_id=customer_id,
                reason=task,
            )
            action = "create_return_request"
        else:
            # Check if an existing return record exists for reporting duplicate state
            verified = verify_return(order_id, db)
            if verified.get("success"):
                tool_result = {
                    "success": True,
                    "created": False,
                    "already_exists": True,
                    "eligible": False,
                    "order_id": order_id,
                    "return_id": verified.get("return_id"),
                    "status": verified.get("status"),
                    "reason": "A return request has already been registered for this order.",
                    "verification": verified,
                }
                action = "verify_return"
            else:
                tool_result = eligibility
                action = "check_return_eligibility"

    elif action == "check_return_eligibility":
        tool_result = check_return_eligibility(order_id, db)
    else:
        tool_result = verify_return(order_id, db)

    # 4. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart.\n"
            f"A customer said: '{task}'\n"
            f"The tool returned: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response.\n"
            f"Do NOT invent return details not present in the tool result."
        )
        response = llm.call(prompt)
    else:
        if tool_result.get("success"):
            if action == "create_return_request":
                ret_id = tool_result.get("return_id", "")
                status = tool_result.get("status", "REQUESTED")
                response = (
                    f"Return request for order {order_id} has been successfully registered. "
                    f"(Return ID: {ret_id}, Status: {status})."
                )
            elif action == "verify_return":
                ret_id = tool_result.get("return_id") or tool_result.get("verification", {}).get("return_id", "")
                status = tool_result.get("status") or tool_result.get("verification", {}).get("status", "")
                response = (
                    f"A return request for order {order_id} already exists. "
                    f"(Return ID: {ret_id}, Status: {status})."
                )
            elif action == "check_return_eligibility":
                eligible = tool_result.get("eligible")
                reason = tool_result.get("reason", "")
                response = (
                    f"Return {'is' if eligible else 'is not'} eligible for order {order_id}. "
                    f"{reason}"
                )
            else:
                ret_id = tool_result.get("return_id", "")
                status = tool_result.get("status", "")
                response = f"Return status for order {order_id}: Return ID {ret_id}, Status {status}."
        else:
            response = tool_result.get("message", "Could not process return request.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
