"""
backend/test_api.py -- FastAPI router integration tests for Support Resolution API Layer (Task 3).

Run from project root:
    .venv\\Scripts\\python.exe -m backend.test_api

Or via pytest:
    .venv\\Scripts\\python.exe -m pytest backend/test_api.py -v
"""

import sys
from typing import Any
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.models.return_request import Return
from backend.models.replacement import Replacement

client = TestClient(app)

_passed = 0
_failed = 0


def _assert(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        print(f"  [PASS] {label}")
        _passed += 1
    else:
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))
        _failed += 1


def run_tests() -> None:
    print("\n==============================================")
    print("  SupportFlow AI -- Task 3 FastAPI API Tests")
    print("==============================================\n")

    # Clean up test returns/replacements for clean isolation
    db = SessionLocal()
    try:
        db.query(Return).filter(Return.order_id.in_(["ORD002", "ORD004"])).delete()
        db.query(Replacement).filter(Replacement.order_id.in_(["ORD002", "ORD004"])).delete()
        db.commit()
    finally:
        db.close()

    # ------------------------------------------------------------------
    # 1. Health Endpoints
    # ------------------------------------------------------------------
    print("[Health Endpoints]")
    r = client.get("/health")
    _assert("/health status 200", r.status_code == 200)

    r_db = client.get("/db-health")
    _assert("/db-health status 200", r_db.status_code == 200)

    # ------------------------------------------------------------------
    # 2. Refund API
    # ------------------------------------------------------------------
    print("\n[Refund API]")

    # GET /api/refunds/eligibility/{order_id}
    r = client.get("/api/refunds/eligibility/ORD007")
    _assert("GET refund eligibility ORD007 status 200", r.status_code == 200)
    _assert("ORD007 eligible is False (already refunded)", r.json().get("eligible") is False)

    r_404 = client.get("/api/refunds/eligibility/ORD_NONEXISTENT")
    _assert("GET refund eligibility nonexistent status 404", r_404.status_code == 404)

    # POST /api/refunds (Pydantic validation: empty order_id -> 422)
    r_val = client.post("/api/refunds", json={"order_id": ""})
    _assert("POST refund empty order_id returns 422", r_val.status_code == 422)

    # POST /api/refunds (Already refunded ORD001 -> 200 OK already_refunded)
    r_proc = client.post("/api/refunds", json={"order_id": "ORD001", "reason": "Already processed check"})
    _assert("POST refund ORD001 status 200", r_proc.status_code == 200)
    _assert("POST refund ORD001 already_refunded is True", r_proc.json().get("already_refunded") is True)

    # GET /api/refunds/{identifier}
    r_ver = client.get("/api/refunds/ORD001")
    _assert("GET verify refund ORD001 status 200", r_ver.status_code == 200)
    _assert("GET verify refund ORD001 order_id matches", r_ver.json().get("order_id") == "ORD001")

    r_ver_404 = client.get("/api/refunds/RFD_NONEXISTENT")
    _assert("GET verify refund nonexistent status 404", r_ver_404.status_code == 404)

    # ------------------------------------------------------------------
    # 3. Return API
    # ------------------------------------------------------------------
    print("\n[Return API]")

    # GET /api/returns/eligibility/{order_id}
    r = client.get("/api/returns/eligibility/ORD002")
    _assert("GET return eligibility ORD002 status 200", r.status_code == 200)
    _assert("ORD002 return eligible is True", r.json().get("eligible") is True)

    r_pend = client.get("/api/returns/eligibility/ORD005")
    _assert("ORD005 return eligible is False", r_pend.json().get("eligible") is False)

    # POST /api/returns (Pydantic validation: empty order_id -> 422)
    r_val = client.post("/api/returns", json={"order_id": ""})
    _assert("POST return empty order_id returns 422", r_val.status_code == 422)

    # POST /api/returns (Create return for ORD002 -> 201 Created)
    r_create = client.post("/api/returns", json={"order_id": "ORD002", "customer_id": "C102", "reason": "Damaged screen"})
    _assert("POST return create status 201", r_create.status_code == 201)
    _assert("POST return created is True", r_create.json().get("created") is True)
    _assert("POST return initial status is REQUESTED", r_create.json().get("status") == "REQUESTED")

    # POST /api/returns duplicate attempt -> 201 already_exists
    r_dup = client.post("/api/returns", json={"order_id": "ORD002", "customer_id": "C102"})
    _assert("POST return duplicate status 201", r_dup.status_code == 201)
    _assert("POST return duplicate already_exists is True", r_dup.json().get("already_exists") is True)

    # GET /api/returns/{identifier}
    r_ver = client.get("/api/returns/ORD002")
    _assert("GET verify return ORD002 status 200", r_ver.status_code == 200)
    _assert("GET verify return status is REQUESTED", r_ver.json().get("status") == "REQUESTED")

    r_ver_404 = client.get("/api/returns/RET_NONEXISTENT")
    _assert("GET verify return nonexistent status 404", r_ver_404.status_code == 404)

    # ------------------------------------------------------------------
    # 4. Replacement API
    # ------------------------------------------------------------------
    print("\n[Replacement API]")

    # GET /api/replacements/eligibility/{order_id}
    r = client.get("/api/replacements/eligibility/ORD002")
    _assert("GET replacement eligibility ORD002 status 200", r.status_code == 200)
    _assert("ORD002 replacement eligible is True", r.json().get("eligible") is True)

    # POST /api/replacements (Pydantic validation: empty order_id -> 422)
    r_val = client.post("/api/replacements", json={"order_id": ""})
    _assert("POST replacement empty order_id returns 422", r_val.status_code == 422)

    # POST /api/replacements (Create replacement for ORD002 -> 201 Created)
    r_create = client.post("/api/replacements", json={"order_id": "ORD002", "customer_id": "C102", "product_id": "P004", "reason": "Flickering screen"})
    _assert("POST replacement create status 201", r_create.status_code == 201)
    _assert("POST replacement created is True", r_create.json().get("created") is True)
    _assert("POST replacement status is REQUESTED", r_create.json().get("status") == "REQUESTED")

    # POST /api/replacements duplicate attempt -> 201 already_exists
    r_dup = client.post("/api/replacements", json={"order_id": "ORD002"})
    _assert("POST replacement duplicate status 201", r_dup.status_code == 201)
    _assert("POST replacement duplicate already_exists is True", r_dup.json().get("already_exists") is True)

    # GET /api/replacements/{identifier}
    r_ver = client.get("/api/replacements/ORD002")
    _assert("GET verify replacement ORD002 status 200", r_ver.status_code == 200)
    _assert("GET verify replacement status is REQUESTED", r_ver.json().get("status") == "REQUESTED")

    r_ver_404 = client.get("/api/replacements/REP_NONEXISTENT")
    _assert("GET verify replacement nonexistent status 404", r_ver_404.status_code == 404)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = _passed + _failed
    print(f"\n==============================================")
    print(f"  Results: {_passed}/{total} passed, {_failed} failed")
    print(f"==============================================\n")

    if _failed > 0:
        sys.exit(1)


def test_api_suite():
    run_tests()


if __name__ == "__main__":
    run_tests()
