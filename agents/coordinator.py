"""
agents/coordinator.py -- CoordinatorAgent for SupportFlow AI.

Architecture
------------
1. Detect intent(s) from the user message using keyword matching.
2. Prioritise and order the specialist(s) to call.
3. Execute the first specialist.
4. Inspect the result -- decide whether a second specialist is required
   (replanning step).
5. If yes, call the second specialist (max 3 total specialist calls).
6. If the issue remains unresolved, create a support ticket.
7. Build a final customer-facing response from all collected results.
8. Return the full workflow trace + response.

Rules
-----
- Max 3 specialist-agent calls per request.
- LLM called at most once -- only for the final response.
- All routing, replanning, and error handling is deterministic.
- Never fabricate order/payment/delivery/account information.
- Never accesses database directly; only calls specialist run() functions
  and the support ticket service for escalation.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from agents.llm_provider import LLMProvider
from agents.order_agent import run as run_order
from agents.payment_agent import run as run_payment
from agents.delivery_agent import run as run_delivery
from agents.account_agent import run as run_account
from backend.database import SessionLocal
from backend.services.support_ticket_service import create_support_ticket


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SPECIALIST_CALLS = 3

_ORDER_KW = {
    "order",
    "cancel",
    "cancellation",
    "item",
    "product",
    "purchase",
    "bought",
    "status",
}

_PAYMENT_KW = {
    "payment",
    "paid",
    "pay",
    "transaction",
    "refund",
    "charge",
    "money",
    "amount",
    "upi",
    "card",
}

_DELIVERY_KW = {
    "delivery",
    "deliver",
    "track",
    "tracking",
    "shipped",
    "ship",
    "package",
    "courier",
    "dispatch",
}

_ACCOUNT_KW = {
    "account",
    "profile",
    "email",
    "phone",
    "customer",
    "registered",
    "name",
    "contact",
}


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _detect_intents(message: str) -> list[str]:
    """
    Return a list of intent labels present in the message,
    ordered by priority.

    Priority:
        payment > order > delivery > account

    Returns at least one intent; falls back to 'unknown'.
    """

    lower = set(re.findall(r"[a-z]+", message.lower()))
    found: list[str] = []

    if lower & _PAYMENT_KW:
        found.append("payment")

    if lower & _ORDER_KW:
        found.append("order")

    if lower & _DELIVERY_KW:
        found.append("delivery")

    if lower & _ACCOUNT_KW:
        found.append("account")

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []

    for intent in found:
        if intent not in seen:
            unique.append(intent)
            seen.add(intent)

    return unique if unique else ["unknown"]


# ---------------------------------------------------------------------------
# ID extraction
# ---------------------------------------------------------------------------

def _extract_order_id(message: str) -> str | None:
    """Extract the first ORD+digits token from the message."""

    match = re.search(r"\bORD\d+\w*\b", message, re.IGNORECASE)

    return match.group(0).upper() if match else None


def _extract_customer_id(message: str) -> str | None:
    """Extract the first C+digits customer ID from the message."""

    match = re.search(r"\bC\d+\b", message, re.IGNORECASE)

    return match.group(0).upper() if match else None


# ---------------------------------------------------------------------------
# Replanning logic
# ---------------------------------------------------------------------------

def _needs_followup(
    primary_intent: str,
    agent_result: dict[str, Any],
    all_intents: list[str],
    called: list[str],
) -> str | None:
    """
    Determine whether a follow-up specialist is needed after observing
    the primary result.

    Returns:
        Next intent label to call, or None if complete.
    """

    # If there are remaining intents not yet called, check them first.
    remaining = [
        intent
        for intent in all_intents
        if intent not in called and intent != "unknown"
    ]

    if remaining:
        return remaining[0]

    # Domain-specific replanning rules
    tool_result = agent_result.get("tool_result") or {}

    if primary_intent == "payment":
        # Payment SUCCESS but order may still be pending.
        pay_status = tool_result.get("status", "")

        if pay_status == "SUCCESS" and "order" not in called:
            return "order"

    if primary_intent == "order":
        # Cancelled order -> check refund/payment information.
        order_status = tool_result.get("status", "")

        if order_status == "CANCELLED" and "payment" not in called:
            return "payment"

    return None


# ---------------------------------------------------------------------------
# Specialist dispatcher
# ---------------------------------------------------------------------------

def _call_specialist(
    intent: str,
    message: str,
    db: Session,
    step_num: int,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Dispatch to the correct specialist, append workflow steps,
    and return result.
    """

    DISPATCH = {
        "order": run_order,
        "payment": run_payment,
        "delivery": run_delivery,
        "account": run_account,
    }

    fn = DISPATCH.get(intent)

    if fn is None:
        return {
            "success": False,
            "message": f"No specialist for intent '{intent}'.",
        }

    # Order/payment/delivery require an order ID.
    _needs_order_id = intent in ("order", "payment", "delivery")

    if _needs_order_id and _extract_order_id(message) is None:
        clarification = (
            "Please provide your order ID (for example, ORD005) so I can "
            "look into your request."
        )

        steps.append(
            {
                "step": step_num,
                "agent": "Coordinator",
                "action": (
                    f"Order ID required for {intent} query "
                    "-- requesting clarification"
                ),
                "status": "completed",
            }
        )

        return {
            "success": True,
            "action": "clarification_needed",
            "agent": f"{intent.capitalize()}Agent",
            "tool": None,
            "tool_result": {
                "success": False,
                "message": clarification,
            },
            "final_response": clarification,
            "missing": "order_id",
        }

    # Account intent requires customer ID.
    if intent == "account" and _extract_customer_id(message) is None:
        clarification = (
            "Please provide your customer ID (for example, C101) so I can "
            "look up your account."
        )

        steps.append(
            {
                "step": step_num,
                "agent": "Coordinator",
                "action": (
                    "Customer ID required for account query "
                    "-- requesting clarification"
                ),
                "status": "completed",
            }
        )

        return {
            "success": True,
            "action": "clarification_needed",
            "agent": "AccountAgent",
            "tool": None,
            "tool_result": {
                "success": False,
                "message": clarification,
            },
            "final_response": clarification,
            "missing": "customer_id",
        }

    steps.append(
        {
            "step": step_num,
            "agent": "Coordinator",
            "action": (
                f"Routing {intent} issue to "
                f"{intent.capitalize()}Agent"
            ),
            "status": "completed",
        }
    )

    result = fn(message, db)

    steps.append(
        {
            "step": step_num + 1,
            "agent": result.get(
                "agent",
                f"{intent.capitalize()}Agent",
            ),
            "action": result.get("action", intent),
            "tool": result.get("tool", intent),
            "status": "completed",
        }
    )

    return result


# ---------------------------------------------------------------------------
# Customer-friendly response helpers
# ---------------------------------------------------------------------------

def _fmt_amount(amount: Any) -> str:
    """Format a numeric amount as INR X,XX,XXX."""

    if amount is None:
        return ""

    try:
        return f"INR {float(amount):,.2f}"
    except (ValueError, TypeError):
        return str(amount)


def _fmt_date(iso: Any) -> str:
    """Convert an ISO date string to a readable date."""

    if not iso:
        return ""

    try:
        from datetime import date as _date

        d = _date.fromisoformat(str(iso)[:10])

        return d.strftime("%d %B %Y").lstrip("0")

    except Exception:
        return str(iso)[:10]


def _build_order_text(
    tr: dict[str, Any],
    action: str,
) -> str:

    oid = tr.get("order_id", "")
    status = tr.get("status", "").upper()

    if action == "cancel_order":

        if not tr.get("success", True):
            msg = tr.get("message", "")

            if "already" in msg.lower():
                return (
                    f"Your order **{oid}** has already been cancelled. "
                    "No further cancellation action is needed."
                )

            if "delivered" in msg.lower():
                return (
                    f"Your order **{oid}** cannot be cancelled because "
                    "it has already been delivered."
                )

            return f"Your order **{oid}** could not be cancelled: {msg}"

        return (
            f"Your order **{oid}** has been successfully cancelled.\n\n"
            "The cancellation has been recorded in our system."
        )

    # check_order
    if status == "DELIVERED":
        return (
            f"Your order **{oid}** has been delivered successfully.\n\n"
            "No further action is required."
        )

    if status == "PENDING":
        return (
            f"Your order **{oid}** is currently pending and has not yet "
            "moved to the next processing stage.\n\n"
            "Please allow some time for the order status to update."
        )

    if status == "CONFIRMED":
        return (
            f"Your order **{oid}** has been confirmed and is being "
            "prepared for dispatch."
        )

    if status == "SHIPPED":
        return (
            f"Your order **{oid}** has been shipped and is on its way to you."
        )

    if status == "CANCELLED":
        return f"Your order **{oid}** has been cancelled."

    return f"Your order **{oid}** currently has a status of {status}."


def _build_payment_text(
    tr: dict[str, Any],
    action: str,
) -> str:

    oid = tr.get("order_id", "")

    if action == "check_refund_eligibility":

        eligible = tr.get("eligible")
        reason = tr.get("reason", "")
        amount = _fmt_amount(tr.get("amount"))

        if eligible:
            amt_str = f" of {amount}" if amount else ""

            return (
                f"Your order **{oid}** is eligible for a refund{amt_str}.\n\n"
                f"{reason}"
            )

        return (
            f"A refund for order **{oid}** is not currently available.\n\n"
            f"{reason}"
        )

    pay_status = tr.get("status", "").upper()
    amount = _fmt_amount(tr.get("amount"))
    method = tr.get("payment_method", "")

    amount_str = f" of {amount}" if amount else ""
    method_str = f" via {method}" if method else ""

    if pay_status == "SUCCESS":
        return (
            f"Your payment{amount_str}{method_str} for order **{oid}** "
            "was successfully received."
        )

    if pay_status == "FAILED":
        return (
            f"The payment for order **{oid}** was not successful. "
            f"No charge{amount_str} has been applied."
        )

    if pay_status == "REFUNDED":
        return (
            f"The payment for order **{oid}** has already been refunded"
            f"{amount_str}."
        )

    if pay_status == "PENDING":
        return f"Your payment for order **{oid}** is currently pending."

    return (
        f"The payment status for order **{oid}** is: {pay_status}."
    )


def _build_delivery_text(tr: dict[str, Any]) -> str:

    oid = tr.get("order_id", "")
    status = tr.get("status", "").upper()
    tracking = tr.get("tracking_id", "")
    expected = _fmt_date(tr.get("expected_date"))

    tracking_str = (
        f"\n\nTracking ID: **{tracking}**"
        if tracking
        else ""
    )

    expected_str = (
        f"\n\nExpected delivery date: {expected}."
        if expected
        else ""
    )

    if status == "DELIVERED":
        return (
            f"Your order **{oid}** has been delivered successfully."
            f"{tracking_str}\n\nNo further action is required."
        )

    if status == "DELAYED":
        return (
            f"We are sorry -- your order **{oid}** is currently "
            f"experiencing a delay."
            f"{tracking_str}{expected_str}\n\n"
            "Our logistics team is working to deliver your order "
            "as soon as possible."
        )

    if status == "SHIPPED":
        return (
            f"Your order **{oid}** has been shipped and is on its way "
            f"to you.{tracking_str}{expected_str}"
        )

    if status == "OUT_FOR_DELIVERY":
        return (
            f"Your order **{oid}** is out for delivery today!"
            f"{tracking_str}"
        )

    if status in ("PENDING", "PROCESSING"):
        return (
            f"Your order **{oid}** is being prepared for shipment."
            f"{expected_str}"
        )

    return (
        f"The delivery status for order **{oid}** is: {status}."
        f"{tracking_str}{expected_str}"
    )


def _build_account_text(tr: dict[str, Any]) -> str:

    cid = tr.get("customer_id", "")
    name = tr.get("name", "")
    email = tr.get("email", "")
    status = tr.get("account_status", "")

    name_str = (
        f"Name: **{name}**\n\n"
        if name
        else ""
    )

    email_str = (
        f"Registered email: **{email}**\n\n"
        if email
        else ""
    )

    status_str = (
        f"Account status: **{status}**"
        if status
        else ""
    )

    return (
        f"Here is the account information for **{cid}**:\n\n"
        f"{name_str}{email_str}{status_str}"
    ).strip()


# ---------------------------------------------------------------------------
# Final response builder
# ---------------------------------------------------------------------------

def _build_response(
    user_message: str,
    results: list[dict[str, Any]],
) -> str:
    """
    Build a final customer-facing response.

    Tries the LLM once with a clear, fact-based prompt.
    Falls back to deterministic customer-friendly response if unavailable.
    """

    llm = LLMProvider()

    if llm.is_live and results:

        fact_lines: list[str] = []

        for result in results:

            tr = result.get("tool_result") or {}
            agent = result.get("agent", "")
            action = result.get("action", "")

            if not tr.get("success", True):
                fact_lines.append(
                    tr.get("message", "")
                )

            elif "Order" in agent:
                fact_lines.append(
                    _build_order_text(tr, action)
                )

            elif "Payment" in agent:
                fact_lines.append(
                    _build_payment_text(tr, action)
                )

            elif "Delivery" in agent:
                fact_lines.append(
                    _build_delivery_text(tr)
                )

            elif "Account" in agent:
                fact_lines.append(
                    _build_account_text(tr)
                )

        facts = "\n\n".join(fact_lines)

        prompt = (
            "You are a helpful, professional customer support agent "
            "for ShopKart, an Indian e-commerce platform.\n\n"
            f"The customer said: '{user_message}'\n\n"
            f"Verified facts from our system:\n{facts}\n\n"
            "Using ONLY the verified facts above, write a clear, "
            "natural, and polite customer-support response addressing "
            "the customer directly. "
            "Do NOT invent amounts, dates, policies, or guarantees "
            "not in the facts. "
            "Do NOT mention agents, tools, or system internals. "
            "Keep the response under 100 words."
        )

        return llm.call(prompt)

    # Deterministic fallback
    parts: list[str] = []

    for result in results:

        tr = result.get("tool_result") or {}
        agent = result.get("agent", "")
        action = result.get("action", "")

        if not tr.get("success", True):

            parts.append(
                tr.get(
                    "message",
                    "We were unable to process your request. "
                    "Please try again.",
                )
            )

            continue

        if "OrderAgent" in agent:
            parts.append(
                _build_order_text(tr, action)
            )

        elif "PaymentAgent" in agent:
            parts.append(
                _build_payment_text(tr, action)
            )

        elif "DeliveryAgent" in agent:
            parts.append(
                _build_delivery_text(tr)
            )

        elif "AccountAgent" in agent:
            parts.append(
                _build_account_text(tr)
            )

    # Remove consecutive duplicate messages.
    deduped: list[str] = []

    for part in parts:
        if not deduped or part != deduped[-1]:
            deduped.append(part)

    return (
        "\n\n".join(deduped)
        if deduped
        else (
            "We were unable to retrieve the requested information "
            "at this time. Please contact our support team for "
            "further assistance."
        )
    )


# ---------------------------------------------------------------------------
# Support ticket escalation
# ---------------------------------------------------------------------------

def _create_escalation_ticket(
    user_message: str,
    db: Session,
    steps: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Create a support ticket when the coordinator cannot fully resolve
    the customer's issue.

    Ticket creation is deterministic and uses the existing
    support_ticket_service.
    """

    order_id = _extract_order_id(user_message)
    customer_id = _extract_customer_id(user_message)

    try:

        ticket = create_support_ticket(
            db=db,
            issue=user_message,
            customer_id=customer_id,
            order_id=order_id,
        )

        steps.append(
            {
                "step": len(steps) + 1,
                "agent": "Coordinator",
                "action": (
                    f"Created support ticket {ticket['ticket_id']} "
                    "for unresolved issue"
                ),
                "status": "completed",
            }
        )

        return ticket

    except Exception as exc:

        steps.append(
            {
                "step": len(steps) + 1,
                "agent": "Coordinator",
                "action": (
                    f"Failed to create support ticket: {exc}"
                ),
                "status": "error",
            }
        )

        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_coordinator(
    user_message: str,
    db: Session | None = None,
) -> dict[str, Any]:
    """
    Orchestrate specialist agents to resolve a customer support request.

    Parameters
    ----------
    user_message : str
        Raw customer support message.

    db : Session | None
        SQLAlchemy session. If None, one is created and closed automatically.

    Returns
    -------
    dict
        success,
        final_response,
        intent,
        intents,
        resolved,
        ticket,
        steps
    """

    steps: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    called: list[str] = []

    specialist_call_count = 0

    # ------------------------------------------------------------------
    # Guard: empty message
    # ------------------------------------------------------------------

    if not user_message or not user_message.strip():

        return {
            "success": True,
            "final_response": (
                "Hello! I am the SupportFlow AI assistant. "
                "How can I help you today? I can assist with orders, "
                "payments, deliveries, and account queries."
            ),
            "intent": "unknown",
            "intents": [],
            "resolved": False,
            "ticket": None,
            "steps": [],
        }

    # ------------------------------------------------------------------
    # Step 1 -- Intent detection
    # ------------------------------------------------------------------

    intents = _detect_intents(user_message)
    primary_intent = intents[0]

    steps.append(
        {
            "step": 1,
            "agent": "Coordinator",
            "action": (
                f"Detected intent(s): {', '.join(intents)}"
            ),
            "status": "completed",
        }
    )

    # ------------------------------------------------------------------
    # Guard: unknown intent
    # ------------------------------------------------------------------

    if primary_intent == "unknown":

        steps.append(
            {
                "step": 2,
                "agent": "Coordinator",
                "action": (
                    "Intent not recognised -- returning clarification"
                ),
                "status": "completed",
            }
        )

        return {
            "success": True,
            "final_response": (
                "I can currently help with orders, payments, deliveries, "
                "and account queries. Could you please provide more details "
                "about your issue?"
            ),
            "intent": "unknown",
            "intents": intents,
            "resolved": False,
            "ticket": None,
            "steps": steps,
        }

    # ------------------------------------------------------------------
    # Manage DB session lifetime
    # ------------------------------------------------------------------

    _own_session = db is None

    if _own_session:
        db = SessionLocal()

    try:

        current_step = 2

        # --------------------------------------------------------------
        # Main loop -- max 3 specialist calls
        # --------------------------------------------------------------

        next_intent: str | None = primary_intent

        while (
            next_intent
            and specialist_call_count < MAX_SPECIALIST_CALLS
        ):

            result = _call_specialist(
                intent=next_intent,
                message=user_message,
                db=db,
                step_num=current_step,
                steps=steps,
            )

            results.append(result)
            called.append(next_intent)

            specialist_call_count += 1
            current_step += 2

            # Replanning check
            next_intent = _needs_followup(
                next_intent,
                result,
                intents,
                called,
            )

            if next_intent:

                steps.append(
                    {
                        "step": current_step,
                        "agent": "Coordinator",
                        "action": (
                            f"Observed result -- replanning: "
                            f"{next_intent} check required"
                        ),
                        "status": "replanning",
                    }
                )

                current_step += 1

        # --------------------------------------------------------------
        # Determine whether clarification is required
        # --------------------------------------------------------------

        missing_type: str | None = None

        for result in results:

            if (
                result.get("action") == "clarification_needed"
                and result.get("missing")
            ):
                missing_type = result["missing"]
                break

        # --------------------------------------------------------------
        # Determine resolution status
        # --------------------------------------------------------------

        has_actual_result = False
        unresolved = False

        for result in results:

            tool_result = result.get("tool_result")

            if tool_result is None:
                continue

            # A clarification is not an unresolved business operation.
            if result.get("action") == "clarification_needed":
                continue

            has_actual_result = True

            if not tool_result.get("success", False):
                unresolved = True

        resolved = has_actual_result and not unresolved

        # --------------------------------------------------------------
        # Create support ticket if issue remains unresolved
        # --------------------------------------------------------------

        ticket: dict[str, Any] | None = None

        if unresolved and missing_type is None:

            ticket = _create_escalation_ticket(
                user_message=user_message,
                db=db,
                steps=steps,
            )

        # --------------------------------------------------------------
        # Build normal response
        # --------------------------------------------------------------

        final_response = _build_response(
            user_message,
            results,
        )

        # --------------------------------------------------------------
        # Add escalation information
        # --------------------------------------------------------------

        if ticket:

            final_response = (
                f"{final_response}\n\n"
                "I couldn't fully resolve this issue automatically, "
                "so I've created a support ticket for you.\n\n"
                f"Ticket ID: **{ticket['ticket_id']}**\n"
                f"Status: **{ticket['status']}**\n\n"
                "Our support team can review your request."
            )

        elif unresolved and missing_type is None:

            final_response = (
                f"{final_response}\n\n"
                "I was unable to create a support ticket automatically. "
                "Please contact our support team for further assistance."
            )

        # --------------------------------------------------------------
        # Final workflow step
        # --------------------------------------------------------------

        if ticket:

            final_action = (
                f"Escalated unresolved issue to "
                f"{ticket['ticket_id']}"
            )

        elif missing_type:

            final_action = (
                "Request requires customer clarification"
            )

        elif resolved:

            final_action = (
                "Combined all results and resolved the request"
            )

        else:

            final_action = (
                "Completed workflow without full resolution"
            )

        steps.append(
            {
                "step": len(steps) + 1,
                "agent": "Coordinator",
                "action": final_action,
                "status": "completed",
            }
        )

        return {
            "success": True,
            "final_response": final_response,
            "intent": primary_intent,
            "intents": intents,
            "resolved": resolved,
            "missing": missing_type,
            "ticket": ticket,
            "steps": steps,
        }

    except Exception as exc:

        steps.append(
            {
                "step": len(steps) + 1,
                "agent": "Coordinator",
                "action": f"Error: {exc}",
                "status": "error",
            }
        )

        return {
            "success": False,
            "final_response": (
                "An unexpected error occurred while processing your "
                "request. Please try again or contact support."
            ),
            "intent": primary_intent,
            "intents": intents,
            "resolved": False,
            "ticket": None,
            "steps": steps,
        }

    finally:

        if _own_session and db is not None:
            db.close()

