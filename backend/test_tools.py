"""
backend/test_tools.py -- Integration test runner for all support tools.

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.test_tools

Uses the existing SQLAlchemy SessionLocal -- no extra DB connections.
Safe to run multiple times: cancel_order handles the already-cancelled
case gracefully.
"""

import sys
from typing import Any

from backend.database import SessionLocal
from tools.account_tool import check_account
from tools.delivery_tool import check_delivery
from tools.order_tool import cancel_order, check_order
from tools.payment_tool import check_payment, check_refund_eligibility


# ---------------------------------------------------------------------------
# Tiny test harness
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _run(label: str, result: dict[str, Any], expect_key: str, expect_value: Any) -> None:
    """Print [PASS] or [FAIL] for a single assertion."""
    global _passed, _failed
    actual = result.get(expect_key)
    if actual == expect_value:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label}")
        print(f"         expected {expect_key}={expect_value!r}, got {actual!r}")
        print(f"         full result: {result}")
        _failed += 1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def run_tests() -> None:
    db = SessionLocal()
    try:
        print("\n========================================")
        print("  SupportFlow AI -- Tool Integration Tests")
        print("========================================\n")

        # ------------------------------------------------------------------
        # check_order
        # ------------------------------------------------------------------
        print("[check_order]")

        r = check_order("ORD005", db)        # Scenario A: PENDING order
        _run("ORD005 found", r, "success", True)
        _run("ORD005 status is PENDING", r, "status", "PENDING")

        r = check_order("ORD002", db)        # Scenario B: DELIVERED order
        _run("ORD002 found", r, "success", True)
        _run("ORD002 status is DELIVERED", r, "status", "DELIVERED")

        r = check_order("ORD_NONEXISTENT", db)
        _run("Non-existent order returns success=False", r, "success", False)

        # ------------------------------------------------------------------
        # check_payment
        # ------------------------------------------------------------------
        print("\n[check_payment]")

        r = check_payment("ORD005", db)      # SUCCESS payment on PENDING order
        _run("ORD005 payment found", r, "success", True)
        _run("ORD005 payment status is SUCCESS", r, "status", "SUCCESS")

        r = check_payment("ORD010", db)      # Scenario E: FAILED payment
        _run("ORD010 payment found", r, "success", True)
        _run("ORD010 payment status is FAILED", r, "status", "FAILED")

        r = check_payment("ORD_NONEXISTENT", db)
        _run("Non-existent order payment returns success=False", r, "success", False)

        # ------------------------------------------------------------------
        # check_refund_eligibility
        # ------------------------------------------------------------------
        print("\n[check_refund_eligibility]")

        r = check_refund_eligibility("ORD007", db)   # Scenario C: CANCELLED + REFUNDED
        _run("ORD007 eligibility check succeeds", r, "success", True)
        _run("ORD007 already refunded -> not eligible", r, "eligible", False)

        r = check_refund_eligibility("ORD002", db)   # DELIVERED -> not eligible
        _run("ORD002 (DELIVERED) not eligible for refund", r, "eligible", False)

        r = check_refund_eligibility("ORD005", db)   # PENDING order -> not eligible
        _run("ORD005 (PENDING order) not eligible for refund", r, "eligible", False)

        # ------------------------------------------------------------------
        # check_delivery
        # ------------------------------------------------------------------
        print("\n[check_delivery]")

        r = check_delivery("ORD009", db)     # Scenario D: DELAYED
        _run("ORD009 delivery found", r, "success", True)
        _run("ORD009 delivery status is DELAYED", r, "status", "DELAYED")

        r = check_delivery("ORD002", db)     # Scenario B: DELIVERED
        _run("ORD002 delivery found", r, "success", True)
        _run("ORD002 delivery status is DELIVERED", r, "status", "DELIVERED")

        r = check_delivery("ORD007", db)     # CANCELLED order -- no delivery record
        _run("ORD007 (CANCELLED) has no delivery record", r, "success", False)

        # ------------------------------------------------------------------
        # check_account
        # ------------------------------------------------------------------
        print("\n[check_account]")

        r = check_account("C101", db)
        _run("C101 found", r, "success", True)
        _run("C101 name is Aarav Sharma", r, "name", "Aarav Sharma")
        _run("C101 account_status is active", r, "account_status", "active")

        r = check_account("C_NONEXISTENT", db)
        _run("Non-existent customer returns success=False", r, "success", False)

        # ------------------------------------------------------------------
        # cancel_order
        # Use ORD001 (CONFIRMED) -- safe to cancel.
        # If already cancelled from a previous run, the tool returns
        # success=False with a clear message; we assert that gracefully.
        # ------------------------------------------------------------------
        print("\n[cancel_order]")

        r = check_order("ORD001", db)
        current_status = r.get("status", "")

        if current_status == "CANCELLED":
            # Already cancelled from a previous test run
            r2 = cancel_order("ORD001", db)
            _run("ORD001 already CANCELLED -> success=False", r2, "success", False)
            print("         (ORD001 was previously cancelled -- idempotency confirmed)")
        else:
            r2 = cancel_order("ORD001", db)
            _run("ORD001 cancelled successfully", r2, "success", True)
            _run("ORD001 new status is CANCELLED", r2, "status", "CANCELLED")

        # Attempt to cancel a DELIVERED order -> must be rejected
        r = cancel_order("ORD002", db)
        _run("ORD002 (DELIVERED) cannot be cancelled", r, "success", False)

        # Attempt to cancel a non-existent order
        r = cancel_order("ORD_NONEXISTENT", db)
        _run("Non-existent order cancel returns success=False", r, "success", False)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total = _passed + _failed
        print(f"\n========================================")
        print(f"  Results: {_passed}/{total} passed, {_failed} failed")
        print(f"========================================\n")

        if _failed > 0:
            sys.exit(1)

    except Exception as exc:
        print(f"\nFATAL ERROR during tests: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
