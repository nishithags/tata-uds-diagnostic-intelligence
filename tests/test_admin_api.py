"""
Integration Tests for Admin Activity Endpoints and Middleware.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from fastapi.testclient import TestClient
import pytest
from src.api.main import app
from src.core.activity_store import ActivityAction, activity_store
from src.core.config import config


@pytest.fixture(autouse=True)
def setup_test_admin_key(monkeypatch):
    """Provides a safe isolated admin key during test execution."""
    test_key = "test-isolated-admin-key-2026"
    monkeypatch.setenv("UDS_ADMIN_KEY", test_key)
    config.admin_api_key = test_key
    yield
    config.admin_api_key = None


@pytest.fixture
def client():
    """Provides a TestClient for FastAPI."""
    return TestClient(app)


def test_admin_endpoints_require_authentication(client: TestClient):
    """Verify that admin activity endpoints are protected and reject unauthenticated requests."""
    # Without header
    resp = client.get("/api/v1/admin/activity")
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

    # With invalid key
    resp_invalid = client.get(
        "/api/v1/admin/activity",
        headers={"X-Admin-Key": "wrong-key"}
    )
    assert resp_invalid.status_code == 403

    # Summary without key
    resp_summary = client.get("/api/v1/admin/activity/summary")
    assert resp_summary.status_code == 403

    # Queries without key
    resp_queries = client.get("/api/v1/admin/activity/queries")
    assert resp_queries.status_code == 403

    # When server has no admin key configured at all
    current_key = config.admin_api_key
    try:
        config.admin_api_key = None
        resp_unconfigured = client.get("/api/v1/admin/activity", headers={"X-Admin-Key": "any-key"})
        assert resp_unconfigured.status_code == 403
        assert "not configured" in resp_unconfigured.json()["detail"]
    finally:
        config.admin_api_key = current_key


def test_admin_endpoints_accessible_with_valid_key(client: TestClient):
    """Verify authorized administrator access using configured X-Admin-Key."""
    # Seed an event
    activity_store.log_activity(
        session_id="sess_admin_test_1",
        action=ActivityAction.KNOWLEDGE_QUERY,
        query_text="What is UDS service 0x10?",
        metadata={"citations_count": 3}
    )

    # Via header
    resp = client.get(
        "/api/v1/admin/activity",
        headers={"X-Admin-Key": config.admin_api_key}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert data["total_count"] >= 1

    # Via query parameter
    resp_param = client.get(
        f"/api/v1/admin/activity/summary?admin_key={config.admin_api_key}"
    )
    assert resp_param.status_code == 200
    summary_data = resp_param.json()
    assert "total_events" in summary_data
    assert "unique_sessions" in summary_data


def test_api_middleware_session_id_propagation(client: TestClient):
    """Verify that requests receive or retain an anonymous X-Session-ID header."""
    # Without session header -> middleware generates one
    resp1 = client.get("/")
    assert resp1.status_code == 200
    generated_sess = resp1.headers.get("X-Session-ID")
    assert generated_sess is not None
    assert generated_sess.startswith("sess_")

    # With custom session header -> middleware retains it
    custom_sess = "sess_client_persisted_777"
    resp2 = client.get("/", headers={"X-Session-ID": custom_sess})
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Session-ID") == custom_sess


def test_admin_knowledge_query_history_api(client: TestClient):
    """Verify Knowledge Query History retrieval through protected admin API."""
    activity_store.log_activity(
        session_id="sess_q_test",
        action=ActivityAction.KNOWLEDGE_QUERY,
        project_id="tata_uds_pilot",
        query_text="Explain DID 0xF190 VIN reading",
        metadata={"citations_count": 5}
    )

    resp = client.get(
        "/api/v1/admin/activity/queries",
        headers={"X-Admin-Key": config.admin_api_key}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_queries"] >= 1
    found = any("0xF190" in q["query"] for q in data["queries"])
    assert found is True


def test_admin_activity_detail_api(client: TestClient):
    """Verify fetching single activity event detail by ID."""
    rec = activity_store.log_activity(
        session_id="sess_detail_test",
        action=ActivityAction.ECU_RESET,
        project_id="tata_uds_pilot",
        status="SUCCESS"
    )

    # Valid ID
    resp = client.get(
        f"/api/v1/admin/activity/{rec.event_id}",
        headers={"X-Admin-Key": config.admin_api_key}
    )
    assert resp.status_code == 200
    assert resp.json()["event_id"] == rec.event_id
    assert resp.json()["action"] == ActivityAction.ECU_RESET

    # Non-existent ID
    resp_404 = client.get(
        "/api/v1/admin/activity/act_nonexistent_9999",
        headers={"X-Admin-Key": config.admin_api_key}
    )
    assert resp_404.status_code == 404
