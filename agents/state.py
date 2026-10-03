"""
agents/state.py — Typed agent state and status representation for SupportFlow AI.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from knowledge.models import PolicyContext


class OrchestrationStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    POLICY_RETRIEVAL = "POLICY_RETRIEVAL"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REPLANNING = "REPLANNING"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class ActionItem(BaseModel):
    agent: str
    action: str
    description: str | None = None
    completed: bool = False


class EscalationCategory(str, Enum):
    INELIGIBLE_TRANSACTION = "INELIGIBLE_TRANSACTION"
    POLICY_COVERAGE_INSUFFICIENT = "POLICY_COVERAGE_INSUFFICIENT"
    MISSING_REQUIRED_INFORMATION = "MISSING_REQUIRED_INFORMATION"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    DUPLICATE_OR_ALREADY_RESOLVED = "DUPLICATE_OR_ALREADY_RESOLVED"


class TicketPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AgentDecision(BaseModel):
    intent: str
    goal: str
    selected_agent: str
    selected_action: str
    rationale: str
    policy_supported: bool = True
    policy_confidence: float = 1.0
    transactional_check_required: bool = True
    requires_clarification: bool = False
    requires_escalation: bool = False


class EscalationContext(BaseModel):
    reason: str
    category: EscalationCategory = EscalationCategory.MANUAL_REVIEW_REQUIRED
    priority: TicketPriority = TicketPriority.MEDIUM
    customer_id: str | None = None
    order_id: str | None = None
    intent: str = "unknown"
    selected_agent: str | None = None
    selected_action: str | None = None
    policy_id: str | None = None
    policy_confidence: float = 0.0
    policy_supported: bool = False
    attempted_actions: list[str] = Field(default_factory=list)
    last_action_result: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    recommended_next_step: str = "Human support agent review required."


class ConversationContext(BaseModel):
    session_id: str = "default_session"
    customer_id: str | None = None
    current_order_id: str | None = None
    current_intent: str | None = None
    current_product_id: str | None = None
    recent_intents: list[str] = Field(default_factory=list)
    recent_order_ids: list[str] = Field(default_factory=list)
    last_agent: str | None = None
    last_resolution_status: str | None = None

    def add_order_id(self, order_id: str) -> None:
        if not order_id:
            return
        self.current_order_id = order_id
        if order_id in self.recent_order_ids:
            self.recent_order_ids.remove(order_id)
        self.recent_order_ids.insert(0, order_id)
        if len(self.recent_order_ids) > 5:
            self.recent_order_ids = self.recent_order_ids[:5]

    def add_intent(self, intent: str) -> None:
        if not intent or intent == "unknown":
            return
        self.current_intent = intent
        if intent in self.recent_intents:
            self.recent_intents.remove(intent)
        self.recent_intents.insert(0, intent)
        if len(self.recent_intents) > 5:
            self.recent_intents = self.recent_intents[:5]


class SessionManager:
    """In-memory session store mapping session_id -> ConversationContext."""

    _sessions: dict[str, ConversationContext] = {}

    @classmethod
    def get_context(cls, session_id: str) -> ConversationContext:
        if session_id not in cls._sessions:
            cls._sessions[session_id] = ConversationContext(session_id=session_id)
        return cls._sessions[session_id]

    @classmethod
    def update_context(
        cls,
        session_id: str,
        state: "AgentState",
    ) -> ConversationContext:
        ctx = cls.get_context(session_id)
        if state.order_id:
            ctx.add_order_id(state.order_id)
        if state.customer_id:
            ctx.customer_id = state.customer_id
        if state.product_id:
            ctx.current_product_id = state.product_id
        if state.intent and state.intent != "unknown":
            ctx.add_intent(state.intent)
        if state.current_agent:
            ctx.last_agent = state.current_agent
        ctx.last_resolution_status = state.status.value if isinstance(state.status, OrchestrationStatus) else str(state.status)
        return ctx

    @classmethod
    def clear_session(cls, session_id: str) -> None:
        if session_id in cls._sessions:
            del cls._sessions[session_id]


class AgentState(BaseModel):
    user_request: str
    session_id: str = "default_session"
    intent: str = "unknown"
    intents: list[str] = Field(default_factory=list)

    order_id: str | None = None
    customer_id: str | None = None
    product_id: str | None = None
    reason: str | None = None

    current_agent: str | None = None
    current_action: str | None = None

    plan: list[ActionItem] = Field(default_factory=list)
    completed_actions: list[dict[str, Any]] = Field(default_factory=list)

    tool_result: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    policy_context: PolicyContext | None = None
    decision: AgentDecision | None = None
    escalation_context: EscalationContext | None = None
    conversation_context: ConversationContext | None = None

    attempt_count: int = 0
    max_attempts: int = 3

    status: OrchestrationStatus = OrchestrationStatus.RECEIVED

    escalation_reason: str | None = None
    ticket_id: str | None = None

    final_response: str | None = None

    def increment_attempt(self) -> None:
        """Increment attempt count and update status if max_attempts exceeded."""
        self.attempt_count += 1
        if self.attempt_count > self.max_attempts and self.status not in (
            OrchestrationStatus.RESOLVED,
            OrchestrationStatus.NEEDS_CLARIFICATION,
        ):
            self.status = OrchestrationStatus.ESCALATED
            if not self.escalation_reason:
                self.escalation_reason = f"Maximum attempt limit ({self.max_attempts}) reached without resolution."

    def to_dict(self) -> dict[str, Any]:
        """Convert state to structured dictionary representation."""
        return {
            "user_request": self.user_request,
            "session_id": self.session_id,
            "intent": self.intent,
            "intents": self.intents,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "reason": self.reason,
            "current_agent": self.current_agent,
            "current_action": self.current_action,
            "plan": [action.model_dump() for action in self.plan],
            "completed_actions": self.completed_actions,
            "tool_result": self.tool_result,
            "verification_result": self.verification_result,
            "policy_context": self.policy_context.model_dump() if self.policy_context else None,
            "decision": self.decision.model_dump() if self.decision else None,
            "escalation_context": self.escalation_context.model_dump() if self.escalation_context else None,
            "conversation_context": self.conversation_context.model_dump() if self.conversation_context else None,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "status": self.status.value if isinstance(self.status, OrchestrationStatus) else str(self.status),
            "escalation_reason": self.escalation_reason,
            "ticket_id": self.ticket_id,
            "final_response": self.final_response,
        }




