"""
backend/test_agents.py -- Integration tests for all four specialist agents.

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.test_agents

Uses the existing SQLAlchemy SessionLocal.
Safe to rerun: cancel tests handle the already-cancelled case gracefully.
All output is plain ASCII (Windows cp1252 compatible).
"""

import sys
from typing import Any

from backend.database import SessionLocal
from agents.order_agent import run as order_agent
from agents.payment_agent import run as payment_agent
from agents.delivery_agent import run as delivery_agent
from agents.account_agent import run as account_agent

# ---------------------------------------------------------------------------
# Tiny test harness
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _check(label: str, result: dict[str, Any], key: str, expected: Any) -> None:
    """Assert result[key] == expected and print [PASS] or [FAIL]."""
    global _passed, _failed
    actual = result.get(key)
    if actual == expected:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label}")
        print(f"         key='{key}'  expected={expected!r}  got={actual!r}")
        _failed += 1


def _check_truthy(label: str, value: Any) -> None:
    """Assert value is truthy."""
    global _passed, _failed
    if value:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label} (value was {value!r})")
        _failed += 1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run_tests() -> None:
    db = SessionLocal()
    try:
        print("\n============================================")
        print("  SupportFlow AI -- Specialist Agent Tests")
        print("============================================\n")

        # ==================================================================
        # OrderAgent
        # ==================================================================
        print("[OrderAgent]")

        # Test: check order status
        r = order_agent("Check the status of order ORD005", db)
        _check("agent name is OrderAgent", r, "agent", "OrderAgent")
        _check("action is check_order", r, "action", "check_order")
        _check("tool is check_order", r, "tool", "check_order")
        _check("tool_result success is True", r["tool_result"], "success", True)
        _check("ORD005 status is PENDING", r["tool_result"], "status", "PENDING")
        _check_truthy("response is non-empty", r.get("response"))

        # Test: check a delivered order
        r = order_agent("Where is my order ORD002?", db)
        _check("ORD002 check -- success", r["tool_result"], "success", True)
        _check("ORD002 status is DELIVERED", r["tool_result"], "status", "DELIVERED")

        # Test: cancel order -- use ORD003 (CONFIRMED, safe to cancel)
        # If already cancelled from a previous run, handles gracefully.
        r = order_agent("Please cancel order ORD003", db)
        _check("cancel action selected", r, "action", "cancel_order")
        tool_res = r["tool_result"]
        if tool_res.get("success"):
            _check("ORD003 status set to CANCELLED", tool_res, "status", "CANCELLED")
        else:
            # Already cancelled on a previous test run -- idempotency OK
            _check_truthy(
                "ORD003 already cancelled (idempotent rerun OK)",
                "already" in tool_res.get("message", "").lower()
                or tool_res.get("status") == "CANCELLED"
            )

        # Test: cannot cancel a DELIVERED order
        r = order_agent("Cancel my order ORD002", db)
        _check("DELIVERED order cancel rejected (success=False)", r["tool_result"], "success", False)

        # Test: missing order ID
        r = order_agent("I have an issue with my order", db)
        _check("missing order ID -- action is None", r, "action", None)
        _check_truthy("missing ID response non-empty", r.get("response"))

        # Test: non-existent order ID format (no digits -> missing-ID path)
        r = order_agent("Check order ORD_FAKE", db)
        _check_truthy("ORD_FAKE has no digits -- returns missing-ID or not-found response",
                      r.get("tool_result") is None or
                      (r.get("tool_result") or {}).get("success") is False)

        # ==================================================================
        # PaymentAgent
        # ==================================================================
        print("\n[PaymentAgent]")

        # Test: check payment (Scenario A -- SUCCESS payment on PENDING order)
        r = payment_agent("Was my payment successful for ORD005?", db)
        _check("agent name is PaymentAgent", r, "agent", "PaymentAgent")
        _check("action is check_payment", r, "action", "check_payment")
        _check("tool_result success is True", r["tool_result"], "success", True)
        _check("ORD005 payment status is SUCCESS", r["tool_result"], "status", "SUCCESS")
        _check_truthy("response non-empty", r.get("response"))

        # Test: failed payment (Scenario E)
        r = payment_agent("Check payment for ORD010", db)
        _check("ORD010 payment found", r["tool_result"], "success", True)
        _check("ORD010 payment status is FAILED", r["tool_result"], "status", "FAILED")

        # Test: refund eligibility (Scenario C -- CANCELLED + REFUNDED)
        r = payment_agent("Can I get a refund for ORD007?", db)
        _check("refund action selected", r, "action", "check_refund_eligibility")
        _check("ORD007 eligibility check succeeded", r["tool_result"], "success", True)
        _check("ORD007 already refunded -- not eligible", r["tool_result"], "eligible", False)

        # Test: refund eligibility for active order
        r = payment_agent("I want a refund for ORD005", db)
        _check("ORD005 refund -- not eligible (order still active)", r["tool_result"], "eligible", False)

        # Test: missing order ID
        r = payment_agent("I need help with my payment", db)
        _check("missing order ID -- action is None", r, "action", None)

        # ==================================================================
        # DeliveryAgent
        # ==================================================================
        print("\n[DeliveryAgent]")

        # Test: delayed delivery (Scenario D)
        r = delivery_agent("What is the delivery status of ORD009?", db)
        _check("agent name is DeliveryAgent", r, "agent", "DeliveryAgent")
        _check("action is check_delivery", r, "action", "check_delivery")
        _check("ORD009 delivery found", r["tool_result"], "success", True)
        _check("ORD009 delivery status is DELAYED", r["tool_result"], "status", "DELAYED")
        _check_truthy("DELAYED response contains apology", "delay" in r.get("response", "").lower()
                      or "apologise" in r.get("response", "").lower()
                      or "delayed" in r.get("response", "").lower())

        # Test: delivered order (Scenario B)
        r = delivery_agent("Has my order ORD002 been delivered?", db)
        _check("ORD002 delivery status is DELIVERED", r["tool_result"], "status", "DELIVERED")

        # Test: cancelled order has no delivery record
        r = delivery_agent("Track order ORD007", db)
        _check("ORD007 no delivery record (success=False)", r["tool_result"], "success", False)

        # Test: missing order ID
        r = delivery_agent("Where is my package?", db)
        _check("missing order ID -- action is None", r, "action", None)

        # ==================================================================
        # AccountAgent
        # ==================================================================
        print("\n[AccountAgent]")

        # Test: look up customer C101
        r = account_agent("Show my account details for C101", db)
        _check("agent name is AccountAgent", r, "agent", "AccountAgent")
        _check("action is check_account", r, "action", "check_account")
        _check("C101 found", r["tool_result"], "success", True)
        _check("C101 name is Aarav Sharma", r["tool_result"], "name", "Aarav Sharma")
        _check("C101 account_status is active", r["tool_result"], "account_status", "active")
        _check_truthy("response is non-empty", r.get("response"))
        # Ensure no password field in tool_result
        _check_truthy("no 'password' field in tool_result", "password" not in r["tool_result"])

        # Test: non-existent customer
        r = account_agent("Show account for C999", db)
        _check("C999 not found (success=False)", r["tool_result"], "success", False)

        # Test: missing customer ID
        r = account_agent("What is my account status?", db)
        _check("missing customer ID -- action is None", r, "action", None)

        # ==================================================================
        # Summary
        # ==================================================================
        total = _passed + _failed
        print(f"\n============================================")
        print(f"  Results: {_passed}/{total} passed, {_failed} failed")
        print(f"============================================\n")

        if _failed > 0:
            sys.exit(1)

    except Exception as exc:
        print(f"\nFATAL ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
