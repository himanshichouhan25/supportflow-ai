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
from agents.state import (
    AgentState,
    ActionItem,
    AgentDecision,
    EscalationContext,
    EscalationCategory,
    TicketPriority,
    ConversationContext,
    SessionManager,
    OrchestrationStatus,
    StepStatus,
    WorkflowStep,
    WorkflowPlan,
)

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
_FOLLOWUP_PRONOUNS = {
    "it",
    "that",
    "this",
    "that order",
    "this order",
    "the same order",
    "same order",
    "same product",
    "that product",
    "that payment",
    "that item",
    "the item",
    "this item",
}


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


def _determine_escalation_category(
    reason: str,
    intent: str,
    tool_result: dict[str, Any] | None = None,
    verification_result: dict[str, Any] | None = None,
    policy_context: Any = None,
) -> EscalationCategory:
    lower_reason = reason.lower()

    if verification_result and not verification_result.get("success"):
        return EscalationCategory.VERIFICATION_FAILED

    if tool_result and tool_result.get("eligible") is False:
        return EscalationCategory.INELIGIBLE_TRANSACTION

    if "not eligible" in lower_reason or "ineligible" in lower_reason or "only eligible" in lower_reason or "not delivered" in lower_reason or "cannot be" in lower_reason:
        return EscalationCategory.INELIGIBLE_TRANSACTION

    if "missing" in lower_reason or "provide" in lower_reason or "order id is required" in lower_reason:
        return EscalationCategory.MISSING_REQUIRED_INFORMATION

    if "insufficient" in lower_reason or "policy review" in lower_reason or (policy_context and policy_context.requires_policy_review):
        return EscalationCategory.POLICY_COVERAGE_INSUFFICIENT

    if tool_result and not tool_result.get("success"):
        return EscalationCategory.ACTION_FAILED

    if "failed" in lower_reason or "error" in lower_reason:
        return EscalationCategory.ACTION_FAILED

    return EscalationCategory.MANUAL_REVIEW_REQUIRED



def _determine_escalation_priority(
    category: EscalationCategory,
    intent: str,
    verification_failed: bool = False,
) -> TicketPriority:
    if verification_failed or category == EscalationCategory.VERIFICATION_FAILED:
        return TicketPriority.HIGH

    if intent in ("refund", "payment") or category == EscalationCategory.ACTION_FAILED:
        return TicketPriority.HIGH

    if intent in ("return", "replacement", "delivery") or category == EscalationCategory.INELIGIBLE_TRANSACTION:
        return TicketPriority.MEDIUM

    if category in (EscalationCategory.MISSING_REQUIRED_INFORMATION, EscalationCategory.POLICY_COVERAGE_INSUFFICIENT):
        return TicketPriority.LOW

    return TicketPriority.MEDIUM


def _determine_recommended_next_step(category: EscalationCategory, intent: str, reason: str) -> str:
    if category == EscalationCategory.INELIGIBLE_TRANSACTION:
        return f"Inspect order status for {intent.upper()} request and evaluate manual policy exception."
    if category == EscalationCategory.POLICY_COVERAGE_INSUFFICIENT:
        return "Review customer inquiry against policy knowledge base and update guidelines."
    if category == EscalationCategory.MISSING_REQUIRED_INFORMATION:
        return "Contact customer to verify missing order ID or account credentials."
    if category == EscalationCategory.ACTION_FAILED:
        return f"Investigate system transaction failure for {intent.upper()} action."
    if category == EscalationCategory.VERIFICATION_FAILED:
        return f"Manually verify database records and confirm {intent.upper()} state."
    return "Human support agent review required."


# ---------------------------------------------------------------------------
# Orchestrator Class
# ---------------------------------------------------------------------------

class Orchestrator:
    ...

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

    def run(self, user_message: str, db: Session | None = None, session_id: str = "default_session") -> dict[str, Any]:
        """
        Execute full agentic workflow for user request.
        """
        active_db = db or self.db
        local_session = False
        if active_db is None:
            active_db = SessionLocal()
            local_session = True

        try:
            # 1. Session Context Retrieval & State Initialization
            ctx = SessionManager.get_context(session_id)
            state = AgentState(user_request=user_message, session_id=session_id)
            state.conversation_context = ctx
            state.status = OrchestrationStatus.PLANNING

            # 2. Goal Understanding & Entity Extraction
            intents = _detect_intents(user_message)
            state.intents = intents
            state.intent = intents[0] if intents else "unknown"
            state.order_id = _extract_order_id(user_message)
            state.customer_id = _extract_customer_id(user_message) or ctx.customer_id
            state.product_id = _extract_product_id(user_message) or ctx.current_product_id
            state.reason = _extract_reason(user_message)

            # Follow-up Anaphora & Contextual Resolution
            lower_msg = user_message.lower()
            has_followup_ref = any(p in lower_msg for p in _FOLLOWUP_PRONOUNS)

            # Explicit entity in current prompt overrides older context
            if state.order_id:
                ctx.add_order_id(state.order_id)
            elif has_followup_ref or state.intent in ("refund", "return", "replacement", "order", "payment", "delivery"):
                if len(ctx.recent_order_ids) > 1 and has_followup_ref:
                    # Ambiguous reference across multiple recent orders -> NEEDS_CLARIFICATION
                    state.status = OrchestrationStatus.NEEDS_CLARIFICATION
                    o1, o2 = ctx.recent_order_ids[0], ctx.recent_order_ids[1]
                    intent_label = "return" if "return" in lower_msg else (state.intent if state.intent != "unknown" else "resolve")
                    state.final_response = f"Which order would you like to {intent_label}, {o1} or {o2}?"
                    state.conversation_context = SessionManager.update_context(session_id, state)
                    return self._build_result(state)
                elif ctx.current_order_id or len(ctx.recent_order_ids) == 1:
                    state.order_id = ctx.current_order_id or ctx.recent_order_ids[0]

            # Contextual Intent Inheritance if prompt has pronoun without explicit intent
            if state.intent == "unknown" and ctx.current_intent:
                state.intent = ctx.current_intent

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
                state.conversation_context = SessionManager.update_context(session_id, state)
                return self._build_result(state)

            if decision.requires_escalation:
                self._escalate(state, active_db, decision.rationale)
                state.conversation_context = SessionManager.update_context(session_id, state)
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

            state.conversation_context = SessionManager.update_context(session_id, state)
            return self._build_result(state)

        finally:
            if local_session and active_db:
                active_db.close()



    def _create_plan(self, state: AgentState) -> None:
        """Generate structured multi-step WorkflowPlan and action items based on state intent(s)."""
        wf_steps: list[WorkflowStep] = []

        # Step 1: Policy Retrieval
        step_1 = WorkflowStep(
            step_id="step_1",
            action="policy_retrieval",
            agent="orchestrator",
            description="Retrieve domain support policy context",
            depends_on=[],
        )
        wf_steps.append(step_1)

        # Step 2: Order Check
        step_2 = WorkflowStep(
            step_id="step_2",
            action="check_order",
            agent="order",
            description="Verify order status and details in PostgreSQL",
            depends_on=["step_1"],
        )
        wf_steps.append(step_2)

        msg_lower = state.user_request.lower()
        primary = state.intent
        if "refund" in msg_lower:
            primary = "refund"

        step_idx = 3

        if primary == "refund":
            step_elig = WorkflowStep(
                step_id=f"step_{step_idx}",
                action="check_refund_eligibility",
                agent="payment",
                description="Check refund eligibility in PostgreSQL",
                depends_on=["step_2"],
            )
            wf_steps.append(step_elig)

            step_create = WorkflowStep(
                step_id=f"step_{step_idx+1}",
                action="process_refund",
                agent="payment",
                description="Process refund in DB",
                depends_on=[f"step_{step_idx}"],
                verification_required=True,
            )
            wf_steps.append(step_create)

            step_verify = WorkflowStep(
                step_id=f"step_{step_idx+2}",
                action="verify_refund",
                agent="payment",
                description="Verify refund state in PostgreSQL",
                depends_on=[f"step_{step_idx+1}"],
            )
            wf_steps.append(step_verify)

            if "status" in msg_lower or "refund status" in msg_lower or "tell me" in msg_lower:
                step_status = WorkflowStep(
                    step_id=f"step_{step_idx+3}",
                    action="get_refund_status",
                    agent="payment",
                    description="Query refund transaction status",
                    depends_on=[f"step_{step_idx+2}"],
                )
                wf_steps.append(step_status)

        elif primary == "return":
            step_elig = WorkflowStep(
                step_id=f"step_{step_idx}",
                action="check_return_eligibility",
                agent="return",
                description="Check return eligibility in PostgreSQL",
                depends_on=["step_2"],
            )
            wf_steps.append(step_elig)

            step_create = WorkflowStep(
                step_id=f"step_{step_idx+1}",
                action="create_return_request",
                agent="return",
                description="Create return request in DB",
                depends_on=[f"step_{step_idx}"],
                verification_required=True,
            )
            wf_steps.append(step_create)

            step_verify = WorkflowStep(
                step_id=f"step_{step_idx+2}",
                action="verify_return",
                agent="return",
                description="Verify return record in PostgreSQL",
                depends_on=[f"step_{step_idx+1}"],
            )
            wf_steps.append(step_verify)

            if "deliver" in msg_lower or "delivery" in msg_lower or "status" in msg_lower or "tell me" in msg_lower:
                step_status = WorkflowStep(
                    step_id=f"step_{step_idx+3}",
                    action="get_delivery_status",
                    agent="delivery",
                    description="Check delivery state of order",
                    depends_on=["step_2"],
                )
                wf_steps.append(step_status)

        elif primary == "replacement":
            step_elig = WorkflowStep(
                step_id=f"step_{step_idx}",
                action="check_replacement_eligibility",
                agent="replacement",
                description="Check replacement eligibility in PostgreSQL",
                depends_on=["step_2"],
            )
            wf_steps.append(step_elig)

            step_create = WorkflowStep(
                step_id=f"step_{step_idx+1}",
                action="create_replacement_request",
                agent="replacement",
                description="Create replacement request in DB",
                depends_on=[f"step_{step_idx}"],
                verification_required=True,
            )
            wf_steps.append(step_create)

            step_verify = WorkflowStep(
                step_id=f"step_{step_idx+2}",
                action="verify_replacement",
                agent="replacement",
                description="Verify replacement record in PostgreSQL",
                depends_on=[f"step_{step_idx+1}"],
            )
            wf_steps.append(step_verify)

            if "status" in msg_lower or "delivery" in msg_lower or "arrive" in msg_lower or "tell me" in msg_lower:
                step_status = WorkflowStep(
                    step_id=f"step_{step_idx+3}",
                    action="get_replacement_status",
                    agent="replacement",
                    description="Retrieve replacement and delivery status",
                    depends_on=[f"step_{step_idx+2}"],
                )
                wf_steps.append(step_status)

        elif primary in ("order", "payment", "delivery", "account"):
            step_lookup = WorkflowStep(
                step_id=f"step_{step_idx}",
                action="lookup",
                agent=primary,
                description=f"Execute {primary} agent lookup",
                depends_on=["step_2"],
            )
            wf_steps.append(step_lookup)

        goal_str = f"Resolve {primary} support request for order '{state.order_id or 'unknown'}'"
        plan = WorkflowPlan(goal=goal_str, steps=wf_steps, max_steps=8, max_replans=1)
        state.workflow_plan = plan

        state.plan = [
            ActionItem(agent=s.agent, action=s.action, description=s.description)
            for s in wf_steps
            if s.action not in ("policy_retrieval", "check_order")
        ]
        if not state.plan:
            state.plan = [ActionItem(agent=primary or "unknown", action="lookup", description="Execute support query")]

    def _execute_plan(self, state: AgentState, db: Session) -> None:
        """Execute plan items step-by-step with dependency checks, observation, and verification."""
        if not state.workflow_plan:
            self._create_plan(state)

        plan = state.workflow_plan
        responses: list[str] = []
        executed_state_changing_actions: set[str] = set()

        for step in plan.steps:
            if state.status in (OrchestrationStatus.ESCALATED, OrchestrationStatus.NEEDS_CLARIFICATION):
                break

            # Dependency validation
            any_dep_failed = any(dep_id in plan.failed_steps for dep_id in step.depends_on)
            if any_dep_failed:
                step.status = StepStatus.SKIPPED
                continue

            # Duplicate action protection for state-changing actions
            if step.action in ("process_refund", "create_return_request", "create_replacement_request"):
                if step.action in executed_state_changing_actions:
                    step.status = StepStatus.SKIPPED
                    continue
                executed_state_changing_actions.add(step.action)

            step.status = StepStatus.RUNNING
            state.current_agent = step.agent
            state.current_action = step.action
            state.increment_attempt()

            if state.status not in (OrchestrationStatus.RESOLVED, OrchestrationStatus.ESCALATED):
                state.status = OrchestrationStatus.EXECUTING

            # Step Execution Logic
            if step.action == "policy_retrieval":
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)

            elif step.action == "check_order":
                if state.order_id:
                    ord_obj = db.query(Order).filter_by(order_id=state.order_id).first()
                    if ord_obj:
                        step.status = StepStatus.COMPLETED
                        plan.completed_steps.append(step.step_id)
                    else:
                        step.status = StepStatus.FAILED
                        plan.failed_steps.append(step.step_id)
                        self._escalate(state, db, f"Order '{state.order_id}' was not found in the database.")
                        break
                else:
                    step.status = StepStatus.COMPLETED
                    plan.completed_steps.append(step.step_id)

            elif step.agent == "payment" and ("refund" in step.action or step.action == "process_refund"):
                self._execute_refund_step_wf(step, state, db, plan)
            elif step.agent == "return" and ("return" in step.action):
                self._execute_return_step_wf(step, state, db, plan)
            elif step.agent == "replacement" and ("replacement" in step.action):
                self._execute_replacement_step_wf(step, state, db, plan)
            elif step.agent == "delivery" and step.action == "get_delivery_status":
                del_res = run_delivery(state.user_request, db)
                resp = del_res.get("response", "")
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
                if resp and resp not in responses:
                    responses.append(resp)
            elif step.agent in ("order", "payment", "delivery", "account"):
                self._execute_specialist_step(ActionItem(agent=step.agent, action=step.action, description=step.description), state, db)
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                self._execute_unknown_step(ActionItem(agent=step.agent, action=step.action, description=step.description), state, db)

            state.completed_actions.append({
                "agent": step.agent,
                "action": step.action,
                "description": step.description,
                "status": step.status.value if isinstance(step.status, StepStatus) else str(step.status),
            })
            state.workflow_trace = plan.get_workflow_trace()

            if state.final_response and state.final_response not in responses:
                responses.append(state.final_response)

            if state.status in (OrchestrationStatus.NEEDS_CLARIFICATION, OrchestrationStatus.ESCALATED):
                break

        if responses:
            state.final_response = "\n\n".join(responses)

    def _execute_refund_step_wf(self, step: WorkflowStep, state: AgentState, db: Session, plan: WorkflowPlan) -> None:
        """Handle refund workflow step execution with WorkflowPlan tracking."""
        if step.action == "check_refund_eligibility":
            res = check_refund_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if not res.get("success") and "not found" in res.get("message", "").lower():
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                self._escalate(state, db, res.get("message", f"Order '{state.order_id}' not found."))
                return

            if res.get("eligible") or res.get("already_refunded") or res.get("payment_status") == "REFUNDED":
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("reason", "Order is not eligible for refund."))

        elif step.action == "process_refund":
            res = process_refund(state.order_id, db, reason=state.reason or "Customer requested refund")
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if res.get("success") or res.get("already_refunded") or res.get("processed"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("message", "Refund processing failed."))

        elif step.action == "verify_refund":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_refund(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") == "COMPLETED":
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
                state.status = OrchestrationStatus.RESOLVED
                amount_str = f"INR {v_res.get('amount')}" if v_res.get("amount") else "amount"
                state.final_response = f"Refund of {amount_str} for order '{state.order_id}' processed successfully. Refund ID: {v_res.get('refund_id')}."
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                self._escalate(state, db, f"Refund verification failed for order '{state.order_id}'.")

        elif step.action == "get_refund_status":
            v_res = verify_refund(state.order_id, db)
            if v_res.get("success"):
                state.final_response = f"Refund of INR {v_res.get('amount')} for order '{state.order_id}' processed successfully. Refund ID: {v_res.get('refund_id')}."
            step.status = StepStatus.COMPLETED
            plan.completed_steps.append(step.step_id)

    def _execute_return_step_wf(self, step: WorkflowStep, state: AgentState, db: Session, plan: WorkflowPlan) -> None:
        """Handle return workflow step execution with WorkflowPlan tracking."""
        if step.action == "check_return_eligibility":
            res = check_return_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if res.get("eligible"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("reason", "Order is not eligible for return."))

        elif step.action == "create_return_request":
            res = create_return_request(
                order_id=state.order_id,
                db=db,
                customer_id=state.customer_id,
                reason=state.reason or "Customer requested return",
            )
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if res.get("success") or res.get("already_exists"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("message", "Return creation failed."))

        elif step.action == "verify_return":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_return(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") in ("REQUESTED", "APPROVED", "COMPLETED"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = f"Your return request for order '{state.order_id}' has been successfully registered. Return ID: {v_res.get('return_id')}, Status: {v_res.get('status')}."
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                self._escalate(state, db, f"Return verification failed for order '{state.order_id}'.")

    def _execute_replacement_step_wf(self, step: WorkflowStep, state: AgentState, db: Session, plan: WorkflowPlan) -> None:
        """Handle replacement workflow step execution with WorkflowPlan tracking."""
        if step.action == "check_replacement_eligibility":
            res = check_replacement_eligibility(state.order_id, db)
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if res.get("eligible"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("reason", "Order is not eligible for product replacement."))

        elif step.action == "create_replacement_request":
            res = create_replacement_request(
                order_id=state.order_id,
                db=db,
                customer_id=state.customer_id,
                product_id=state.product_id,
                reason=state.reason or "Customer requested product replacement",
            )
            state.tool_result = res
            state.status = OrchestrationStatus.OBSERVING
            if res.get("success") or res.get("already_exists"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                if plan.can_replan():
                    plan.replans += 1
                    state.status = OrchestrationStatus.REPLANNING
                    self._escalate(state, db, res.get("message", "Replacement creation failed."))

        elif step.action == "verify_replacement":
            state.status = OrchestrationStatus.VERIFYING
            v_res = verify_replacement(state.order_id, db)
            state.verification_result = v_res
            if v_res.get("success") and v_res.get("status") in ("REQUESTED", "APPROVED", "COMPLETED"):
                step.status = StepStatus.COMPLETED
                plan.completed_steps.append(step.step_id)
                state.status = OrchestrationStatus.RESOLVED
                state.final_response = f"Your replacement request for order '{state.order_id}' has been successfully registered. Replacement ID: {v_res.get('replacement_id')}, Status: {v_res.get('status')}."
            else:
                step.status = StepStatus.FAILED
                plan.failed_steps.append(step.step_id)
                self._escalate(state, db, f"Replacement verification failed for order '{state.order_id}'.")

        elif step.action == "get_replacement_status":
            v_res = verify_replacement(state.order_id, db)
            if v_res.get("success"):
                state.final_response = f"Your replacement request for order '{state.order_id}' has been created successfully as {v_res.get('replacement_id')}. The request is currently in {v_res.get('status')} status."
            step.status = StepStatus.COMPLETED
            plan.completed_steps.append(step.step_id)

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
        """Escalate unresolved request by creating a structured support ticket."""
        state.status = OrchestrationStatus.ESCALATED
        state.escalation_reason = reason

        category = _determine_escalation_category(
            reason=reason,
            intent=state.intent,
            tool_result=state.tool_result,
            verification_result=state.verification_result,
            policy_context=state.policy_context,
        )
        verification_failed = bool(state.verification_result and not state.verification_result.get("success"))
        priority = _determine_escalation_priority(category, state.intent, verification_failed)
        next_step = _determine_recommended_next_step(category, state.intent, reason)

        attempted_raw = ["policy_retrieval", "agent_decision"] + [a["action"] for a in state.completed_actions]
        attempted_actions: list[str] = []
        for act in attempted_raw:
            if act not in attempted_actions:
                attempted_actions.append(act)

        policy_id = state.policy_context.top_policy.category if (state.policy_context and state.policy_context.top_policy) else None
        policy_confidence = state.policy_context.retrieval_confidence if state.policy_context else 0.0
        policy_supported = state.decision.policy_supported if state.decision else False

        esc_ctx = EscalationContext(
            reason=reason,
            category=category,
            priority=priority,
            customer_id=state.customer_id,
            order_id=state.order_id,
            intent=state.intent,
            selected_agent=state.decision.selected_agent if state.decision else state.intent,
            selected_action=state.decision.selected_action if state.decision else None,
            policy_id=policy_id,
            policy_confidence=policy_confidence,
            policy_supported=policy_supported,
            attempted_actions=attempted_actions,
            last_action_result=state.tool_result,
            verification_result=state.verification_result,
            recommended_next_step=next_step,
        )
        state.escalation_context = esc_ctx

        issue_str = (
            f"[{category.value}] [{priority.value}] {reason} | "
            f"Intent: {state.intent} | Order: {state.order_id or 'N/A'} | "
            f"Agent: {esc_ctx.selected_agent} | Action: {esc_ctx.selected_action} | "
            f"Policy: {esc_ctx.policy_id or 'None'} | Attempted: {attempted_actions} | "
            f"Next Step: {next_step}"
        )

        ticket = create_support_ticket(
            db=db,
            issue=issue_str,
            customer_id=state.customer_id,
            order_id=state.order_id,
        )

        state.ticket_id = ticket.get("ticket_id")
        state.final_response = (
            f"I was unable to resolve your request automatically: {reason}\n\n"
            f"I have created a support ticket ({state.ticket_id}, Priority: {priority.value}) for our team to assist you further."
        )

    def _build_result(self, state: AgentState) -> dict[str, Any]:
        """Format structured orchestration result."""
        wf_trace = state.workflow_trace if state.workflow_trace else (state.workflow_plan.get_workflow_trace() if state.workflow_plan else [])
        return {
            "success": state.status == OrchestrationStatus.RESOLVED or state.status == OrchestrationStatus.NEEDS_CLARIFICATION,
            "status": state.status.value if isinstance(state.status, OrchestrationStatus) else str(state.status),
            "intent": state.intent,
            "order_id": state.order_id,
            "session_id": state.session_id,
            "conversation_context": state.conversation_context.model_dump() if state.conversation_context else None,
            "workflow_plan": state.workflow_plan.model_dump() if state.workflow_plan else None,
            "workflow_trace": wf_trace,
            "completed_actions": [a["action"] for a in state.completed_actions],
            "verification": state.verification_result or {"verified": state.status == OrchestrationStatus.RESOLVED},
            "policy_context": state.policy_context.model_dump() if state.policy_context else None,
            "decision": state.decision.model_dump() if state.decision else None,
            "escalation_context": state.escalation_context.model_dump() if state.escalation_context else None,
            "final_response": state.final_response,
            "ticket_id": state.ticket_id,
            "escalation_reason": state.escalation_reason,
            "state": state.to_dict(),
        }



