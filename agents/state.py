"""
agents/state.py — Typed agent state and status representation for SupportFlow AI.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class OrchestrationStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
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


class AgentState(BaseModel):
    user_request: str
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
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "status": self.status.value if isinstance(self.status, OrchestrationStatus) else str(self.status),
            "escalation_reason": self.escalation_reason,
            "ticket_id": self.ticket_id,
            "final_response": self.final_response,
        }
