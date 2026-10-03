"""
backend/test_workflow.py — Unit & Integration Test Suite for Advanced Multi-Step Agent Workflows (Task 11).
"""

import sys
from typing import Any
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.refund import Refund
from backend.models.return_request import Return
from backend.models.replacement import Replacement
from backend.models.support_ticket import SupportTicket

from agents.state import (
    AgentState,
    OrchestrationStatus,
    StepStatus,
    WorkflowStep,
    WorkflowPlan,
    SessionManager,
)
from agents.orchestrator import Orchestrator


def test_workflow_suite():
    db = SessionLocal()
    try:
        print("\n=================================================")
        print("  SupportFlow AI — Advanced Multi-Step Workflow Tests")
        print("=================================================\n")

        # Cleanup test records for isolation
        db.query(Refund).filter(Refund.order_id.in_(["ORD006"])).delete()
        p006 = db.query(Payment).filter_by(order_id="ORD006").first()
        if p006:
            p006.payment_status = "SUCCESS"
        db.query(Return).filter(Return.order_id.in_(["ORD002", "ORD008", "ORD009"])).delete()
        db.query(Replacement).filter(Replacement.order_id.in_(["ORD002", "ORD004", "ORD008"])).delete()
        db.commit()

        orch = Orchestrator(db=db)

        # ------------------------------------------------------------------
        # Test 1: WorkflowPlan Creation & Dependency Model
        # ------------------------------------------------------------------
        print("[Test 1] WorkflowPlan creation & step dependency ordering")
        s1 = AgentState(user_request="I want a replacement for ORD004")
        s1.intent = "replacement"
        s1.order_id = "ORD004"
        orch._create_plan(s1)

        assert s1.workflow_plan is not None
        assert s1.workflow_plan.max_steps == 8
        assert s1.workflow_plan.max_replans == 1
        step_ids = [s.step_id for s in s1.workflow_plan.steps]
        actions = [s.action for s in s1.workflow_plan.steps]
        assert actions[:3] == ["policy_retrieval", "check_order", "check_replacement_eligibility"]
        assert "create_replacement_request" in actions
        assert "verify_replacement" in actions

        # Check dependency chain
        create_step = next(s for s in s1.workflow_plan.steps if s.action == "create_replacement_request")
        assert "check_replacement_eligibility" in [
            s.action for s in s1.workflow_plan.steps if s.step_id in create_step.depends_on
        ]

        # ------------------------------------------------------------------
        # E2E Scenario 1: Multi-step Replacement Request
        # "My delivered product ORD004 is damaged. I want a replacement and I want to know its status."
        # ------------------------------------------------------------------
        print("\n[Test 2 - E2E 1] Replacement Multi-Step Request (ORD004)")
        r_sc1 = orch.run(
            "My delivered product ORD004 is damaged. I want a replacement and I want to know its status.",
            db=db,
            session_id="test_wf_sc1",
        )

        assert r_sc1["status"] == "RESOLVED"
        assert r_sc1["order_id"] == "ORD004"
        assert r_sc1["workflow_plan"] is not None
        assert r_sc1["workflow_trace"] is not None
        trace_actions = [t["step"] for t in r_sc1["workflow_trace"]]
        assert "check_replacement_eligibility" in trace_actions
        assert "create_replacement_request" in trace_actions
        assert "verify_replacement" in trace_actions

        # DB Verification
        rep_db = db.query(Replacement).filter_by(order_id="ORD004").first()
        assert rep_db is not None
        assert rep_db.status in ("REQUESTED", "APPROVED", "COMPLETED")
        print(f"         Replacement created in DB: {rep_db.replacement_id}, status={rep_db.status}")

        # ------------------------------------------------------------------
        # E2E Scenario 2: Multi-step Refund Request
        # "I want a refund for cancelled order ORD006 and tell me the refund status."
        # ------------------------------------------------------------------
        print("\n[Test 3 - E2E 2] Refund Multi-Step Request (ORD006)")
        r_sc2 = orch.run(
            "I want a refund for cancelled order ORD006 and tell me the refund status.",
            db=db,
            session_id="test_wf_sc2",
        )

        assert r_sc2["status"] == "RESOLVED"
        assert r_sc2["order_id"] == "ORD006"
        ref_db = db.query(Refund).filter_by(order_id="ORD006").first()
        assert ref_db is not None
        assert ref_db.status == "COMPLETED"
        ref_count = db.query(Refund).filter_by(order_id="ORD006").count()
        assert ref_count == 1, "No duplicate refund record created"
        print(f"         Refund created in DB: {ref_db.refund_id}, status={ref_db.status}")

        # ------------------------------------------------------------------
        # E2E Scenario 3: Failed Return Eligibility
        # "Return ORD009 and tell me why it cannot be returned."
        # ORD009 is CONFIRMED (not delivered) -> Eligibility fails
        # ------------------------------------------------------------------
        print("\n[Test 4 - E2E 3] Failed Eligibility Return Request (ORD009)")
        r_sc3 = orch.run(
            "Return ORD009 and tell me why it cannot be returned.",
            db=db,
            session_id="test_wf_sc3",
        )

        assert r_sc3["status"] == "ESCALATED"
        assert r_sc3["order_id"] == "ORD009"
        # Verify create_return_request was skipped due to failed dependency
        wf_steps_sc3 = r_sc3["workflow_plan"]["steps"]
        create_step_sc3 = next((s for s in wf_steps_sc3 if s["action"] == "create_return_request"), None)
        if create_step_sc3:
            assert create_step_sc3["status"] in ("SKIPPED", "PENDING")

        ret_db = db.query(Return).filter_by(order_id="ORD009").first()
        assert ret_db is None, "No return record created for ineligible order"
        assert r_sc3["ticket_id"] is not None, "Support ticket created for escalation"
        print(f"         Ineligible return safely escalated with ticket: {r_sc3['ticket_id']}")

        # ------------------------------------------------------------------
        # E2E Scenario 4: Isolated Test Fixture (Action failure after eligibility)
        # ------------------------------------------------------------------
        print("\n[Test 5 - E2E 4] Partial Success & Action Failure Handling")
        # Simulating state where eligibility succeeds but action/verification triggers escalation
        s_fail = AgentState(user_request="I want to return ORD002", session_id="test_wf_sc4")
        s_fail.order_id = "ORD002"
        s_fail.intent = "return"
        orch._create_plan(s_fail)
        # Mock failed step in workflow plan
        s_fail.workflow_plan.completed_steps = ["step_1", "step_2", "step_3"]
        s_fail.workflow_plan.failed_steps = ["step_4"]
        orch._escalate(db=db, state=s_fail, reason="Simulated return creation network timeout")

        assert s_fail.status == OrchestrationStatus.ESCALATED
        assert s_fail.ticket_id is not None
        assert "Simulated return creation" in (s_fail.escalation_reason or "")
        print(f"         Preserved completed steps: {s_fail.workflow_plan.completed_steps}")
        print(f"         Ticket created for action failure: {s_fail.ticket_id}")

        # ------------------------------------------------------------------
        # E2E Scenario 5: Context Follow-Up Workflow
        # Turn 1: "Tell me about ORD004."
        # Turn 2: "I want a replacement and tell me its status."
        # ------------------------------------------------------------------
        print("\n[Test 6 - E2E 5] Conversation Context Follow-Up Multi-Step Workflow")
        sess_followup = "test_wf_sc5"
        SessionManager.clear_session(sess_followup)

        r_t1 = orch.run("Tell me about ORD004.", db=db, session_id=sess_followup)
        assert r_t1["order_id"] == "ORD004"

        r_t2 = orch.run("I want a replacement and tell me its status.", db=db, session_id=sess_followup)
        assert r_t2["order_id"] == "ORD004"
        assert r_t2["intent"] == "replacement"
        assert r_t2["status"] == "RESOLVED"
        print(f"         Resolved 'it/replacement' -> ORD004 with multi-step result: {r_t2['status']}")

        # ------------------------------------------------------------------
        # E2E Scenario 6: Ambiguous Context Handling
        # Turn 1: ORD002 discussed
        # Turn 2: ORD004 discussed
        # Turn 3: "Replace that one and tell me its status."
        # ------------------------------------------------------------------
        print("\n[Test 7 - E2E 6] Ambiguous Context -> NEEDS_CLARIFICATION")
        sess_amb = "test_wf_sc6"
        SessionManager.clear_session(sess_amb)

        orch.run("Check ORD002", db=db, session_id=sess_amb)
        orch.run("Check ORD004", db=db, session_id=sess_amb)
        r_amb = orch.run("Replace that one and tell me its status.", db=db, session_id=sess_amb)

        assert r_amb["status"] == "NEEDS_CLARIFICATION"
        assert "Which order" in r_amb["final_response"] or "ORD" in r_amb["final_response"]
        print(f"         Ambiguous reference correctly returned clarification prompt: {r_amb['final_response'][:80]}")

        # ------------------------------------------------------------------
        # Test 8: Duplicate Action Protection
        # ------------------------------------------------------------------
        print("\n[Test 8] Duplicate State-Changing Action Protection")
        s_dup = AgentState(user_request="Process refund for ORD006 twice", session_id="test_wf_dup")
        s_dup.order_id = "ORD006"
        s_dup.intent = "refund"
        orch._create_plan(s_dup)
        # Duplicate process_refund step
        step_dup = WorkflowStep(
            step_id="step_dup",
            action="process_refund",
            agent="payment",
            description="Duplicate process refund attempt",
            depends_on=["step_3"],
        )
        s_dup.workflow_plan.steps.append(step_dup)
        orch._execute_plan(s_dup, db)

        executed_process_refunds = [
            a for a in s_dup.completed_actions if a["action"] == "process_refund" and a["status"] != "SKIPPED"
        ]
        assert len(executed_process_refunds) <= 1, "Duplicate process_refund prevented"

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n=================================================")
        print("  All Task 11 Multi-Step Workflow Tests Passed!")
        print("=================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    test_workflow_suite()
