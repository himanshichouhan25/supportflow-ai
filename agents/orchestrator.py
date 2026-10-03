"""
agents/orchestrator.py — Agentic Orchestration Controller for SupportFlow AI.

Architecture
------------
1. State Initialization: Create a fresh AgentState for each customer request.
2. Goal Understanding: Parse user message into structured intent and entities (order_id, customer_id, product_id, reason).
3. Required Information Check: If required IDs are missing for state-changing or query operations, set status to NEEDS_CLARIFICATION.
4. Plan Creation: Generate a structured sequence of ActionItems.
5. Action Selection & Specialist Execution: Step through plan items, executing domain services/agents.
6. Observation Storage: Store exact tool results after every action.
7. Verification: Verify persistent state changes in PostgreSQL before resolving.
8. Replanning & Escalation: If ineligible or failed, trigger replanning/escalation and create a support ticket.
9. Final Response Generation: Return a structured orchestration result.
"""

from __future__ import annotations

import re
from typing import Any
from sqlalchemy.orm import Session

from knowledge import PolicyRetriever
from agents.state import AgentState, ActionItem, AgentDecision, OrchestrationStatus
from backend.database import SessionLocal
from backend.models.order import Order

from backend.services.refund_service import (
    check_refund_eligibility,
    process_refund,
    verify_refund,
)
from backend.services.return_service import (
    check_return_eligibility,
    create_return_request,
    verify_return,
)
from backend.services.replacement_service import (
    check_replacement_eligibility,
    create_replacement_request,
    verify_replacement,
)
from backend.services.support_ticket_service import create_support_ticket

from agents.order_agent import run as run_order
from agents.payment_agent import run as run_payment
from agents.delivery_agent import run as run_delivery
from agents.account_agent import run as run_account
from agents.return_agent import run as run_return
from agents.replacement_agent import run as run_replacement


# ---------------------------------------------------------------------------
# Helper Extraction Functions
# ---------------------------------------------------------------------------

_ORDER_KW = {"order", "cancel", "cancellation", "item", "product", "purchase", "bought", "status"}
_PAYMENT_KW = {"payment", "paid", "pay", "transaction", "refund", "charge", "money", "amount", "upi", "card"}
_DELIVERY_KW = {"delivery", "deliver", "track", "tracking", "shipped", "ship", "package", "courier", "dispatch"}
_ACCOUNT_KW = {"account", "profile", "email", "phone", "customer", "registered", "name", "contact"}
_RETURN_KW = {"return", "returning", "sendback"}
_REPLACEMENT_KW = {"replace", "replacement", "exchange", "substitute"}


def _detect_intents(message: str) -> list[str]:
    """Detect customer intent from message, ordered by domain priority."""
    lower_tokens = set(re.findall(r"[a-z]+", message.lower()))
    found: list[str] = []

    if (
        lower_tokens & _REPLACEMENT_KW
        or "send replacement" in message.lower()
        or "need replacement" in message.lower()
        or "want replacement" in message.lower()
    ):
        found.append("replacement")

    if lower_tokens & _RETURN_KW or "send back" in message.lower():
        found.append("return")

    if lower_tokens & _PAYMENT_KW:
        found.append("payment")

    if lower_tokens & _ORDER_KW:
        found.append("order")

    if lower_tokens & _DELIVERY_KW:
        found.append("delivery")

    if lower_tokens & _ACCOUNT_KW:
        found.append("account")

    seen: set[str] = set()
    unique: list[str] = []
    for intent in found:
        if intent not in seen:
            unique.append(intent)
            seen.add(intent)

    return unique if unique else ["unknown"]


def _extract_order_id(message: str) -> str | None:
    match = re.search(r"\bORD\d+\w*\b", message, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_customer_id(message: str) -> str | None:
    match = re.search(r"\bC\d+\b", message, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_product_id(message: str) -> str | None:
    match = re.search(r"\bP\d+\b", message, re.IGNORECASE)
    return match.group(0).upper() if match else None


def _extract_reason(message: str) -> str | None:
    lower = message.lower()
    for marker in ["because", "due to", "reason:", "reason is"]:
        if marker in lower:
            parts = message.split(marker, 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
    return None


# ---------------------------------------------------------------------------
# Orchestrator Class
# ---------------------------------------------------------------------------

class Orchestrator:
    """Central Workflow Orchestrator for SupportFlow AI."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def _make_decision(self, state: AgentState, db: Session) -> AgentDecision:
        """
        Synthesize Goal, Policy Context, and Transactional Facts into an AgentDecision.
        """
        intent = state.intent
        order_id = state.order_id
        customer_id = state.customer_id
        policy_ctx = state.policy_context

        display_intent = "refund" if "refund" in state.user_request.lower() else intent
        goal = f"Resolve {display_intent} support request"
        if order_id:
            goal = f"Process {display_intent} for order {order_id}"
        elif customer_id:
            goal = f"Manage account request for customer {customer_id}"


        policy_supported = True
        policy_confidence = policy_ctx.retrieval_confidence if policy_ctx else 0.0
        if not policy_ctx or policy_ctx.requires_policy_review or not policy_ctx.top_policy:
            policy_supported = False

        order_obj = None
        order_status = None
        payment_status = None
        if order_id:
            order_obj = db.query(Order).filter_by(order_id=order_id).first()
            if order_obj:
                order_status = (order_obj.order_status or "").upper()
                if order_obj.payment:
                    payment_status = (order_obj.payment.payment_status or "").upper()


        requires_clarify = False
        requires_escalate = False
        selected_agent = intent
        selected_action = f"process_{intent}" if intent in ("refund", "return", "replacement") else "lookup"
        rationale = ""

        if intent in ("refund", "return", "replacement", "order", "payment", "delivery") and not order_id:
            requires_clarify = True
            selected_action = "clarify"
            rationale = f"Policy coverage is sufficient, but order ID is missing for {display_intent} request."

        elif intent == "account" and not customer_id:
            requires_clarify = True
            selected_action = "clarify"
            rationale = "Policy coverage is sufficient, but customer ID is missing for account request."
        elif intent == "unknown" or (not policy_supported and policy_ctx and policy_ctx.requires_policy_review):
            requires_clarify = True
            selected_agent = "unknown"
            selected_action = "clarify"
            rationale = "Policy coverage is insufficient for request; clarification is required."
        elif order_id and not order_obj:
            selected_action = "check_eligibility"
            rationale = f"Order {order_id} not found in database; verification required."
        else:
            is_refund = intent == "refund" or "refund" in state.user_request.lower()
            if is_refund:
                selected_agent = "payment"
                selected_action = "check_refund_eligibility"
                if order_status == "CANCELLED" and payment_status in ("PAID", "SUCCESS"):
                    rationale = f"Refund policy matched and order {order_id} is CANCELLED with {payment_status} payment status."

                elif payment_status == "REFUNDED":
                    rationale = f"Refund policy matched; order {order_id} has already been refunded."
                else:
                    rationale = f"Refund policy matched, but order {order_id} status is {order_status or 'UNKNOWN'}."
            elif intent == "return":
                selected_agent = "return"
                selected_action = "check_return_eligibility"
                if order_status == "DELIVERED":
                    rationale = f"Return policy matched and order {order_id} is DELIVERED."
                else:
                    rationale = f"Return policy matched, but order {order_id} is not delivered (status: {order_status or 'UNKNOWN'})."
            elif intent == "replacement":
                selected_agent = "replacement"
                selected_action = "check_replacement_eligibility"
                if order_status == "DELIVERED":
                    rationale = f"Replacement policy matched and order {order_id} is DELIVERED."
                else:
                    rationale = f"Replacement policy matched, but order {order_id} is not delivered (status: {order_status or 'UNKNOWN'})."
            else:
                selected_action = "lookup"
                rationale = f"{intent.capitalize()} policy matched for order {order_id or 'general inquiry'}."


        return AgentDecision(
            intent=intent,
            goal=goal,
            selected_agent=selected_agent,
            selected_action=selected_action,
            rationale=rationale,
            policy_supported=policy_supported,
            policy_confidence=policy_confidence,
            transactional_check_required=bool(order_id),
            requires_clarification=requires_clarify,
            requires_escalation=requires_escalate,
        )

    def run(self, user_message: str, db: Session | None = None) -> dict[str, Any]:
        """
        Execute full agentic workflow for user request.
        """
        active_db = db or self.db
        local_session = False
        if active_db is None:
            active_db = SessionLocal()
            local_session = True

        try:
            # 1. State Initialization
            state = AgentState(user_request=user_message)
            state.status = OrchestrationStatus.PLANNING

            # 2. Goal Understanding & Entity Extraction
            intents = _detect_intents(user_message)
            state.intents = intents
            state.intent = intents[0] if intents else "unknown"
            state.order_id = _extract_order_id(user_message)
            state.customer_id = _extract_customer_id(user_message)
            state.product_id = _extract_product_id(user_message)
            state.reason = _extract_reason(user_message)

            # 3. Policy Retrieval Stage
            state.status = OrchestrationStatus.POLICY_RETRIEVAL
            policy_ctx = PolicyRetriever.retrieve_policy(user_message)
            state.policy_context = policy_ctx

            # 4. Agent Decision Stage
            state.status = OrchestrationStatus.DECIDING
            decision = self._make_decision(state, active_db)
            state.decision = decision

            if decision.requires_clarification:
                state.status = OrchestrationStatus.NEEDS_CLARIFICATION
                if state.intent in ("refund", "return", "replacement", "order", "payment", "delivery") and not state.order_id:
                    state.final_response = f"Please provide your order ID (for example, ORD005) so I can look into your {state.intent} request."
                elif state.intent == "account" and not state.customer_id:
                    state.final_response = "Please provide your customer ID (for example, C101) so I can look up your account."
                else:
                    state.final_response = (
                        "I can currently help with orders, payments, deliveries, "
                        "returns, replacements, and account queries. Could you please provide more details "
                        "about your issue?"
                    )
                return self._build_result(state)

            if decision.requires_escalation:
                self._escalate(state, active_db, decision.rationale)
                return self._build_result(state)

            # 5. Plan Creation
            self._create_plan(state)

            # 6. Execute Plan
            self._execute_plan(state, active_db)

            # 7. Safety check & Escalation fallback
            if state.status not in (
                OrchestrationStatus.RESOLVED,
                OrchestrationStatus.NEEDS_CLARIFICATION,
                OrchestrationStatus.ESCALATED,
            ):
                self._escalate(state, active_db, "Workflow completed without clean resolution.")

            return self._build_result(state)

        finally:
            if local_session and active_db:
                active_db.close()


    def _create_plan(self, state: AgentState) -> None:
        """Generate structured action plan based on state intent(s)."""
        plan: list[ActionItem] = []

        primary = state.intent
        if primary in ("refund", "return", "replacement"):
            intents_to_plan = [primary]
        else:
            intents_to_plan = state.intents if state.intents else ([primary] if primary else [])

        for intent in intents_to_plan:
            if intent == "refund":
                plan.extend([
                    ActionItem(agent="payment", action="check_refund_eligibility", description="Check refund eligibility"),
                    ActionItem(agent="payment", action="process_refund", description="Process refund in DB"),
                    ActionItem(agent="payment", action="verify_refund", description="Verify refund state in PostgreSQL"),
                ])
            elif intent == "return":
                plan.extend([
                    ActionItem(agent="return", action="check_return_eligibility", description="Check return eligibility"),
                    ActionItem(agent="return", action="create_return_request", description="Create return request in DB"),
                    ActionItem(agent="return", action="verify_return", description="Verify return record in PostgreSQL"),
                ])
            elif intent == "replacement":
                plan.extend([
                    ActionItem(agent="replacement", action="check_replacement_eligibility", description="Check replacement eligibility"),
                    ActionItem(agent="replacement", action="create_replacement_request", description="Create replacement request in DB"),
                    ActionItem(agent="replacement", action="verify_replacement", description="Verify replacement record in PostgreSQL"),
                ])
            elif intent in ("order", "payment", "delivery", "account"):
                plan.append(
                    ActionItem(agent=intent, action="lookup", description=f"Execute {intent} agent lookup")
                )

        if not plan:
            plan.append(
                ActionItem(agent="unknown", action="general_support", description="Handle general support request")
            )

        state.plan = plan

    def _execute_plan(self, state: AgentState, db: Session) -> None:
        """Execute plan items step-by-step with observation and verification."""
        responses: list[str] = []

        for item in state.plan:
            if state.status == OrchestrationStatus.RESOLVED:
                break

            state.increment_attempt()
            if state.status == OrchestrationStatus.ESCALATED:
                break

            state.current_agent = item.agent
            state.current_action = item.action
            if state.status != OrchestrationStatus.RESOLVED:
                state.status = OrchestrationStatus.EXECUTING

            # Execute specific domain action
            if item.agent == "payment" and (item.action.startswith("check_refund") or item.action == "process_refund" or item.action == "verify_refund"):
                self._execute_refund_step(item, state, db)
            elif item.agent == "return" and ("return" in item.action):
                self._execute_return_step(item, state, db)
            elif item.agent == "replacement" and ("replacement" in item.action):
                self._execute_replacement_step(item, state, db)
            elif item.agent in ("order", "payment", "delivery", "account"):
                self._execute_specialist_step(item, state, db)
            else:
                self._execute_unknown_step(item, state, db)

            item.completed = True
            state.completed_actions.append(
                {
                    "agent": item.agent,
                    "action": item.action,
                    "description": item.description,
                    "status": state.status.value,
                }
            )

            if state.final_response and state.final_response not in responses:
                responses.append(state.final_response)

            # Terminal states break execution loop early
            if state.status in (
                OrchestrationStatus.RESOLVED,
                OrchestrationStatus.NEEDS_CLARIFICATION,
                OrchestrationStatus.ESCALATED,
            ):
                break

        if responses:
            state.final_response = "\n\n".join(responses)


    def _execute_refund_step(self, item: ActionItem, state: AgentState, db: Session) -> None:
        """Handle refund workflow steps."""
        if item.action == "check_refund_eligibility":
            res = check_refund_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if not res.get("success") and "not found" in res.get("message", "").lower():
                self._escalate(state, db, res.get("message", f"Order '{state.order_id}' not found."))
                return

            if not res.get("eligible"):
                if res.get("reason") == "Refund has already been processed for this order." or res.get("payment_status") == "REFUNDED":
                    v_res = verify_refund(state.order_id, db)
                    state.verification_result = v_res
                    state.status = OrchestrationStatus.RESOLVED
                    state.final_response = f"Refund for order '{state.order_id}' has already been processed."
                else:
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("reason", "Order is not eligible for refund."))

        elif item.action == "process_refund":
            res = process_refund(state.order_id, db, reason=state.reason or "Customer requested refund")
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if res.get("already_refunded"):
                v_res = verify_refund(state.order_id, db)
                state.verification_result = v_res
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = res.get("message", f"Refund for order '{state.order_id}' has already been processed.")
            elif not res.get("success") or not res.get("processed"):
                self._escalate(state, db, res.get("message", "Refund processing failed."))

        elif item.action == "verify_refund":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_refund(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") == "COMPLETED":
                state.status = OrchestrationStatus.RESOLVED
                amount_str = f"INR {v_res.get('amount')}" if v_res.get("amount") else "amount"
                state.final_response = (
                    f"Refund of {amount_str} for order '{state.order_id}' processed successfully. "
                    f"Refund ID: {v_res.get('refund_id')}."
                )
            else:
                self._escalate(state, db, f"Refund verification failed for order '{state.order_id}'.")

    def _execute_return_step(self, item: ActionItem, state: AgentState, db: Session) -> None:
        """Handle return workflow steps."""
        if item.action == "check_return_eligibility":
            res = check_return_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if not res.get("success") or not res.get("eligible"):
                state.status = OrchestrationStatus.REPLANNING
                self._escalate(state, db, res.get("reason", "Order is not eligible for a product return."))

        elif item.action == "create_return_request":
            res = create_return_request(
                order_id=state.order_id,
                db=db,
                customer_id=state.customer_id,
                reason=state.reason or "Customer requested product return",
            )
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if res.get("already_exists"):
                v_res = verify_return(state.order_id, db)
                state.verification_result = v_res
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = res.get("message", f"A return request already exists for order '{state.order_id}'.")
            elif not res.get("success"):
                self._escalate(state, db, res.get("message", "Return creation failed."))

        elif item.action == "verify_return":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_return(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") in ("REQUESTED", "APPROVED", "COMPLETED"):
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = (
                    f"Your return request for order '{state.order_id}' has been successfully registered. "
                    f"Return ID: {v_res.get('return_id')}, Status: {v_res.get('status')}."
                )
            else:
                self._escalate(state, db, f"Return verification failed for order '{state.order_id}'.")

    def _execute_replacement_step(self, item: ActionItem, state: AgentState, db: Session) -> None:
        """Handle replacement workflow steps."""
        if item.action == "check_replacement_eligibility":
            res = check_replacement_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if not res.get("success") or not res.get("eligible"):
                state.status = OrchestrationStatus.REPLANNING
                self._escalate(state, db, res.get("reason", "Order is not eligible for product replacement."))

        elif item.action == "create_replacement_request":
            res = create_replacement_request(
                order_id=state.order_id,
                db=db,
                customer_id=state.customer_id,
                product_id=state.product_id,
                reason=state.reason or "Customer requested product replacement",
            )
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING

            if res.get("already_exists"):
                v_res = verify_replacement(state.order_id, db)
                state.verification_result = v_res
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = res.get("message", f"A replacement request already exists for order '{state.order_id}'.")
            elif not res.get("success"):
                self._escalate(state, db, res.get("message", "Replacement creation failed."))

        elif item.action == "verify_replacement":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_replacement(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") in ("REQUESTED", "APPROVED", "COMPLETED"):
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = (
                    f"Your replacement request for order '{state.order_id}' has been successfully registered. "
                    f"Replacement ID: {v_res.get('replacement_id')}, Status: {v_res.get('status')}."
                )
            else:
                self._escalate(state, db, f"Replacement verification failed for order '{state.order_id}'.")

    def _execute_specialist_step(self, item: ActionItem, state: AgentState, db: Session) -> None:
        """Delegate to domain specialist agents (order, payment, delivery, account)."""
        agent_name = item.agent
        res: dict[str, Any] = {}

        if agent_name == "order":
            res = run_order(state.user_request, db)
        elif agent_name == "payment":
            res = run_payment(state.user_request, db)
        elif agent_name == "delivery":
            res = run_delivery(state.user_request, db)
        elif agent_name == "account":
            res = run_account(state.user_request, db)

        state.tool_result = res.get("tool_result")
        response = res.get("response", "")

        if "need an order id" in response.lower() or "please provide" in response.lower():
            state.status = OrchestrationStatus.NEEDS_CLARIFICATION
            state.final_response = response
        elif "not found" in response.lower() or "unable" in response.lower():
            self._escalate(state, db, response)
        else:
            state.status = OrchestrationStatus.RESOLVED
            state.final_response = response

    def _execute_unknown_step(self, item: ActionItem, state: AgentState, db: Session) -> None:
        """Handle unrecognized intents."""
        state.status = OrchestrationStatus.NEEDS_CLARIFICATION
        state.final_response = (
            "I can currently help with orders, payments, deliveries, "
            "and account queries. Could you please provide more details "
            "about your issue?"
        )

    def _escalate(self, state: AgentState, db: Session, reason: str) -> None:
        """Escalate unresolved request by creating a support ticket."""
        state.status = OrchestrationStatus.ESCALATED
        state.escalation_reason = reason

        ticket = create_support_ticket(
            db=db,
            issue=f"[{state.intent.upper()} ESCALATION] {reason} | Request: '{state.user_request}'",
            customer_id=state.customer_id,
            order_id=state.order_id,
        )

        state.ticket_id = ticket.get("ticket_id")
        state.final_response = (
            f"I was unable to resolve your request automatically: {reason}\n\n"
            f"I have created a support ticket ({state.ticket_id}) for our team to assist you further."
        )

    def _build_result(self, state: AgentState) -> dict[str, Any]:
        """Format structured orchestration result."""
        return {
            "success": state.status == OrchestrationStatus.RESOLVED or state.status == OrchestrationStatus.NEEDS_CLARIFICATION,
            "status": state.status.value,
            "intent": state.intent,
            "order_id": state.order_id,
            "completed_actions": [a["action"] for a in state.completed_actions],
            "verification": state.verification_result or {"verified": state.status == OrchestrationStatus.RESOLVED},
            "policy_context": state.policy_context.model_dump() if state.policy_context else None,
            "decision": state.decision.model_dump() if state.decision else None,
            "final_response": state.final_response,
            "ticket_id": state.ticket_id,
            "escalation_reason": state.escalation_reason,
            "state": state.to_dict(),
        }


