"""
backend/test_orchestrator.py — Comprehensive unit & integration tests for Agentic Orchestration.
"""

import sys
from typing import Any
from backend.database import SessionLocal
from agents.state import AgentState, OrchestrationStatus, ActionItem
from agents.orchestrator import Orchestrator
from backend.models.order import Order
from backend.models.refund import Refund
from backend.models.return_request import Return
from backend.models.replacement import Replacement
from backend.models.support_ticket import SupportTicket


def test_orchestrator_suite():
    db = SessionLocal()
    try:
        # Clean up test records for clean test isolation
        db.query(Refund).filter(Refund.order_id.in_(["ORD006"])).delete()
        db.query(Return).filter(Return.order_id.in_(["ORD002", "ORD008"])).delete()
        db.query(Replacement).filter(Replacement.order_id.in_(["ORD002", "ORD004", "ORD008"])).delete()
        db.commit()

        print("\n=================================================")
        print("  SupportFlow AI — Agentic Orchestrator Tests")
        print("=================================================\n")


        # ------------------------------------------------------------------
        # 1. State Initialisation & Transitions
        # ------------------------------------------------------------------
        print("[Test 1] Initial state creation & defaults")
        s1 = AgentState(user_request="I want a refund for ORD006")
        assert s1.status == OrchestrationStatus.RECEIVED
        assert s1.attempt_count == 0
        assert s1.max_attempts == 3

        print("[Test 2] State transition & attempt counter")
        s1.increment_attempt()
        assert s1.attempt_count == 1
        s1.increment_attempt()
        s1.increment_attempt()
        s1.increment_attempt()
        assert s1.attempt_count == 4
        assert s1.status == OrchestrationStatus.ESCALATED
        assert "Maximum attempt limit" in (s1.escalation_reason or "")


        # ------------------------------------------------------------------
        # 2. Plan Generation
        # ------------------------------------------------------------------
        print("[Test 3] Refund plan creation")
        orch = Orchestrator(db=db)
        s_ref = AgentState(user_request="I want a refund for ORD006")
        s_ref.intent = "refund"
        orch._create_plan(s_ref)
        assert len(s_ref.plan) == 3
        assert [a.action for a in s_ref.plan] == ["check_refund_eligibility", "process_refund", "verify_refund"]

        print("[Test 4] Return plan creation")
        s_ret = AgentState(user_request="I want to return ORD002")
        s_ret.intent = "return"
        orch._create_plan(s_ret)
        assert len(s_ret.plan) == 3
        assert [a.action for a in s_ret.plan] == ["check_return_eligibility", "create_return_request", "verify_return"]

        print("[Test 5] Replacement plan creation")
        s_rep = AgentState(user_request="I want a replacement for ORD004")
        s_rep.intent = "replacement"
        orch._create_plan(s_rep)
        assert len(s_rep.plan) == 3
        assert [a.action for a in s_rep.plan] == [
            "check_replacement_eligibility",
            "create_replacement_request",
            "verify_replacement",
        ]

        # ------------------------------------------------------------------
        # 3. Missing Information / Clarification Safety
        # ------------------------------------------------------------------
        print("[Test 6] Missing order ID -> NEEDS_CLARIFICATION without DB mutation")
        r_clarify = orch.run("I want a refund for my item", db=db)
        assert r_clarify["status"] == "NEEDS_CLARIFICATION"
        assert "order id" in r_clarify["final_response"].lower()
        assert len(r_clarify["completed_actions"]) == 0

        # ------------------------------------------------------------------
        # 4. Refund Execution & Verification
        # ------------------------------------------------------------------
        print("[Test 7] Refund workflow execution & DB verification (ORD006)")
        r_refund = orch.run("I want a refund for order ORD006 because I cancelled it", db=db)
        assert r_refund["status"] in ("RESOLVED", "ESCALATED")
        assert "ORD006" in r_refund["order_id"]
        assert len(r_refund["completed_actions"]) > 0
        assert r_refund["state"]["tool_result"] is not None

        # ------------------------------------------------------------------
        # 5. Return Execution & Verification
        # ------------------------------------------------------------------
        print("[Test 8] Return workflow execution & DB verification (ORD002)")
        r_return = orch.run("I want to return my order ORD002", db=db)
        assert r_return["status"] == "RESOLVED"
        assert r_return["verification"].get("status") in ("REQUESTED", "APPROVED", "COMPLETED")
        assert r_return["verification"].get("return_id") is not None

        # ------------------------------------------------------------------
        # 6. Replacement Execution & Verification
        # ------------------------------------------------------------------
        print("[Test 9] Replacement workflow execution & DB verification (ORD004)")
        r_rep = orch.run("I need a replacement for order ORD004", db=db)
        assert r_rep["status"] == "RESOLVED"
        assert r_rep["verification"].get("status") in ("REQUESTED", "APPROVED", "COMPLETED")
        assert r_rep["verification"].get("replacement_id") is not None

        # ------------------------------------------------------------------
        # 7. Ineligible Request & Escalation Ticket Creation
        # ------------------------------------------------------------------
        print("[Test 10] Ineligible request -> REPLANNING -> ESCALATED with Support Ticket")
        # ORD009 is CONFIRMED (active order, not delivered) -> ineligible for return
        r_inelig = orch.run("I want to return order ORD009", db=db)
        assert r_inelig["status"] == "ESCALATED"
        assert r_inelig["ticket_id"] is not None
        assert "TKT-" in r_inelig["ticket_id"]

        # Verify support ticket exists in DB
        tkt = db.query(SupportTicket).filter_by(ticket_id=r_inelig["ticket_id"]).first()
        assert tkt is not None
        assert tkt.order_id == "ORD009"

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n=================================================")
        print("  Orchestrator Tests Passed: 10/10")
        print("=================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    test_orchestrator_suite()
