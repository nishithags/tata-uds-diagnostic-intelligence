"""
Unit and Integration Tests for Activity Store and Privacy Guardrails.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from pathlib import Path
import pytest
from src.core.activity_store import (
    ActivityAction,
    ActivityRecord,
    SQLiteActivityStore,
    process_client_ip,
    sanitize_sensitive_data,
)
from src.core.config import config


@pytest.fixture
def temp_activity_store(tmp_path: Path):
    """Provides a fresh isolated SQLiteActivityStore in a temporary directory."""
    db_file = tmp_path / "test_activity_store.db"
    store = SQLiteActivityStore(db_path=db_file)
    yield store


def test_activity_record_creation(temp_activity_store: SQLiteActivityStore):
    """Test standard activity record creation and field persistence."""
    rec = temp_activity_store.log_activity(
        session_id="sess_test_1001",
        action=ActivityAction.TEST_GENERATED,
        user_id="engineer_01",
        project_id="ws_bcm_test",
        endpoint="/api/v1/workspaces/ws_bcm_test/test-cases/generate",
        http_method="POST",
        test_case_id="TC_UDS_0x22_001",
        status="SUCCESS",
        http_status_code=201,
        duration_ms=12.4,
        metadata={"service_id": "0x22", "count": 1}
    )

    assert rec.event_id.startswith("act_")
    assert rec.session_id == "sess_test_1001"
    assert rec.user_id == "engineer_01"
    assert rec.is_authenticated is True
    assert rec.action == ActivityAction.TEST_GENERATED
    assert rec.duration_ms == 12.4
    assert rec.metadata.get("service_id") == "0x22"

    # Query from DB
    retrieved = temp_activity_store.get_event_by_id(rec.event_id)
    assert retrieved is not None
    assert retrieved.event_id == rec.event_id
    assert retrieved.test_case_id == "TC_UDS_0x22_001"
    assert retrieved.http_status_code == 201


def test_knowledge_query_logging_and_history(temp_activity_store: SQLiteActivityStore):
    """Test that KNOWLEDGE_QUERY records actual user query text and citation metrics."""
    temp_activity_store.log_activity(
        session_id="sess_alice_1",
        action=ActivityAction.KNOWLEDGE_QUERY,
        project_id="tata_uds_pilot",
        query_text="What is UDS service 0x22?",
        duration_ms=45.0,
        metadata={"citations_count": 6, "model": "llama-3.1-8b"}
    )
    temp_activity_store.log_activity(
        session_id="sess_bob_2",
        action=ActivityAction.KNOWLEDGE_QUERY,
        project_id="tata_uds_pilot",
        query_text="What is NRC 0x31?",
        duration_ms=32.1,
        metadata={"citations_count": 4, "model": "mock-v1"}
    )

    history = temp_activity_store.get_knowledge_query_history(project_id="tata_uds_pilot")
    assert len(history) == 2
    assert history[0]["query"] == "What is NRC 0x31?"  # Ordered DESC
    assert history[0]["result"] == "4 citations"
    assert history[1]["query"] == "What is UDS service 0x22?"
    assert history[1]["result"] == "6 citations"

    # Search filter
    filtered = temp_activity_store.get_knowledge_query_history(search_term="0x22")
    assert len(filtered) == 1
    assert filtered[0]["query"] == "What is UDS service 0x22?"


def test_session_id_generation_and_persistence(temp_activity_store: SQLiteActivityStore):
    """Verify session ID persistence across multiple actions."""
    sess_id = "sess_browser_unique_99"
    temp_activity_store.log_activity(session_id=sess_id, action=ActivityAction.KNOWLEDGE_QUERY, query_text="Q1")
    temp_activity_store.log_activity(session_id=sess_id, action=ActivityAction.TEST_GENERATED)
    temp_activity_store.log_activity(session_id=sess_id, action=ActivityAction.TEST_EXECUTED)

    events = temp_activity_store.get_events(session_id=sess_id)
    assert len(events) == 3
    for ev in events:
        assert ev.session_id == sess_id


def test_successful_and_failed_action_logging(temp_activity_store: SQLiteActivityStore):
    """Verify success and failure telemetry recording and aggregation."""
    temp_activity_store.log_activity(
        session_id="sess_1",
        action=ActivityAction.TEST_EXECUTED,
        status="SUCCESS",
        http_status_code=200
    )
    temp_activity_store.log_activity(
        session_id="sess_1",
        action=ActivityAction.TEST_EXECUTED,
        status="FAILURE",
        http_status_code=200,
        metadata={"verdict": "FAIL"}
    )
    temp_activity_store.log_activity(
        session_id="sess_1",
        action=ActivityAction.API_ERROR,
        status="ERROR",
        http_status_code=500,
        metadata={"error": "Database lock timeout"}
    )

    stats = temp_activity_store.get_summary_stats()
    assert stats["total_events"] == 3
    assert stats["success_count"] == 1
    assert stats["failure_count"] == 2  # 1 FAILURE + 1 ERROR
    assert stats["tests_executed_count"] == 2


def test_response_time_recording(temp_activity_store: SQLiteActivityStore):
    """Verify response duration is precisely captured in milliseconds."""
    rec = temp_activity_store.log_activity(
        session_id="sess_timing",
        action=ActivityAction.TEST_OPTIMIZED,
        duration_ms=189.734
    )
    assert rec.duration_ms == 189.73

    retrieved = temp_activity_store.get_event_by_id(rec.event_id)
    assert retrieved.duration_ms == 189.73


def test_filtering_capabilities(temp_activity_store: SQLiteActivityStore):
    """Verify multi-criteria filtering across workspaces, actions, and status."""
    temp_activity_store.log_activity(session_id="s1", project_id="ws_a", action=ActivityAction.TEST_GENERATED, status="SUCCESS")
    temp_activity_store.log_activity(session_id="s1", project_id="ws_b", action=ActivityAction.TEST_GENERATED, status="SUCCESS")
    temp_activity_store.log_activity(session_id="s2", project_id="ws_a", action=ActivityAction.DOCUMENT_UPLOAD, status="FAILURE")

    # Filter by project
    assert len(temp_activity_store.get_events(project_id="ws_a")) == 2
    assert len(temp_activity_store.get_events(project_id="ws_b")) == 1

    # Filter by action
    assert len(temp_activity_store.get_events(action=ActivityAction.DOCUMENT_UPLOAD)) == 1

    # Filter by status
    assert len(temp_activity_store.get_events(status="FAILURE")) == 1


def test_privacy_configuration_ip_logging(monkeypatch):
    """Verify client IP privacy configuration: zero collection by default, anonymized if enabled."""
    # Default: log_client_ip = False
    monkeypatch.setattr(config, "log_client_ip", False)
    assert process_client_ip("192.168.1.55") is None

    # Enabled with anonymization
    monkeypatch.setattr(config, "log_client_ip", True)
    monkeypatch.setattr(config, "anonymize_ip", True)
    assert process_client_ip("192.168.1.55") == "192.168.1.xxx"

    # Enabled without anonymization
    monkeypatch.setattr(config, "anonymize_ip", False)
    assert process_client_ip("192.168.1.55") == "192.168.1.55"


def test_prevention_of_secret_and_token_logging():
    """Verify that sensitive keys, passwords, bearer tokens, and credentials are redacted."""
    sensitive_payload = {
        "user": "lead_engineer",
        "password": "SuperSecretPassword123!",
        "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload",
        "api_key": "uds-secret-api-key-9999",
        "nested": {
            "client_secret": "my_client_secret_xyz",
            "safe_param": "0x22"
        },
        "header_val": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"
    }

    sanitized = sanitize_sensitive_data(sensitive_payload)

    assert sanitized["user"] == "lead_engineer"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["auth_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["client_secret"] == "[REDACTED]"
    assert sanitized["nested"]["safe_param"] == "0x22"
    assert "Bearer [REDACTED]" in sanitized["header_val"]


def test_identity_distinction_anonymous_vs_authenticated(temp_activity_store: SQLiteActivityStore):
    """Verify strict classification between anonymous sessions and authenticated users."""
    # Anonymous record (no user_id or "anonymous")
    anon_rec = temp_activity_store.log_activity(
        session_id="sess_anon_123",
        action=ActivityAction.KNOWLEDGE_QUERY,
        user_id=None
    )
    assert anon_rec.is_authenticated is False

    # Authenticated record
    auth_rec = temp_activity_store.log_activity(
        session_id="sess_auth_456",
        action=ActivityAction.TEST_REVIEWED,
        user_id="lead_specialist"
    )
    assert auth_rec.is_authenticated is True

    summary = temp_activity_store.get_summary_stats()
    assert summary["unique_anonymous_sessions"] == 1
    assert summary["unique_authenticated_users"] == 1
