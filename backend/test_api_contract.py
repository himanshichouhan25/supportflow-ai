"""
backend/test_api_contract.py — Integration and API Contract Tests for FastAPI & Streamlit Service layer.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models.replacement import Replacement
from backend.models.return_request import Return
from backend.models.refund import Refund

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_db():
    db = SessionLocal()
    try:
        db.query(Replacement).filter(Replacement.order_id.in_(["ORD004", "ORD002"])).delete()
        db.query(Return).filter(Return.order_id.in_(["ORD009"])).delete()
        db.query(Refund).filter(Refund.order_id.in_(["ORD006"])).delete()
        db.commit()
    finally:
        db.close()


def test_api_contract_valid_support_request():
    """Test valid support request endpoint returns expected structure."""
    payload = {
        "message": "Tell me about my order ORD004.",
        "session_id": "test-session-contract-001"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "final_status" in data
    assert "session_id" in data
    assert data["session_id"] == "test-session-contract-001"
    assert "workflow_plan" in data
    assert "workflow_trace" in data
    assert isinstance(data["workflow_trace"], list)


def test_api_contract_missing_required_message():
    """Test request without message returns validation error (HTTP 422)."""
    payload = {
        "session_id": "test-session-contract-002"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 422


def test_api_contract_invalid_order_id():
    """Test resolution with an invalid order ID returns escalation context safely."""
    payload = {
        "message": "I want a refund for order ORD99999",
        "session_id": "test-session-contract-003"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["final_status"] in ["ESCALATED", "NEEDS_CLARIFICATION"]
    assert "workflow_trace" in data


def test_api_contract_successful_replacement():
    """Test replacement workflow via FastAPI endpoint."""
    payload = {
        "message": "My product is damaged. I want a replacement for ORD004.",
        "session_id": "test-session-contract-004",
        "order_id": "ORD004"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["final_status"] == "RESOLVED"
    assert data["workflow_plan"] is not None
    assert len(data["workflow_trace"]) > 0


def test_api_contract_ineligible_return():
    """Test ineligible return request produces escalation with ticket context."""
    payload = {
        "message": "Return ORD009 and tell me why it cannot be returned.",
        "session_id": "test-session-contract-005"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["final_status"] == "ESCALATED"
    assert data.get("ticket") is not None or data.get("ticket_id") is not None


def test_api_contract_clarification_response():
    """Test ambiguous request requires clarification."""
    payload = {
        "message": "I want to cancel that order",
        "session_id": "test-session-contract-006"
    }
    response = client.post("/api/support/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["final_status"] == "NEEDS_CLARIFICATION" or data.get("clarification_needed") is True


def test_api_contract_session_preservation():
    """Test session_id is preserved across multi-turn requests."""
    session_id = "test-session-preservation-123"
    
    res1 = client.post("/api/support/resolve", json={
        "message": "Tell me about order ORD004.",
        "session_id": session_id
    })
    assert res1.status_code == 200
    assert res1.json()["session_id"] == session_id

    res2 = client.post("/api/support/resolve", json={
        "message": "I want a replacement for it.",
        "session_id": session_id
    })
    assert res2.status_code == 200
    assert res2.json()["session_id"] == session_id


def test_api_contract_products_endpoint():
    """Test GET /api/products returns list of products."""
    res = client.get("/api/products")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "product_id" in data[0]
        assert "name" in data[0]


def test_api_contract_orders_endpoint():
    """Test GET /api/orders returns customer orders."""
    res = client.get("/api/orders?email=aarav.sharma@example.com")
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert "orders" in data


def test_api_contract_tickets_endpoint():
    """Test GET /api/tickets returns list of support tickets."""
    res = client.get("/api/tickets")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_api_contract_dashboard_endpoint():
    """Test GET /api/dashboard/metrics returns operational metrics."""
    res = client.get("/api/dashboard/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "total_orders" in data
    assert "open_tickets" in data
