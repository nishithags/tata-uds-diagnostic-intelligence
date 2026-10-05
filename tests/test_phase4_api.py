"""
Integration and Validation Tests for Phase 4 API Endpoints.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Tests:
- POST /api/v1/workspaces/{project_id}/export (Enforce 403 on unapproved, export Python & CAPL on approved)
- GET /api/v1/workspaces/{project_id}/coverage (Deterministic 15-service coverage matrix)
- POST /api/v1/workspaces/{project_id}/optimize (Deterministic deduplication & optimization report)
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


@pytest.fixture(scope="module")
def setup_workspace():
    """Ensure a test workspace exists for Phase 4 API tests."""
    ws_id = "test_phase4_api_ws"
    client.post("/api/v1/workspaces", json={
        "project_id": ws_id,
        "name": "Phase 4 Test Workspace",
        "description": "Integration testing for script export & test optimization",
        "oem_name": "Tata Motors",
        "ecu_model": "BCM_GEN3"
    })
    return ws_id


class TestPhase4APIEndpoints:
    """Test suite for Phase 4 Automation Script Export and Test Optimization REST APIs."""

    def test_export_blocked_on_unapproved_test_case_api(self, setup_workspace):
        """Verify export is strictly BLOCKED with HTTP 403 if test case is not approved."""
        # 1. Generate test case (status is PENDING_REVIEW)
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

        # 2. Attempt export -> MUST return HTTP 403
        exp_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/export",
            json={
                "test_case_ids": [tc_id],
                "format": "python_can_udsoncan",
                "operator_name": "Test Runner"
            }
        )
        assert exp_resp.status_code == 403
        assert "Cannot export unapproved test cases" in exp_resp.json()["detail"]

    def test_export_approved_python_and_capl_api(self, setup_workspace):
        """Verify exporting formally approved test cases to Python and CAPL formats via API."""
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

        # 2. Approve test case
        rev_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/test-cases/{tc_id}/review",
            json={
                "reviewer_name": "Senior Test Architect",
                "reviewer_role": "Validation Lead",
                "action": "APPROVE",
                "comments": "Approved for Phase 4 export API testing."
            }
        )
        assert rev_resp.status_code == 200

        # 3. Export to Python
        py_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/export",
            json={
                "test_case_ids": [tc_id],
                "format": "python_can_udsoncan",
                "operator_name": "Validation Lead",
                "file_name": "exported_suite.py"
            }
        )
        assert py_resp.status_code == 200
        py_data = py_resp.json()
        assert py_data["export_format"] == "python_can_udsoncan"
        assert py_data["file_extension"] == ".py"
        assert "UDSTestHarness" in py_data["code_content"]
        assert len(py_data["sha256_hash"]) == 64
        assert py_data["audit_id"] is not None

        # 4. Export to CAPL
        capl_resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/export",
            json={
                "test_case_ids": [tc_id],
                "format": "canoe_capl",
                "operator_name": "Validation Lead",
                "file_name": "exported_suite.can"
            }
        )
        assert capl_resp.status_code == 200
        capl_data = capl_resp.json()
        assert capl_data["export_format"] == "canoe_capl"
        assert capl_data["file_extension"] == ".can"
        assert "testcase tc_" in capl_data["code_content"]

    def test_export_non_existent_test_case_api(self, setup_workspace):
        """Verify exporting a non-existent test case ID returns 404."""
        resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/export",
            json={
                "test_case_ids": ["tc_does_not_exist_9999"],
                "format": "python_can_udsoncan"
            }
        )
        assert resp.status_code == 404

    def test_get_coverage_matrix_api(self, setup_workspace):
        """Verify GET /coverage returns comprehensive 15-service matrix."""
        resp = client.get(f"/api/v1/workspaces/{setup_workspace}/coverage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_services_in_scope"] == 15
        assert len(data["service_breakdown"]) == 15
        assert "service_coverage_pct" in data
        assert "uncovered_combinations" in data

    def test_optimize_test_cases_api(self, setup_workspace):
        """Verify POST /optimize returns deduplication and coverage preservation report."""
        resp = client.post(
            f"/api/v1/workspaces/{setup_workspace}/optimize",
            json={}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "original_count" in data
        assert "retained_count" in data
        assert "removed_duplicates_count" in data
        assert "deduplication_ratio_pct" in data
        assert "coverage_impact" in data
