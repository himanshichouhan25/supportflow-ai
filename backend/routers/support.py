"""
backend/routers/support.py — FastAPI Router for Support Resolution API.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.support import SupportResolutionRequest, SupportResolutionResponse
from agents.orchestrator import Orchestrator
from agents.state import SessionManager

router = APIRouter(prefix="/api/support", tags=["Support Resolution"])
v1_router = APIRouter(prefix="/api/v1/support", tags=["Support Resolution V1"])


@router.post("/resolve", response_model=SupportResolutionResponse, status_code=status.HTTP_200_OK)
@v1_router.post("/resolve", response_model=SupportResolutionResponse, status_code=status.HTTP_200_OK)
def resolve_support_request(
    payload: SupportResolutionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Execute multi-step agentic support resolution workflow for customer request.
    """
    if not payload.message or not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Support request message cannot be empty.",
        )

    session_id = payload.session_id or "default_session"

    # Pre-populate session context if order_id/customer_id/product_id provided
    ctx = SessionManager.get_context(session_id)
    if payload.order_id:
        ctx.add_order_id(payload.order_id)
    if payload.customer_id:
        ctx.customer_id = payload.customer_id
    if payload.product_id:
        ctx.current_product_id = payload.product_id

    orch = Orchestrator(db=db)
    result = orch.run(
        user_message=payload.message,
        db=db,
        session_id=session_id,
    )

    status_val = result.get("status", "COMPLETED")
    state_dict = result.get("state", {})
    
    final_status = status_val
    msg = result.get("final_response") or ""
    resolved = (status_val == "RESOLVED")
    
    esc_ctx = result.get("escalation_context")
    ticket_data = None
    if esc_ctx:
        ticket_data = esc_ctx
    elif result.get("ticket_id"):
        ticket_data = {
            "ticket_id": result.get("ticket_id"),
            "status": "OPEN",
            "reason": result.get("escalation_reason"),
        }

    clarification_needed = (status_val == "NEEDS_CLARIFICATION") or state_dict.get("clarification_needed", False)
    clarification_prompt = state_dict.get("clarification_prompt")
    missing = state_dict.get("missing") or ("order_id" if status_val == "NEEDS_CLARIFICATION" and not result.get("order_id") else None)

    response_data = {
        "success": result.get("success", True),
        "status": status_val,
        "final_status": final_status,
        "intent": result.get("intent") or state_dict.get("intent", "general"),
        "goal": state_dict.get("goal"),
        "order_id": result.get("order_id"),
        "session_id": session_id,
        "message": msg,
        "final_response": msg,
        "selected_agent": state_dict.get("current_agent"),
        "selected_action": state_dict.get("current_action"),
        "workflow_plan": result.get("workflow_plan"),
        "workflow_trace": result.get("workflow_trace") or [],
        "completed_actions": result.get("completed_actions") or [],
        "completed_steps": state_dict.get("completed_steps") or [],
        "failed_steps": state_dict.get("failed_steps") or [],
        "replans": state_dict.get("replan_count", 0),
        "tool_results": state_dict.get("observations") or [],
        "verification": result.get("verification") or {},
        "verification_result": result.get("verification"),
        "policy_context": result.get("policy_context"),
        "decision": result.get("decision"),
        "escalation_context": esc_ctx,
        "ticket": ticket_data,
        "ticket_id": result.get("ticket_id"),
        "escalation_reason": result.get("escalation_reason"),
        "conversation_context": result.get("conversation_context"),
        "clarification_needed": clarification_needed,
        "clarification_prompt": clarification_prompt,
        "missing": missing,
        "resolved": resolved,
    }
    return response_data
