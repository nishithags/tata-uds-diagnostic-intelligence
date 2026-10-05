"""
Integration and validation tests for FastAPI Knowledge Pilot endpoints.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from fastapi.testclient import TestClient
import pytest
from src.api.main import app

client = TestClient(app)


def test_api_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "UDS Knowledge Pilot" in data["service"]
    assert data["llm_runtime_status"] == "PENDING_FORMAL_USER_APPROVAL"


def test_workspace_creation_and_listing():
    create_payload = {
        "project_id": "test_api_ws_01",
        "name": "API Test Workspace",
        "description": "Integration testing workspace",
        "oem_name": "Tata Test OEM",
        "ecu_model": "BCM_TEST"
    }
    create_resp = client.post("/api/v1/workspaces", json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["project_id"] == "test_api_ws_01"
    assert created_data["name"] == "API Test Workspace"

    list_resp = client.get("/api/v1/workspaces")
    assert list_resp.status_code == 200
    workspaces = list_resp.json()
    assert any(w["project_id"] == "test_api_ws_01" for w in workspaces)


def test_document_upload_and_query_flow():
    # 1. Create workspace
    ws_id = "test_upload_ws_02"
    client.post("/api/v1/workspaces", json={
        "project_id": ws_id,
        "name": "Upload Flow Test",
        "oem_name": "OEM Test",
        "ecu_model": "ECU_01"
    })

    # 2. Upload text diagnostic specification
    sample_content = (
        "Service 0x10 DiagnosticSessionControl\n"
        "Supported subfunctions: 0x01 DefaultSession, 0x02 ProgrammingSession, 0x03 ExtendedSession.\n"
        "P2Server timeout maximum is 50 milliseconds."
    ).encode("utf-8")

    files = {"file": ("test_uds_session.txt", sample_content, "text/plain")}
    upload_resp = client.post(
        f"/api/v1/workspaces/{ws_id}/documents/upload",
        files=files,
        data={"doc_type": "STANDARD_SPEC"}
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["status"] == "SUCCESS"
    assert upload_data["document"]["filename"] == "test_uds_session.txt"
    assert upload_data["document"]["total_chunks"] >= 1

    # 3. List documents
    docs_resp = client.get(f"/api/v1/workspaces/{ws_id}/documents")
    assert docs_resp.status_code == 200
    docs_list = docs_resp.json()
    assert docs_list["total_documents"] >= 1

    # 4. Query knowledge
    query_payload = {
        "project_id": ws_id,
        "query": "What are the supported subfunctions for DiagnosticSessionControl 0x10?",
        "top_k": 3
    }
    query_resp = client.post("/api/v1/knowledge/query", json=query_payload)
    assert query_resp.status_code == 200
    q_data = query_resp.json()
    assert q_data["total_citations"] >= 1
    assert "0x01 DefaultSession" in q_data["citations"][0]["text_snippet"]
    assert q_data["llm_decision_status"] == "PENDING_FORMAL_USER_APPROVAL"


def test_invalid_file_upload_rejected():
    ws_id = "test_invalid_ws"
    client.post("/api/v1/workspaces", json={"project_id": ws_id, "name": "Invalid File Test"})

    # Upload unsupported file extension
    files = {"file": ("malicious_script.exe", b"binarycontent", "application/octet-stream")}
    resp = client.post(f"/api/v1/workspaces/{ws_id}/documents/upload", files=files)
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]
