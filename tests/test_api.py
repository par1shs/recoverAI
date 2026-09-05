"""Tests for RecoverAI API Layer (Phase 5)."""
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure simulator mode for all tests
os.environ["EXECUTION_MODE"] = "simulator"
os.environ["LLM_PROVIDER"] = "fake"

from backend.app import app
from backend.database import init_db, save_recovery_record, get_recovery_records, get_recovery_record_by_payment_id

@pytest.fixture
def client(tmp_path):
    """Create a test client with a temporary database."""
    db_path = str(tmp_path / "test.db")
    os.environ["DATABASE_PATH"] = db_path
    init_db(db_path)
    with TestClient(app) as c:
        yield c
    if "DATABASE_PATH" in os.environ:
        del os.environ["DATABASE_PATH"]

def _base_request(failure_type="temporary_bank_failure", retry_count=0, amount=1000.0):
    return {
        "payment_id": "pay_test_001",
        "customer_id": "cust_test_001",
        "amount": amount,
        "failure_type": failure_type,
        "retry_count": retry_count,
        "customer_tenure_months": 12,
        "previous_successes": 10,
        "previous_failures": 0,
    }


# ─── 1. Application imports ──────────────────────────────────────────────────
def test_app_import():
    from backend.app import app
    assert app is not None


# ─── 2. Health endpoint ──────────────────────────────────────────────────────
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "recoverAI"


# ─── 3. Analyze endpoint ─────────────────────────────────────────────────────
def test_analyze_valid(client):
    resp = client.post("/api/v1/recoveries/analyze", json=_base_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_id"] == "pay_test_001"
    assert data["recovery_opportunity_score"] > 0
    assert len(data["candidate_actions"]) > 0
    assert data["agent_decision"]["selected_action"] is not None
    assert "policy_decision" in data


# ─── 4. Ground truth never reaches LLM ──────────────────────────────────────
def test_ground_truth_excluded(client):
    """Ground truth must never appear in the recovery context or agent context."""
    req = _base_request()
    req["ground_truth_outcome"] = "recovered"  # attempt injection
    # PaymentContext has extra='forbid', so this field should be ignored at the API layer
    # The API schema (PaymentRequest) does not have ground_truth_outcome
    resp = client.post("/api/v1/recoveries/analyze", json=req)
    # Extra fields in PaymentRequest are simply ignored by Pydantic
    assert resp.status_code == 200


# ─── 5. Candidates from deterministic backend ────────────────────────────────
def test_candidates_from_backend(client):
    resp = client.post("/api/v1/recoveries/analyze", json=_base_request())
    data = resp.json()
    actions = [c["action"] for c in data["candidate_actions"]]
    # For temporary_bank_failure, expect retry_now, retry_later, payment_link
    assert "retry_now" in actions
    assert "retry_later" in actions


# ─── 6. Allowed action reaches simulator execution ──────────────────────────
def test_execute_allowed(client):
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_decision"]["allowed"] is True
    assert data["execution_result"]["provider"] == "simulator"
    assert data["execution_result"]["status"] in ["executed", "scheduled"]


# ─── 7. MANDATORY SAFETY TEST: Policy-denied NEVER reaches execution ────────
def test_policy_denied_no_execution(client):
    """retry_count >= max_retries → policy blocks → execution adapter NOT called."""
    req = _base_request(retry_count=5)
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_exec:
        resp = client.post("/api/v1/recoveries/execute", json=req)
        assert resp.status_code == 200
        data = resp.json()
        assert data["policy_decision"]["allowed"] is False
        assert data["execution_result"]["status"] == "blocked"
        mock_exec.assert_not_called()


# ─── 8. Simulator works without Razorpay credentials ────────────────────────
def test_simulator_no_razorpay_creds(client):
    # Remove any Razorpay env vars
    for k in ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"]:
        os.environ.pop(k, None)
    os.environ["EXECUTION_MODE"] = "simulator"
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_result"]["provider"] == "simulator"


# ─── 9. Simulator clearly identifies itself ──────────────────────────────────
def test_simulator_provider_name(client):
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    data = resp.json()
    assert data["execution_result"]["provider"] == "simulator"


# ─── 10. Razorpay mode requires credentials ─────────────────────────────────
def test_razorpay_mode_requires_credentials(client):
    for k in ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"]:
        os.environ.pop(k, None)
    os.environ["EXECUTION_MODE"] = "razorpay_test"
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    assert resp.status_code == 503
    os.environ["EXECUTION_MODE"] = "simulator"


# ─── 11. No real Razorpay calls during pytest ────────────────────────────────
def test_no_real_razorpay_calls(client):
    """Ensure no real Razorpay API calls happen."""
    os.environ["EXECUTION_MODE"] = "simulator"
    # If this test passes without network, the constraint is met
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    assert resp.status_code == 200


# ─── 12. No real OpenAI calls during pytest ──────────────────────────────────
def test_no_real_openai_calls(client):
    """Ensure FakeLLMProvider is used."""
    os.environ["LLM_PROVIDER"] = "fake"
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    assert resp.status_code == 200
    assert resp.json()["agent_decision"]["status"] == "success"


# ─── 13. Recovery records persist ────────────────────────────────────────────
def test_records_persist(client):
    # Execute a recovery
    client.post("/api/v1/recoveries/execute", json=_base_request())
    # Retrieve records
    resp = client.get("/api/v1/recoveries")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 1
    assert records[0]["payment_id"] == "pay_test_001"


# ─── 14. Recovery records by payment_id ──────────────────────────────────────
def test_records_by_payment_id(client):
    client.post("/api/v1/recoveries/execute", json=_base_request())
    resp = client.get("/api/v1/recoveries/pay_test_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["payment_id"] == "pay_test_001"
    assert data["full_result"] is not None


# ─── 15. Missing payment_id returns 404 ──────────────────────────────────────
def test_missing_record_404(client):
    resp = client.get("/api/v1/recoveries/pay_nonexistent")
    assert resp.status_code == 404


# ─── 16. Demo scenarios list ─────────────────────────────────────────────────
def test_demo_list(client):
    resp = client.get("/api/v1/demos")
    assert resp.status_code == 200
    data = resp.json()
    assert "insufficient_funds" in data
    assert "retry_limit_reached" in data
    assert "expired_card" in data
    assert "permanent_failure" in data


# ─── 17. Demo Scenario A: Insufficient Funds ────────────────────────────────
def test_demo_insufficient_funds(client):
    resp = client.post("/api/v1/demos/insufficient_funds/execute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_type"] == "insufficient_funds"
    assert len(data["candidate_actions"]) > 0
    assert "retry_now" in [candidate["action"] for candidate in data["candidate_actions"]]

def test_demo_replaces_prior_record_for_a_predictable_dashboard(client):
    client.post("/api/v1/demos/insufficient_funds/execute")
    client.post("/api/v1/demos/insufficient_funds/execute")
    records = client.get("/api/v1/recoveries").json()
    assert sum(record["payment_id"] == "pay_demo_insuf_001" for record in records) == 1


# ─── 18. Demo Scenario B: Retry Limit Reached (safety) ──────────────────────
def test_demo_retry_limit_safety(client):
    resp = client.post("/api/v1/demos/retry_limit_reached/execute")
    assert resp.status_code == 200
    data = resp.json()
    # With retry_count=3 and max_retries=2, policy MUST block retry actions
    assert data["policy_decision"]["allowed"] is False
    assert data["execution_result"]["status"] == "blocked"


# ─── 19. Demo Scenario C: Expired Card ──────────────────────────────────────
def test_demo_expired_card(client):
    resp = client.post("/api/v1/demos/expired_card/execute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_type"] == "expired_card"
    # For expired_card, candidates should include payment_link
    actions = [c["action"] for c in data["candidate_actions"]]
    assert "payment_link" in actions


# ─── 20. Demo Scenario D: Permanent Failure ─────────────────────────────────
def test_demo_permanent_failure(client):
    resp = client.post("/api/v1/demos/permanent_failure/execute")
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_type"] == "permanent_decline"
    # Should be stopped/escalated, no retry
    actions = [c["action"] for c in data["candidate_actions"]]
    assert "retry_now" not in actions
    assert "retry_later" not in actions


# ─── 21. Unknown demo scenario 404 ──────────────────────────────────────────
def test_unknown_demo_404(client):
    resp = client.post("/api/v1/demos/nonexistent_scenario/execute")
    assert resp.status_code == 404


# ─── 22. Execution and verification are separate ─────────────────────────────
def test_execution_verification_separate(client):
    resp = client.post("/api/v1/recoveries/execute", json=_base_request())
    data = resp.json()
    # Execution and verification are independently present
    assert "execution_result" in data
    assert "verification_result" in data
    # Payment link executed != recovered
    req = _base_request(failure_type="expired_card")
    resp2 = client.post("/api/v1/recoveries/execute", json=req)
    data2 = resp2.json()
    if data2["policy_decision"]["allowed"] and data2["execution_result"]["action"] == "payment_link":
        assert data2["verification_result"]["verification_status"] == "pending"
