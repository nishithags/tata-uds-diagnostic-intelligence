"""
Integration and Validation Tests for Phase 2 API Endpoints.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Tests:
- POST /api/v1/workspaces/{project_id}/test-cases/generate (Positive, Negative, Suite)
- GET /api/v1/workspaces/{project_id}/test-cases
- GET /api/v1/workspaces/{project_id}/test-cases/{id}
- POST /api/v1/workspaces/{project_id}/test-cases/{id}/review (Approve, Edit & Approve, Reject)
- POST /api/v1/workspaces/{project_id}/test-cases/{id}/assert-executable (Enforce 403 on unapproved)
- POST /api/v1/workspaces/{project_id}/test-cases/validate-custom (Custom frame rule checking)
- GET /api/v1/workspaces/{project_id}/audit-logs
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_workspace():
    """Ensure a test workspace exists for Phase 2 API tests."""
    ws_id = "test_phase2_api_ws"
    client.post("/api/v1/workspaces", json={
        "project_id": ws_id,
        "name": "Phase 2 Test Workspace",
        "description": "Integration testing for test generation & rule verification",
        "oem_name": "Tata Motors",
        "ecu_model": "BCM_GEN3"
    })
    return ws_id


class TestPhase2APIEndpoints:
    """Test suite for Phase 2 test generation, rule checking, and governance REST APIs."""

    def test_generate_positive_test_case_api(self, setup_workspace):
        """Verify generating a positive test case via API."""
        payload = {
            "service_id": 0x10,
            "test_scenario": "POSITIVE",
            "subfunction": 1,
            "session": "DEFAULT",
            "security": 0
        }
        resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        tc = data[0]
        assert tc["service_id"] == 0x10
        assert tc["rule_verification_status"] == "PASSED"
        assert tc["review_status"] == "PENDING_REVIEW"
        assert tc["rule_verification_report"]["overall_verdict"] == "PASS"

    def test_generate_negative_test_case_api(self, setup_workspace):
        """Verify generating a negative test case (invalid subfunction -> NRC 0x12) via API."""
        payload = {
            "service_id": 0x10,
            "test_scenario": "NEGATIVE_SUBFUNCTION",
            "session": "DEFAULT"
        }
        resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        tc = data[0]
        assert tc["test_type"] == "NEGATIVE_INVALID_SUBFUNCTION"
        assert tc["steps"][0]["expected_nrc"] == "0x12"
        assert tc["rule_verification_status"] == "PASSED"

    def test_generate_suite_api(self, setup_workspace):
        """Verify generating a complete test suite via API."""
        payload = {
            "service_id": 0x22,
            "test_scenario": "SUITE"
        }
        resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) >= 2  # Nominal + Negative length

    def test_list_and_get_test_cases_api(self, setup_workspace):
        """Verify listing and retrieving individual test cases."""
        list_resp = client.get(f"/api/v1/workspaces/{setup_workspace}/test-cases")
        assert list_resp.status_code == 200
        cases = list_resp.json()
        assert len(cases) > 0

        target_id = cases[0]["test_case_id"]
        get_resp = client.get(f"/api/v1/workspaces/{setup_workspace}/test-cases/{target_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["test_case_id"] == target_id

    def test_review_lifecycle_and_guardrail_enforcement_api(self, setup_workspace):
        """
        Verify:
        1. An unapproved test case is blocked from export/execution (HTTP 403).
        2. Submitting an approval review sets status to APPROVED (HTTP 200).
        3. The approved test case is permitted for export/execution (HTTP 200).
        """
        # Generate a fresh test case
        gen_resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/generate", json={
            "service_id": 0x3E,
            "test_scenario": "POSITIVE"
        })
        tc = gen_resp.json()[0]
        tc_id = tc["test_case_id"]
        assert tc["review_status"] == "PENDING_REVIEW"

        # 1. Attempt to execute unapproved test case -> Must be BLOCKED with 403
        exec_blocked_resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/assert-executable")
        assert exec_blocked_resp.status_code == 403
        assert "cannot be exported or executed" in exec_blocked_resp.json()["detail"]

        # 2. Submit formal approval review
        review_payload = {
            "reviewer_name": "A. Lead Engineer",
            "reviewer_role": "Diagnostic Validation Specialist",
            "action": "APPROVE",
            "comments": "Formally reviewed and approved for validation cycle."
        }
        review_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/review",
            json=review_payload
        )
        assert review_resp.status_code == 200
        updated_tc = review_resp.json()
        assert updated_tc["review_status"] == "APPROVED"

        # 3. Execution check now succeeds with HTTP 200
        exec_allowed_resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/assert-executable")
        assert exec_allowed_resp.status_code == 200
        assert exec_allowed_resp.json()["status"] == "ALLOWED"

    def test_custom_frame_rule_validation_api(self, setup_workspace):
        """Verify custom raw frame deterministic validation endpoint."""
        # Valid frame
        valid_payload = {
            "request_hex": "22 F1 90",
            "session": "DEFAULT",
            "security": 0,
            "expected_response_type": "POSITIVE"
        }
        resp = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/validate-custom", json=valid_payload)
        assert resp.status_code == 200
        assert resp.json()["overall_verdict"] == "PASS"

        # Invalid frame (missing subfunction for 0x10 in positive test)
        invalid_payload = {
            "request_hex": "10",
            "session": "DEFAULT",
            "security": 0,
            "expected_response_type": "POSITIVE"
        }
        resp_inv = client.post(f"/api/v1/workspaces/{setup_workspace}/test-cases/validate-custom", json=invalid_payload)
        assert resp_inv.status_code == 200
        assert resp_inv.json()["overall_verdict"] == "FAIL"

    def test_audit_logs_retrieval_api(self, setup_workspace):
        """Verify retrieval of workspace audit logs."""
        resp = client.get(f"/api/v1/workspaces/{setup_workspace}/audit-logs")
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) > 0
        event_types = [e["event_type"] for e in events]
        assert "TEST_GENERATED" in event_types
