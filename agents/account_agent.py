"""
agents/account_agent.py -- AccountAgent specialist.

Responsibilities
----------------
- Understand account/profile related support tasks.
- Always calls check_account (single allowed tool for this agent).
- Returns only safe, non-sensitive customer profile data.
- Generate a concise human-readable response (via LLM if configured).

Allowed tools: check_account
No passwords or authentication data are ever returned.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from tools.account_tool import check_account

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

AGENT_NAME = "AccountAgent"


def _extract_customer_id(task: str) -> str | None:
    """Pull the first C-prefixed customer ID token from the task string."""
    match = re.search(r"\bC\d+\b", task, re.IGNORECASE)
    return match.group(0).upper() if match else None


def run(task: str, db: Session) -> dict[str, Any]:
    """
    Execute an account-profile task and return a structured result.

    Parameters
    ----------
    task : str
        Free-text customer support request (e.g. "Show account for C101").
    db : Session
        Active SQLAlchemy session.

    Returns
    -------
    dict with keys:
        agent, action, tool, tool_result, response
    """
    llm = LLMProvider()
    action = "check_account"

    # 1. Extract customer ID
    customer_id = _extract_customer_id(task)
    if not customer_id:
        return {
            "agent": AGENT_NAME,
            "action": None,
            "tool": None,
            "tool_result": None,
            "response": (
                "I need a customer ID to look up account details. "
                "Please provide your customer ID (e.g. C101)."
            ),
        }

    # 2. Execute tool (deterministic)
    tool_result = check_account(customer_id, db)

    # 3. Generate response
    if llm.is_live:
        prompt = (
            f"You are a customer support agent for ShopKart. "
            f"A customer said: '{task}'\n"
            f"The account tool returned: {tool_result}\n"
            f"Write a concise, polite 1-2 sentence response with the account details. "
            f"Do NOT reveal passwords or sensitive authentication information. "
            f"Only use information present in the tool result."
        )
        response = llm.call(prompt)
    else:
        if tool_result.get("success"):
            name = tool_result.get("name")
            email = tool_result.get("email")
            status = tool_result.get("account_status")
            response = (
                f"Account {customer_id}: name '{name}', "
                f"email {email}, status {status}."
            )
        else:
            response = tool_result.get("message", "Could not retrieve account information.")

    return {
        "agent": AGENT_NAME,
        "action": action,
        "tool": action,
        "tool_result": tool_result,
        "response": response,
    }
