"""
backend/test_return.py -- Integration tests for Return processing (Task 2B).

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.test_return

Uses the existing SQLAlchemy SessionLocal.
Safe to rerun multiple times.
"""

import sys
from typing import Any

from backend.database import SessionLocal
from backend.models.return_request import Return
from tools.return_tool import (
    check_return_eligibility,
    create_return_request,
    verify_return,
)
from agents.return_agent import run as return_agent
from agents.coordinator import run_coordinator

_passed = 0
_failed = 0


def _run(label: str, result: dict[str, Any], expect_key: str, expect_value: Any) -> None:
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


def _run_truthy(label: str, value: Any) -> None:
    global _passed, _failed
    if value:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label} (value was {value!r})")
        _failed += 1


def run_tests() -> None:
    db = SessionLocal()
    try:
        print("\n========================================")
        print("  SupportFlow AI -- Task 2B Return Tests")
        print("========================================\n")

        # ------------------------------------------------------------------
        # 1. check_return_eligibility
        # ------------------------------------------------------------------
        print("[check_return_eligibility]")

        # ORD002 is DELIVERED -> eligible
        r = check_return_eligibility("ORD002", db)
        _run("ORD002 (DELIVERED) is eligible", r, "eligible", True)
        _run("ORD002 success is True", r, "success", True)

        # ORD005 is PENDING -> not eligible
        r = check_return_eligibility("ORD005", db)
        _run("ORD005 (PENDING) not eligible", r, "eligible", False)

        # ORD001 is CANCELLED -> not eligible
        r = check_return_eligibility("ORD001", db)
        _run("ORD001 (CANCELLED) not eligible", r, "eligible", False)

        # Non-existent order
        r = check_return_eligibility("ORD_FAKE", db)
        _run("Non-existent order -> success=False", r, "success", False)

        # ------------------------------------------------------------------
        # 2. create_return_request & verify_return
        # ------------------------------------------------------------------
        print("\n[create_return_request & verify_return]")

        # Clean up existing test returns for ORD002 & ORD004 if re-running
        db.query(Return).filter(Return.order_id.in_(["ORD002", "ORD004", "ORD008"])).delete()
        db.commit()

        # TEST 1: Create return for DELIVERED order ORD002
        res1 = create_return_request("ORD002", db, reason="Defective item")
        _run("TEST 1: Return created for ORD002", res1, "created", True)
        _run("TEST 1: Initial status is REQUESTED", res1, "status", "REQUESTED")
        _run_truthy("TEST 1: return_id generated", res1.get("return_id"))
        _run_truthy("TEST 1: created_at populated", res1.get("created_at"))

        # TEST 2: Verify return query
        ret_id = res1.get("return_id", "")
        ver = verify_return(ret_id, db)
        _run("TEST 2: verify_return finds record", ver, "success", True)
        _run("TEST 2: order_id matches", ver, "order_id", "ORD002")
        _run("TEST 2: status is REQUESTED", ver, "status", "REQUESTED")

        # TEST 3: Duplicate Return Protection (Step 4)
        dup = create_return_request("ORD002", db, reason="Duplicate attempt")
        _run("TEST 3: Duplicate return creation prevented", dup, "created", False)
        _run("TEST 3: already_exists is True", dup, "already_exists", True)
        _run("TEST 3: Existing return_id returned", dup, "return_id", ret_id)

        # TEST 4: Ownership verification check (Step 9)
        # ORD004 belongs to C102. Trying to return with C101 customer_id must fail.
        own_fail = create_return_request("ORD004", db, customer_id="C101", reason="Wrong customer")
        _run("TEST 4: Ownership mismatch rejected", own_fail, "success", False)

        # Correct ownership for ORD004 (C104)
        own_pass = create_return_request("ORD004", db, customer_id="C104", reason="Disliked color")
        _run("TEST 4: Correct ownership succeeds", own_pass, "created", True)

        # ------------------------------------------------------------------
        # 3. ReturnAgent
        # ------------------------------------------------------------------
        print("\n[ReturnAgent]")

        r = return_agent("I want to return order ORD008", db)
        _run("ReturnAgent name", r, "agent", "ReturnAgent")
        _run("ReturnAgent action is create_return_request", r, "action", "create_return_request")
        _run("ReturnAgent tool_result created is True", r["tool_result"], "created", True)
        _run("ReturnAgent initial status is REQUESTED", r["tool_result"], "status", "REQUESTED")

        # Duplicate attempt via agent
        r_dup = return_agent("I want to return order ORD008", db)
        _run("ReturnAgent duplicate tool_result already_exists is True", r_dup["tool_result"], "already_exists", True)

        # Missing order ID
        r_no_id = return_agent("I need to return my item", db)
        _run("ReturnAgent missing ID -> action is None", r_no_id, "action", None)

        # ------------------------------------------------------------------
        # 4. CoordinatorAgent Integration
        # ------------------------------------------------------------------
        print("\n[CoordinatorAgent Return Routing]")

        coord_res = run_coordinator("I want to return order ORD002.", db)
        _run("Coordinator handles return request", coord_res, "success", True)
        _run("Primary intent is return", coord_res, "intent", "return")
        _run_truthy("Final response contains return info", "return" in coord_res.get("final_response", "").lower())

        # Return request without order ID -> clarification needed
        coord_clar = run_coordinator("I want to return my product.", db)
        _run("Coordinator missing order ID -> success True", coord_clar, "success", True)
        _run_truthy("Coordinator requests order ID clarification", "order id" in coord_clar.get("final_response", "").lower())

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
        print(f"\nFATAL ERROR during return tests: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


def test_return_suite():
    run_tests()


if __name__ == "__main__":
    run_tests()
