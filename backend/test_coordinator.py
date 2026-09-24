"""
backend/test_coordinator.py -- Integration tests for the CoordinatorAgent.

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.test_coordinator

Uses the existing SQLAlchemy SessionLocal.
All output is plain ASCII (Windows cp1252 compatible).
"""

import sys
from typing import Any

from agents.coordinator import run_coordinator
from backend.database import SessionLocal

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))
        _failed += 1


def _agents_in_steps(steps: list[dict[str, Any]]) -> set[str]:
    """Return the set of non-Coordinator agent names that appear in steps."""
    return {
        s["agent"]
        for s in steps
        if s.get("agent") and s["agent"] != "Coordinator"
    }


def _specialist_call_count(steps: list[dict[str, Any]]) -> int:
    """Count how many specialist agent steps appear (excludes Coordinator steps)."""
    return sum(1 for s in steps if s.get("agent", "Coordinator") != "Coordinator")


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

def run_tests() -> None:
    db = SessionLocal()
    try:
        print("\n=================================================")
        print("  SupportFlow AI -- Coordinator Agent Tests")
        print("=================================================\n")

        # ------------------------------------------------------------------
        # Scenario 1: Payment + Order (multi-agent replanning)
        # "My payment was successful but my iPhone 15 order is still pending."
        # Expected: PaymentAgent -> replan -> OrderAgent
        # ------------------------------------------------------------------
        print("[Scenario 1] Payment SUCCESS + Order PENDING (multi-agent)")
        msg1 = "My payment was successful but my iPhone 15 order ORD005 is still pending."
        r = run_coordinator(msg1, db)

        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        _check("steps list exists", isinstance(r.get("steps"), list))
        agents = _agents_in_steps(r["steps"])
        _check("PaymentAgent was called", "PaymentAgent" in agents, str(agents))
        _check("OrderAgent was called", "OrderAgent" in agents, str(agents))
        _check("no more than 3 specialist calls",
               _specialist_call_count(r["steps"]) <= 3,
               str(_specialist_call_count(r["steps"])))
        _check("replanning step present",
               any(s.get("status") == "replanning" for s in r["steps"]))
        print(f"         Agents called: {agents}")
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Scenario 2: Cancel + Refund (multi-agent replanning)
        # "Cancel my order ORD007 and check whether I can get a refund."
        # ORD007 is already CANCELLED -- cancel returns already-cancelled message
        # then refund eligibility is checked
        # Expected: OrderAgent -> replan -> PaymentAgent
        # ------------------------------------------------------------------
        print("\n[Scenario 2] Cancel order + Refund eligibility")
        msg2 = "Cancel my order ORD007 and check whether I can get a refund."
        r = run_coordinator(msg2, db)

        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        agents = _agents_in_steps(r["steps"])
        _check("OrderAgent was called", "OrderAgent" in agents, str(agents))
        _check("PaymentAgent was called", "PaymentAgent" in agents, str(agents))
        _check("no more than 3 specialist calls",
               _specialist_call_count(r["steps"]) <= 3)
        print(f"         Agents called: {agents}")
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Scenario 3: Single delivery query
        # "Where is my package for ORD009?"
        # Expected: DeliveryAgent only (DELAYED status)
        # ------------------------------------------------------------------
        print("\n[Scenario 3] Delivery tracking -- single agent")
        msg3 = "Where is my package for ORD009?"
        r = run_coordinator(msg3, db)

        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        agents = _agents_in_steps(r["steps"])
        _check("DeliveryAgent was called", "DeliveryAgent" in agents, str(agents))
        _check("OrderAgent NOT called unnecessarily",
               "OrderAgent" not in agents, str(agents))
        _check("1 specialist call only", _specialist_call_count(r["steps"]) == 1)
        print(f"         Agents called: {agents}")
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Scenario 4: Account query
        # "What email is registered for C101?"
        # Expected: AccountAgent only
        # ------------------------------------------------------------------
        print("\n[Scenario 4] Account query -- single agent")
        msg4 = "What email is registered for customer C101?"
        r = run_coordinator(msg4, db)

        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        agents = _agents_in_steps(r["steps"])
        _check("AccountAgent was called", "AccountAgent" in agents, str(agents))
        _check("no other agent called unnecessarily",
               agents == {"AccountAgent"}, str(agents))
        print(f"         Agents called: {agents}")
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Scenario 5: Unknown / greeting
        # "Hello"
        # Expected: clarification response, no specialist called
        # ------------------------------------------------------------------
        print("\n[Scenario 5] Unknown intent -- graceful clarification")
        msg5 = "Hello"
        r = run_coordinator(msg5, db)

        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        _check("intent is unknown", r.get("intent") == "unknown")
        _check("no specialist agents called",
               _specialist_call_count(r.get("steps", [])) == 0)
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Scenario 6: Empty message guard
        # ------------------------------------------------------------------
        print("\n[Scenario 6] Empty message guard")
        r = run_coordinator("   ", db)
        _check("returns success=True for empty message", r.get("success") is True)
        _check("final_response is helpful", bool(r.get("final_response")))
        _check("no steps for empty message", len(r.get("steps", [])) == 0)

        # ------------------------------------------------------------------
        # Scenario 7: Missing ID -- delivery without order ID
        # ------------------------------------------------------------------
        print("\n[Scenario 7] Delivery request without order ID")
        msg7 = "Where is my delivery?"
        r = run_coordinator(msg7, db)
        _check("returns success=True", r.get("success") is True)
        _check("final_response exists", bool(r.get("final_response")))
        # With no order ID, coordinator returns a clarification message
        # instead of calling DeliveryAgent with None -- check for that.
        _check(
            "clarification returned for missing order ID",
            "order" in r["final_response"].lower() or "provide" in r["final_response"].lower(),
            r["final_response"][:120],
        )
        _check(
            "None not in response",
            "None" not in r["final_response"],
            r["final_response"][:120],
        )
        print(f"         Response: {r['final_response'][:120]}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total = _passed + _failed
        print(f"\n=================================================")
        print(f"  Results: {_passed}/{total} passed, {_failed} failed")
        print(f"=================================================\n")

        if _failed > 0:
            sys.exit(1)

    except Exception as exc:
        print(f"\nFATAL ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
