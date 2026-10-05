"""
Integration tests for Phase 5 API Endpoints (Lineage & Analytics Telemetry).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from fastapi.testclient import TestClient
import pytest

from src.api.main import app
from src.core.generator import TestCase, TestStep, test_generator
from src.core.test_case_store import test_case_store
from src.core.workspace_manager import workspace_manager

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_phase5_workspace():
    ws_id = "test_phase5_api_ws"
    if not workspace_manager.get_workspace(ws_id):
        workspace_manager.create_workspace(
            project_id=ws_id,
            name="Phase 5 API Workspace",
            description="Testing Phase 5 Lineage and Metrics APIs",
            oem_name="Tata Technologies",
            ecu_model="BCM_EV"
        )
    return ws_id


def test_get_lineage_api_endpoint(setup_phase5_workspace):
    ws_id = setup_phase5_workspace

    # Generate a positive test case in this workspace
    tc = test_generator.generate_positive_test(
        service_id=0x10,
        project_id=ws_id
    )
    test_case_store.save_test_case(tc)

    # Query UPSTREAM lineage
    resp = client.get(f"/api/v1/workspaces/{ws_id}/lineage/{tc.test_case_id}?direction=UPSTREAM")
    assert resp.status_code == 200
    data = resp.json()

    assert data["root_node_id"] == tc.test_case_id
    assert data["direction"] == "UPSTREAM"
    assert data["total_nodes"] >= 1
    assert any(n["node_id"] == tc.test_case_id for n in data["nodes"])

    # Query BIDIRECTIONAL lineage
    resp_bi = client.get(f"/api/v1/workspaces/{ws_id}/lineage/{tc.test_case_id}?direction=BIDIRECTIONAL")
    assert resp_bi.status_code == 200
    data_bi = resp_bi.json()
    assert data_bi["direction"] == "BIDIRECTIONAL"


def test_get_lineage_nonexistent_workspace():
    resp = client.get("/api/v1/workspaces/non_existent_ws_999/lineage/some_node")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_analytics_metrics_api_endpoint(setup_phase5_workspace):
    ws_id = setup_phase5_workspace

    resp = client.get(f"/api/v1/workspaces/{ws_id}/analytics/metrics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == ws_id
    assert "computed_at" in data

    # Verify all 5 Section 11 metrics are present
    assert "test_design_time" in data
    assert "generation_accuracy" in data
    assert "coverage_improvement" in data
    assert "reuse_rate" in data
    assert "defect_detection" in data

    # Verify strict segregation: measured_value vs target_value
    for metric_key in ["test_design_time", "generation_accuracy", "coverage_improvement", "reuse_rate", "defect_detection"]:
        m = data[metric_key]
        assert "measured_value" in m
        assert "target_value" in m
        assert "target_label" in m
        assert "status" in m
        assert "analysis_note" in m
        assert isinstance(m["measured_value"], (int, float))
        assert isinstance(m["target_value"], (int, float))


def test_get_analytics_nonexistent_workspace():
    resp = client.get("/api/v1/workspaces/non_existent_ws_999/analytics/metrics")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
