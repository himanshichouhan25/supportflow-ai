"""
backend/test_replacement.py -- Comprehensive test suite for Task 2C Replacement Processing.

Run from the project root:
    .venv\\Scripts\\python.exe -m backend.test_replacement

Or via pytest:
    .venv\\Scripts\\python.exe -m pytest backend/test_replacement.py -v
"""

import sys
from typing import Any

from backend.database import SessionLocal
from backend.models.replacement import Replacement
from tools.replacement_tool import (
    check_replacement_eligibility,
    create_replacement_request,
    verify_replacement,
)
from agents.replacement_agent import run as replacement_agent
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
        print("\n==============================================")
        print("  SupportFlow AI -- Task 2C Replacement Tests")
        print("==============================================\n")

        # ------------------------------------------------------------------
        # 1. Eligibility Tests (1-4)
        # ------------------------------------------------------------------
        print("[Eligibility Tests (1-4)]")

        # 1. Delivered order -> eligible
        r1 = check_replacement_eligibility("ORD002", db)
        _run("1. Delivered order ORD002 is eligible", r1, "eligible", True)

        # 2. Pending order -> rejected
        r2 = check_replacement_eligibility("ORD005", db)
        _run("2. Pending order ORD005 is not eligible", r2, "eligible", False)

        # 3. Cancelled order -> rejected
        r3 = check_replacement_eligibility("ORD001", db)
        _run("3. Cancelled order ORD001 is not eligible", r3, "eligible", False)

        # 4. Nonexistent order -> rejected
        r4 = check_replacement_eligibility("ORD_NONEXISTENT", db)
        _run("4. Nonexistent order returns success=False", r4, "success", False)

        # ------------------------------------------------------------------
        # 2. Creation & Verification Tests (5-9, 14-16)
        # ------------------------------------------------------------------
        print("\n[Creation & Verification Tests (5-9, 14-16)]")

        # Clean up existing test replacements for test isolation
        db.query(Replacement).filter(Replacement.order_id.in_(["ORD002", "ORD004", "ORD008"])).delete()
        db.commit()

        # 5. Valid replacement request -> creates record
        res5 = create_replacement_request("ORD002", db, reason="Screen flickering")
        _run("5. Valid replacement request creates record", res5, "created", True)

        # 6. Correct initial status -> REQUESTED
        _run("6. Initial status is REQUESTED", res5, "status", "REQUESTED")

        # 7 & 8. Customer & Product relationship
        _run("7. Customer ID populated", res5, "customer_id", "C102")
        _run("8. Product ID populated", res5, "product_id", "P004")

        # 9. Replacement ID generated correctly
        rep_id = res5.get("replacement_id", "")
        _run_truthy("9. Replacement ID generated (e.g. REP0001)", rep_id.startswith("REP"))

        # 14. Verify by replacement ID
        v14 = verify_replacement(rep_id, db)
        _run("14. Verify by replacement ID succeeds", v14, "success", True)
        _run("14. Verified order_id matches", v14, "order_id", "ORD002")

        # 15. Verify by order ID
        v15 = verify_replacement("ORD002", db)
        _run("15. Verify by order ID succeeds", v15, "success", True)
        _run("15. Verified replacement_id matches", v15, "replacement_id", rep_id)

        # 16. Missing replacement -> clear failure
        v16 = verify_replacement("REP9999", db)
        _run("16. Nonexistent replacement returns success=False", v16, "success", False)

        # ------------------------------------------------------------------
        # 3. Duplicate Protection (10-11)
        # ------------------------------------------------------------------
        print("\n[Duplicate Protection (10-11)]")

        # 10. Same order active replacement -> no duplicate
        dup = create_replacement_request("ORD002", db, reason="Duplicate request attempt")
        _run("10. Duplicate request creation prevented", dup, "created", False)
        _run("10. already_exists is True", dup, "already_exists", True)

        # 11. Existing replacement returned
        _run("11. Existing replacement ID returned", dup, "replacement_id", rep_id)

        # ------------------------------------------------------------------
        # 4. Ownership & Security (12-13)
        # ------------------------------------------------------------------
        print("\n[Ownership & Security (12-13)]")

        # 12. Wrong customer -> rejected
        res12 = create_replacement_request("ORD004", db, customer_id="C101", product_id="P005", reason="Wrong customer")
        _run("12. Wrong customer ID rejected", res12, "success", False)

        # 13. Product not belonging to order -> rejected
        res13 = create_replacement_request("ORD004", db, customer_id="C104", product_id="P001", reason="Wrong product")
        _run("13. Wrong product ID rejected", res13, "success", False)

        # Correct customer & product for ORD004 (C104, P005)
        res_valid = create_replacement_request("ORD004", db, customer_id="C104", product_id="P005", reason="Valid request")
        _run("Valid request with matching customer & product succeeds", res_valid, "created", True)

        # ------------------------------------------------------------------
        # 5. Coordinator Integration & Collision Checks (17-20)
        # ------------------------------------------------------------------
        print("\n[Coordinator Integration & Collision Checks (17-20)]")

        # 17. Replacement intent routes to ReplacementAgent
        c17 = run_coordinator("I want a replacement for order ORD008 because the product is defective.", db)
        _run("17. Coordinator routes replacement intent", c17, "success", True)
        _run("17. Primary intent is replacement", c17, "intent", "replacement")

        # 18. Missing order ID produces clarification
        c18 = run_coordinator("I want a replacement for my product.", db)
        _run("18. Missing order ID -> success True", c18, "success", True)
        _run_truthy("18. Requests order ID clarification", "order id" in c18.get("final_response", "").lower())

        # 19. Return request still routes to ReturnAgent ("I want to return my damaged product")
        c19 = run_coordinator("I want to return my damaged product for order ORD002.", db)
        _run("19. Return request routes to return intent", c19, "intent", "return")

        # 20. Refund request still routes to PaymentAgent
        c20 = run_coordinator("Cancel order ORD007 and check whether I can get a refund.", db)
        _run("20. Refund request routes to payment intent", c20, "intent", "payment")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total = _passed + _failed
        print(f"\n==============================================")
        print(f"  Results: {_passed}/{total} passed, {_failed} failed")
        print(f"==============================================\n")

        if _failed > 0:
            sys.exit(1)

    except Exception as exc:
        print(f"\nFATAL ERROR during replacement tests: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


def test_replacement_suite() -> None:
    run_tests()


if __name__ == "__main__":
    run_tests()
