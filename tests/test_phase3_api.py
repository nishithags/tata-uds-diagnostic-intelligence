"""
Integration and Validation Tests for Phase 3 API Endpoints.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Tests:
- GET /api/v1/workspaces/{project_id}/ecu-state (Retrieve virtual ECU snapshot)
- POST /api/v1/workspaces/{project_id}/ecu-state/reset (Power-on reset)
- POST /api/v1/workspaces/{project_id}/test-cases/{id}/execute (Enforce 403 on unapproved, execute approved)
- POST /api/v1/workspaces/{project_id}/test-cases/{id}/execute with Fault Profile
- GET /api/v1/workspaces/{project_id}/execution-runs (List workspace runs)
- GET /api/v1/workspaces/{project_id}/execution-runs/{id} (Retrieve run by ID)
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_workspace():
    """Ensure a test workspace exists for Phase 3 API tests."""
    ws_id = "test_phase3_api_ws"
    client.post("/api/v1/workspaces", json={
        "project_id": ws_id,
        "name": "Phase 3 Test Workspace",
        "description": "Integration testing for simulated ECU & execution runner",
        "oem_name": "Tata Motors",
        "ecu_model": "BCM_GEN3"
    })
    return ws_id


class TestPhase3APIEndpoints:
    """Test suite for Phase 3 Simulated ECU and Controlled Execution REST APIs."""

    def test_get_ecu_state_api(self, setup_workspace):
        """Verify GET /ecu-state returns valid snapshot."""
        resp = client.get(f"/api/v1/workspaces/{setup_workspace}/ecu-state")
        assert resp.status_code == 200
        data = resp.json()
        assert "session" in data
        assert "security_level" in data
        assert "security_locked" in data
        assert "dtc_count" in data
        assert data["session"] in ("DEFAULT", "EXTENDED", "PROGRAMMING")

    def test_reset_ecu_state_api(self, setup_workspace):
        """Verify POST /ecu-state/reset restores power-on state."""
        resp = client.post(f"/api/v1/workspaces/{setup_workspace}/ecu-state/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"] == "DEFAULT"
        assert data["security_level"] == 0
        assert data["security_locked"] is True
        assert data["dtc_count"] == 3

    def test_execute_blocked_on_unapproved_test_case(self, setup_workspace):
        """Verify execution is strictly BLOCKED with HTTP 403 on unapproved test case."""
        # 1. Generate test case (default review_status is PENDING_REVIEW)
        gen_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/generate",
            json={
                "service_id": 0x10,
                "test_scenario": "POSITIVE",
                "subfunction": 1
            }
        )
        assert gen_resp.status_code == 201
        tc_id = gen_resp.json()[0]["test_case_id"]

        # 2. Attempt execution without approval -> MUST receive 403 Forbidden
        exec_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/execute",
            json={"operator_name": "Test Runner"}
        )
        assert exec_resp.status_code == 403
        assert "cannot be exported or executed" in exec_resp.json()["detail"]

    def test_execute_approved_test_case_api(self, setup_workspace):
        """Verify executing a formally approved test case yields HTTP 200 and PASS verdict."""
        # 1. Generate test case
        gen_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/generate",
            json={
                "service_id": 0x22,
                "test_scenario": "POSITIVE"
            }
        )
        assert gen_resp.status_code == 201
        tc_id = gen_resp.json()[0]["test_case_id"]

        # 2. Approve test case via review endpoint
        rev_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/review",
            json={
                "reviewer_name": "Senior Test Architect",
                "reviewer_role": "Validation Lead",
                "action": "APPROVE",
                "comments": "Approved for Phase 3 API execution verification."
            }
        )
        assert rev_resp.status_code == 200
        assert rev_resp.json()["review_status"] == "APPROVED"

        # 3. Execute approved test case
        exec_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/execute",
            json={"operator_name": "Automated Execution Harness"}
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["overall_verdict"] == "PASS"
        assert exec_data["test_case_id"] == tc_id
        assert exec_data["governance_verified"] is True
        assert len(exec_data["step_results"]) == 1
        assert exec_data["step_results"][0]["step_verdict"] == "PASS"
        assert exec_data["audit_id"] is not None

        # 4. Verify run appears in execution history
        hist_resp = client.get(f"/api/v1/workspaces/{setup_workspace}/execution-runs")
        assert hist_resp.status_code == 200
        runs = hist_resp.json()
        assert any(r["execution_id"] == exec_data["execution_id"] for r in runs)

        # 5. Retrieve specific run by execution ID
        single_resp = client.get(
            f"/api/v1/workspaces/{setup_workspace}/execution-runs/{exec_data['execution_id']}"
        )
        assert single_resp.status_code == 200
        assert single_resp.json()["execution_id"] == exec_data["execution_id"]

    def test_execute_with_fault_injection_api(self, setup_workspace):
        """Verify executing an approved test with injected fault causes verdict to FAIL."""
        # 1. Generate and approve test case
        gen_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/generate",
            json={
                "service_id": 0x10,
                "test_scenario": "POSITIVE",
                "subfunction": 1
            }
        )
        tc_id = gen_resp.json()[0]["test_case_id"]
        client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/review",
            json={
                "reviewer_name": "Fault Engineer",
                "reviewer_role": "QA",
                "action": "APPROVE",
                "comments": "Approved for fault injection API testing."
            }
        )

        # 2. Execute with forced NRC 0x10 (GeneralReject)
        exec_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/execute",
            json={
                "operator_name": "Fault Harness",
                "fault_profile": {
                    "forced_nrc": 0x10
                }
            }
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["overall_verdict"] == "FAIL"
        assert exec_data["step_results"][0]["actual_nrc"] == "0x10"

    def test_execute_non_existent_test_case_api(self, setup_workspace):
        """Verify executing non-existent test case returns 404."""
        resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/tc_nonexistent_9999/execute",
            json={"operator_name": "Runner"}
        )
        assert resp.status_code == 404

    def test_get_non_existent_execution_run_api(self, setup_workspace):
        """Verify retrieving non-existent execution run returns 404."""
        resp = client.get(
            f"/api/v1/workspaces/{setup_workspace}/execution-runs/exec_nonexistent_9999"
        )
        assert resp.status_code == 404
