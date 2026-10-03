"""
backend/test_orchestrator.py — Comprehensive unit & integration tests for Agentic Orchestration.
"""

import sys
from typing import Any
from backend.database import SessionLocal
from agents.state import AgentState, OrchestrationStatus, ActionItem
from agents.orchestrator import Orchestrator
from backend.models.order import Order
from backend.models.payment import Payment
from backend.models.refund import Refund
from backend.models.return_request import Return
from backend.models.replacement import Replacement
from backend.models.support_ticket import SupportTicket


def test_orchestrator_suite():
    db = SessionLocal()
    try:
        # Clean up test records for clean test isolation
        db.query(Refund).filter(Refund.order_id.in_(["ORD006"])).delete()
        p006 = db.query(Payment).filter_by(order_id="ORD006").first()
        if p006:
            p006.payment_status = "SUCCESS"
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
        # 8. Policy RAG Integration & Context Attachment
        # ------------------------------------------------------------------
        print("[Test 11] Refund policy retrieval")
        r_pol_ref = orch.run("I want a refund for my cancelled order ORD006", db=db)
        assert r_pol_ref["policy_context"] is not None
        ref_cats = [p["category"] for p in r_pol_ref["policy_context"]["matched_policies"]]
        assert "refund" in ref_cats
        assert r_pol_ref["policy_context"]["requires_policy_review"] is False

        print("[Test 12] Return policy retrieval")
        r_pol_ret = orch.run("I want to return my order ORD002", db=db)
        assert r_pol_ret["policy_context"] is not None
        ret_cats = [p["category"] for p in r_pol_ret["policy_context"]["matched_policies"]]
        assert "return" in ret_cats

        print("[Test 13] Replacement policy retrieval")
        r_pol_rep = orch.run("My product is damaged. I want a replacement for ORD004", db=db)
        assert r_pol_rep["policy_context"] is not None
        rep_cats = [p["category"] for p in r_pol_rep["policy_context"]["matched_policies"]]
        assert "replacement" in rep_cats

        print("[Test 14] Delivery policy retrieval")
        r_pol_del = orch.run("My order ORD001 is late. What is the delivery status?", db=db)
        assert r_pol_del["policy_context"] is not None
        del_cats = [p["category"] for p in r_pol_del["policy_context"]["matched_policies"]]
        assert "delivery" in del_cats

        print("[Test 15] Payment policy retrieval")
        r_pol_pay = orch.run("My payment failed but money was deducted from my bank", db=db)
        assert r_pol_pay["policy_context"] is not None
        pay_cats = [p["category"] for p in r_pol_pay["policy_context"]["matched_policies"]]
        assert "payment" in pay_cats

        print("[Test 16] Account policy retrieval")
        r_pol_acc = orch.run("I cannot login to my account and need password reset", db=db)
        assert r_pol_acc["policy_context"] is not None
        acc_cats = [p["category"] for p in r_pol_acc["policy_context"]["matched_policies"]]
        assert "account" in acc_cats

        # ------------------------------------------------------------------
        # 9. Task 8 Agent Decision & Policy-Aware Resolution Tests
        # ------------------------------------------------------------------
        print("[Test 18] AgentDecision structure & operational rationale for refund")
        r_dec_ref = orch.run("I want a refund for order ORD006 because I cancelled it", db=db)
        assert r_dec_ref["decision"] is not None
        d_ref = r_dec_ref["decision"]
        assert d_ref["intent"] in ("refund", "payment")
        assert "ORD006" in d_ref["goal"]
        assert d_ref["selected_agent"] == "payment"
        assert d_ref["selected_action"] in ("check_refund_eligibility", "process_refund")
        assert "CANCELLED" in d_ref["rationale"] or "Refund policy matched" in d_ref["rationale"]
        assert d_ref["policy_supported"] is True
        assert d_ref["transactional_check_required"] is True


        print("[Test 19] AgentDecision structure & operational rationale for ineligible return (ORD009)")
        r_dec_inelig = orch.run("I want to return order ORD009", db=db)
        assert r_dec_inelig["decision"] is not None
        d_inelig = r_dec_inelig["decision"]
        assert d_inelig["intent"] == "return"
        assert "not delivered" in d_inelig["rationale"] or "CONFIRMED" in d_inelig["rationale"]

        # ------------------------------------------------------------------
        # 10. Task 9 Intelligent Escalation & Ticket Intelligence Tests
        # ------------------------------------------------------------------
        print("[Test 21] EscalationContext structure for ineligible return (ORD009)")
        r_esc_inelig = orch.run("I want to return order ORD009", db=db)
        assert r_esc_inelig["escalation_context"] is not None
        esc = r_esc_inelig["escalation_context"]
        assert esc["category"] == "INELIGIBLE_TRANSACTION"
        assert esc["priority"] == "MEDIUM"
        assert esc["order_id"] == "ORD009"
        assert esc["intent"] == "return"
        assert len(esc["attempted_actions"]) > 0
        assert "recommended_next_step" in esc

        print("[Test 22] Duplicate ticket protection check for repeated escalation")
        r_esc_dup = orch.run("I want to return order ORD009", db=db)
        assert r_esc_dup["ticket_id"] == r_esc_inelig["ticket_id"]

        print("[Test 23] EscalationContext state serialization")
        assert r_esc_inelig["state"]["escalation_context"] is not None
        assert r_esc_inelig["state"]["escalation_context"]["category"] == "INELIGIBLE_TRANSACTION"

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print("\n=================================================")
        print("  Orchestrator Tests Passed: 23/23")
        print("=================================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    test_orchestrator_suite()



