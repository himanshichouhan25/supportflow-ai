"""
backend/schemas/support.py — Pydantic schemas for FastAPI Support Resolution API.
"""

from typing import Any
from pydantic import BaseModel, Field


class SupportResolutionRequest(BaseModel):
    message: str = Field(..., description="Raw customer support query message")
    session_id: str | None = Field(default="default_session", description="Session identifier for multi-turn conversation memory")
    customer_id: str | None = Field(default=None, description="Optional customer ID context")
    order_id: str | None = Field(default=None, description="Optional order ID context")
    product_id: str | None = Field(default=None, description="Optional product ID context")


class SupportResolutionResponse(BaseModel):
    success: bool = True
    status: str
    final_status: str
    intent: str | None = None
    goal: str | None = None
    order_id: str | None = None
    session_id: str
    message: str | None = None
    final_response: str | None = None
    selected_agent: str | None = None
    selected_action: str | None = None
    workflow_plan: dict[str, Any] | None = None
    workflow_trace: list[dict[str, Any]] = Field(default_factory=list)
    completed_actions: list[str] = Field(default_factory=list)
    completed_steps: list[dict[str, Any]] = Field(default_factory=list)
    failed_steps: list[dict[str, Any]] = Field(default_factory=list)
    replans: int = 0
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] = Field(default_factory=dict)
    verification_result: dict[str, Any] | None = None
    policy_context: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    escalation_context: dict[str, Any] | None = None
    ticket: dict[str, Any] | None = None
    ticket_id: str | None = None
    escalation_reason: str | None = None
    conversation_context: dict[str, Any] | None = None
    clarification_needed: bool = False
    clarification_prompt: str | None = None
    missing: str | None = None
    resolved: bool = False
