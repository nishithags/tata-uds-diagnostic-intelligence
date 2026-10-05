"""
API Routes for Phase 1 Knowledge Pilot.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from pathlib import Path
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status

from src.api.models import (
    ActivityListResponse,
    ActivityRecordResponse,
    ActivitySummaryResponse,
    AuditLogResponse,
    CitationResponseModel,
    CoverageReportResponse,
    CustomValidateRequest,
    DocumentListResponse,
    DocumentMetadataResponse,
    DocumentUploadResponse,
    ECUStateResponse,
    EnterpriseMetricsResponse,
    FaultProfileModel,
    GraphEdgeModel,
    GraphLineageResponse,
    GraphNodeModel,
    KnowledgeQueryHistoryItem,
    KnowledgeQueryHistoryResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    OptimizationReportResponse,
    RemovedTestDetailResponse,
    RuleCheckItem,
    ServiceCoverageResponse,
    SingleMetricResponse,
    StepExecutionResponse,
    TestCaseExecutionResponse,
    TestCaseResponse,
    TestExecuteRequest,
    TestExportRequest,
    TestExportResponse,
    TestGenerateRequest,
    TestOptimizeRequest,
    TestReviewRequest,
    TestStepModel,
    ValidationReportResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from src.core.activity_store import ActivityAction, activity_store
from src.core.analytics import analytics_engine
from src.core.config import config
from src.core.chunking import ContextAwareChunker
from src.core.execution_engine import TestCaseExecutionResult, execution_engine
from src.core.execution_store import execution_store
from src.core.exporter import script_exporter
from src.core.generator import TestCase, test_generator
from src.core.governance import GovernanceError, governance_manager
from src.core.graph_store import graph_store
from src.core.ingestion import DocumentIngestionEngine, IngestionError
from src.core.llm_interface import LLMClientFactory
from src.core.optimizer import test_optimizer
from src.core.rules import DiagnosticSession, SecurityLevel, rule_engine
from src.core.simulator import FaultProfile, simulated_ecu
from src.core.test_case_store import test_case_store
from src.core.vector_store import IsolatedVectorStore
from src.core.workspace_manager import workspace_manager

router = APIRouter(prefix="/api/v1")


def _get_session_ctx(request: Optional[Request] = None):
    """Extracts session ID, user ID, and client IP from request state or generates anonymous defaults."""
    if request is None or not hasattr(request, "state"):
        return f"sess_{uuid.uuid4().hex[:12]}", None, None
    session_id = getattr(request.state, "session_id", None) or f"sess_{uuid.uuid4().hex[:12]}"
    user_id = getattr(request.state, "user_id", None)
    client_ip = getattr(request.state, "client_ip", None)
    return session_id, user_id, client_ip


# Initialize core services
ingestion_engine = DocumentIngestionEngine()
chunker = ContextAwareChunker()
vector_store = IsolatedVectorStore()
llm_client = LLMClientFactory.get_client()


@router.get("/health", tags=["System"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": config.app_name,
        "version": config.app_version,
        "vector_store": "ChromaDB (Isolated Multi-Collection)",
        "embedding_model": vector_store.embedding_service.model_name,
        "llm_runtime_status": "PENDING_FORMAL_USER_APPROVAL"
    }


# ==========================================
# Workspace / Project Endpoints
# ==========================================

@router.get("/workspaces", response_model=List[WorkspaceResponse], tags=["Workspaces"])
def list_workspaces():
    """Lists all available isolated engineering workspaces."""
    workspaces = workspace_manager.list_workspaces()
    response = []
    for ws in workspaces:
        chunks_count = vector_store.count_chunks(ws.project_id)
        response.append(
            WorkspaceResponse(
                project_id=ws.project_id,
                name=ws.name,
                description=ws.description,
                oem_name=ws.oem_name,
                ecu_model=ws.ecu_model,
                created_at=ws.created_at,
                documents_count=len(ws.documents),
                chunks_count=chunks_count
            )
        )
    return response


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED, tags=["Workspaces"])
def create_workspace(req: WorkspaceCreateRequest, request: Request = None):
    """Creates a new isolated project workspace."""
    clean_id = req.project_id.strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="Project ID cannot be empty.")
    
    ws = workspace_manager.create_workspace(
        project_id=clean_id,
        name=req.name,
        description=req.description or "",
        oem_name=req.oem_name or "Generic OEM",
        ecu_model=req.ecu_model or "Generic ECU"
    )
    chunks_count = vector_store.count_chunks(clean_id)

    sess_id, uid, cip = _get_session_ctx(request)
    activity_store.log_activity(
        session_id=sess_id,
        user_id=uid,
        project_id=clean_id,
        action=ActivityAction.WORKSPACE_CREATED,
        endpoint="/api/v1/workspaces",
        http_method="POST",
        status="SUCCESS",
        client_ip=cip,
        metadata={"name": req.name, "oem": req.oem_name, "ecu": req.ecu_model}
    )

    return WorkspaceResponse(
        project_id=ws.project_id,
        name=ws.name,
        description=ws.description,
        oem_name=ws.oem_name,
        ecu_model=ws.ecu_model,
        created_at=ws.created_at,
        documents_count=len(ws.documents),
        chunks_count=chunks_count
    )


@router.get("/workspaces/{project_id}", response_model=WorkspaceResponse, tags=["Workspaces"])
def get_workspace(project_id: str):
    """Retrieves workspace metadata and document statistics."""
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")
    chunks_count = vector_store.count_chunks(project_id)
    return WorkspaceResponse(
        project_id=ws.project_id,
        name=ws.name,
        description=ws.description,
        oem_name=ws.oem_name,
        ecu_model=ws.ecu_model,
        created_at=ws.created_at,
        documents_count=len(ws.documents),
        chunks_count=chunks_count
    )


# ==========================================
# Document Ingestion Endpoints
# ==========================================

@router.post(
    "/workspaces/{project_id}/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"]
)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(default="SPECIFICATION"),
    request: Request = None
):
    """
    Uploads and ingests an authorized diagnostic document.
    Extracts text, calculates SHA-256 provenance hash, creates context-aware chunks,
    and indexes them in the project's isolated vector collection.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    try:
        file_bytes = await file.read()
        filename = file.filename or "uploaded_spec.pdf"
        
        # 1. Ingest document and extract text page-by-page
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            ingested_doc = ingestion_engine.ingest_pdf(
                file_bytes=file_bytes,
                filename=filename,
                project_id=project_id,
                metadata={"doc_type": doc_type}
            )
        elif ext in (".txt", ".md"):
            text_content = file_bytes.decode("utf-8", errors="replace")
            ingested_doc = ingestion_engine.ingest_text(
                text=text_content,
                filename=filename,
                project_id=project_id,
                metadata={"doc_type": doc_type}
            )
        else:
            raise IngestionError(f"Unsupported file type '{ext}'. Allowed: PDF, TXT, MD.")

        # 2. Context-aware chunking
        chunks = chunker.chunk_document(ingested_doc)

        # 3. Embed & store into isolated vector collection
        vector_store.add_chunks(project_id=project_id, chunks=chunks)

        # 4. Save metadata record to workspace manifest
        doc_record = {
            "doc_id": ingested_doc.doc_id,
            "project_id": project_id,
            "filename": ingested_doc.filename,
            "file_type": ingested_doc.file_type,
            "file_size_bytes": ingested_doc.file_size_bytes,
            "file_hash_sha256": ingested_doc.file_hash_sha256,
            "total_pages": ingested_doc.total_pages,
            "total_chunks": len(chunks),
            "ingested_at": ingested_doc.ingested_at,
            "authorization_status": ingested_doc.authorization_status,
            "metadata": {"doc_type": doc_type}
        }
        workspace_manager.record_document(project_id=project_id, doc_metadata=doc_record)

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.DOCUMENT_UPLOAD,
            endpoint=f"/api/v1/workspaces/{project_id}/documents/upload",
            http_method="POST",
            status="SUCCESS",
            client_ip=cip,
            metadata={
                "filename": filename,
                "doc_type": doc_type,
                "file_size_bytes": len(file_bytes),
                "chunks_count": len(chunks)
            }
        )

        return DocumentUploadResponse(
            status="SUCCESS",
            message=f"Document '{filename}' successfully ingested into workspace '{project_id}'.",
            document=DocumentMetadataResponse(**doc_record)
        )

    except IngestionError as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.DOCUMENT_UPLOAD,
            endpoint=f"/api/v1/workspaces/{project_id}/documents/upload",
            http_method="POST",
            status="FAILURE",
            http_status_code=400,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.DOCUMENT_UPLOAD,
            endpoint=f"/api/v1/workspaces/{project_id}/documents/upload",
            http_method="POST",
            status="ERROR",
            http_status_code=500,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Internal ingestion error: {str(e)}")


@router.get(
    "/workspaces/{project_id}/documents",
    response_model=DocumentListResponse,
    tags=["Documents"]
)
def list_documents(project_id: str):
    """Lists all ingested documents in the specified workspace."""
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    docs = workspace_manager.get_documents_for_project(project_id)
    return DocumentListResponse(
        project_id=project_id,
        total_documents=len(docs),
        documents=[DocumentMetadataResponse(**d) for d in docs]
    )


# ==========================================
# Cited Knowledge Retrieval & Q&A
# ==========================================

@router.post("/knowledge/query", response_model=KnowledgeQueryResponse, tags=["Knowledge Retrieval"])
def query_knowledge(req: KnowledgeQueryRequest, request: Request = None):
    """
    Executes a cited diagnostic search strictly within the specified workspace.
    Retrieves source citations with relevance scores, page numbers, sections,
    and returns an evidence-grounded response.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    ws = workspace_manager.get_workspace(req.project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{req.project_id}' not found.")

    # 1. Retrieve top-k cited chunks from isolated vector store
    citations = vector_store.query(
        project_id=req.project_id,
        query_text=req.query,
        top_k=req.top_k
    )

    # 2. Generate answer via abstract LLM client
    qa_result = llm_client.generate_answer(query=req.query, citations=citations)

    citation_models = [
        CitationResponseModel(
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            project_id=c.project_id,
            document_name=c.document_name,
            page_number=c.page_number,
            section_title=c.section_title,
            text_snippet=c.text_snippet,
            relevance_score=c.relevance_score,
            distance=c.distance,
            source_hash_sha256=c.source_hash_sha256
        )
        for c in citations
    ]

    activity_store.log_activity(
        session_id=sess_id,
        user_id=uid,
        project_id=req.project_id,
        action=ActivityAction.KNOWLEDGE_QUERY,
        endpoint="/api/v1/knowledge/query",
        http_method="POST",
        query_text=req.query,
        status="SUCCESS",
        duration_ms=qa_result.inference_latency_ms,
        client_ip=cip,
        metadata={
            "citations_count": len(citation_models),
            "model": qa_result.model_identifier,
            "is_mock": getattr(qa_result, "is_mock_fallback", True)
        }
    )

    return KnowledgeQueryResponse(
        project_id=req.project_id,
        query=req.query,
        answer=qa_result.answer,
        citations=citation_models,
        total_citations=len(citation_models),
        model_identifier=qa_result.model_identifier,
        llm_decision_status=qa_result.llm_decision_status,
        disclaimer=qa_result.disclaimer
    )


# ==========================================
# Phase 2: Rule Verification & Test Generation Endpoints
# ==========================================

@router.post(
    "/workspaces/{project_id}/test-cases/generate",
    response_model=List[TestCaseResponse],
    status_code=status.HTTP_201_CREATED,
    tags=["Test Generation & Rules"]
)
def generate_test_cases(project_id: str, req: TestGenerateRequest, request: Request = None):
    """
    Generates rule-verified UDS test cases (positive, negative, or complete suite)
    for the specified service, applying deterministic ISO 14229 rules immediately.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    try:
        session_enum = DiagnosticSession(req.session)
    except Exception:
        session_enum = DiagnosticSession.DEFAULT

    try:
        security_enum = SecurityLevel(req.security)
    except Exception:
        security_enum = SecurityLevel.LOCKED

    generated_cases: List[TestCase] = []

    try:
        if req.test_scenario == "SUITE":
            generated_cases = test_generator.generate_suite_for_service(
                service_id=req.service_id,
                project_id=project_id
            )
        elif req.test_scenario == "POSITIVE":
            tc = test_generator.generate_positive_test(
                service_id=req.service_id,
                project_id=project_id,
                subfunction=req.subfunction,
                did_hex=req.did_hex,
                session=session_enum,
                security=security_enum
            )
            generated_cases = [tc]
        elif req.test_scenario.startswith("NEGATIVE"):
            defect_type = req.test_scenario.replace("NEGATIVE_", "")
            if defect_type == "SUBFUNCTION":
                defect_type = "INVALID_SUBFUNCTION"
            elif defect_type == "LENGTH":
                defect_type = "INCORRECT_LENGTH"
            elif defect_type == "SESSION":
                defect_type = "SESSION_VIOLATION"
            elif defect_type == "SECURITY":
                defect_type = "SECURITY_LOCKED"
            tc = test_generator.generate_negative_test(
                service_id=req.service_id,
                defect_type=defect_type,
                project_id=project_id,
                session=session_enum,
                security=security_enum
            )
            generated_cases = [tc]
        else:
            raise HTTPException(status_code=400, detail=f"Unknown test scenario '{req.test_scenario}'")

        # Save to test case store & log governance audit event
        for tc in generated_cases:
            test_case_store.save_test_case(tc)
            governance_manager.log_audit(
                project_id=project_id,
                event_type="TEST_GENERATED",
                performed_by="AI Rule-Verified Generator",
                details={
                    "test_case_id": tc.test_case_id,
                    "service_id": f"0x{tc.service_id:02X}",
                    "test_type": tc.test_type,
                    "verdict": tc.rule_verification_status
                }
            )

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.TEST_GENERATED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/generate",
            http_method="POST",
            status="SUCCESS",
            client_ip=cip,
            metadata={
                "service_id": f"0x{req.service_id:02X}",
                "test_scenario": req.test_scenario,
                "generated_count": len(generated_cases),
                "test_case_ids": [tc.test_case_id for tc in generated_cases]
            }
        )

        return [TestCaseResponse(**tc.model_dump()) for tc in generated_cases]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get(
    "/workspaces/{project_id}/test-cases",
    response_model=List[TestCaseResponse],
    tags=["Test Generation & Rules"]
)
def list_test_cases(project_id: str):
    """Lists all stored test cases in the specified workspace."""
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")
    cases = test_case_store.list_test_cases(project_id)
    return [TestCaseResponse(**tc.model_dump()) for tc in cases]


@router.get(
    "/workspaces/{project_id}/test-cases/{test_case_id}",
    response_model=TestCaseResponse,
    tags=["Test Generation & Rules"]
)
def get_test_case(project_id: str, test_case_id: str):
    """Retrieves a single test case by its ID."""
    tc = test_case_store.get_test_case(project_id, test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{test_case_id}' not found.")
    return TestCaseResponse(**tc.model_dump())


@router.post(
    "/workspaces/{project_id}/test-cases/{test_case_id}/review",
    response_model=TestCaseResponse,
    tags=["Test Governance"]
)
def review_test_case(project_id: str, test_case_id: str, req: TestReviewRequest, request: Request = None):
    """
    Submits a formal engineering review for a test case.
    Valid actions: APPROVE, EDIT_AND_APPROVE, REJECT.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    tc = test_case_store.get_test_case(project_id, test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{test_case_id}' not found.")

    try:
        updated_tc, review_rec = governance_manager.submit_review(
            test_case=tc,
            reviewer_name=req.reviewer_name,
            reviewer_role=req.reviewer_role,
            action=req.action,
            comments=req.comments,
            edited_title=req.edited_title,
            edited_description=req.edited_description
        )
        test_case_store.save_test_case(updated_tc)

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.reviewer_name,
            project_id=project_id,
            action=ActivityAction.TEST_REVIEWED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/{test_case_id}/review",
            http_method="POST",
            test_case_id=test_case_id,
            status="SUCCESS",
            client_ip=cip,
            metadata={
                "action": req.action,
                "reviewer_name": req.reviewer_name,
                "reviewer_role": req.reviewer_role,
                "verdict": updated_tc.review_status
            }
        )

        return TestCaseResponse(**updated_tc.model_dump())
    except GovernanceError as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.reviewer_name,
            project_id=project_id,
            action=ActivityAction.TEST_REVIEWED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/{test_case_id}/review",
            http_method="POST",
            test_case_id=test_case_id,
            status="FAILURE",
            http_status_code=400,
            client_ip=cip,
            metadata={"error": str(e), "action": req.action}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review submission failed: {str(e)}")


@router.post(
    "/workspaces/{project_id}/test-cases/{test_case_id}/assert-executable",
    tags=["Test Governance"]
)
def assert_test_case_executable(project_id: str, test_case_id: str):
    """
    Enforces that unapproved tests cannot be exported or executed.
    Returns 200 if approved, 403 Forbidden if unapproved or rejected.
    """
    tc = test_case_store.get_test_case(project_id, test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{test_case_id}' not found.")
    try:
        governance_manager.assert_can_export_or_execute(tc)
        return {
            "status": "ALLOWED",
            "test_case_id": tc.test_case_id,
            "review_status": tc.review_status,
            "message": "Test case is approved for downstream export and execution."
        }
    except GovernanceError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/workspaces/{project_id}/test-cases/validate-custom",
    response_model=ValidationReportResponse,
    tags=["Test Generation & Rules"]
)
def validate_custom_frame(project_id: str, req: CustomValidateRequest, request: Request = None):
    """
    Validates an arbitrary raw UDS hex frame against deterministic ISO 14229 rules.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    try:
        session_enum = DiagnosticSession(req.session)
    except Exception:
        session_enum = DiagnosticSession.DEFAULT

    try:
        security_enum = SecurityLevel(req.security)
    except Exception:
        security_enum = SecurityLevel.LOCKED

    try:
        report = rule_engine.validate_request(
            request_hex=req.request_hex,
            current_session=session_enum,
            current_security=security_enum,
            expected_response_type=req.expected_response_type,
            expected_nrc=req.expected_nrc
        )

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.RULE_VERIFIED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/validate-custom",
            http_method="POST",
            status="SUCCESS",
            client_ip=cip,
            metadata={
                "service_hex": report.service_hex,
                "overall_verdict": report.overall_verdict,
                "passed_checks": sum(1 for c in report.checks if c.passed),
                "total_checks": len(report.checks)
            }
        )

        return ValidationReportResponse(
            overall_verdict=report.overall_verdict,
            service_id=report.service_id,
            service_hex=report.service_hex,
            service_name=report.service_name,
            checks=[
                RuleCheckItem(
                    rule_code=c.rule_code,
                    rule_name=c.rule_name,
                    passed=c.passed,
                    message=c.message,
                    expected=c.expected,
                    actual=c.actual
                )
                for c in report.checks
            ],
            errors=report.errors,
            warnings=report.warnings
        )
    except Exception as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid,
            project_id=project_id,
            action=ActivityAction.RULE_VERIFIED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/validate-custom",
            http_method="POST",
            status="FAILURE",
            http_status_code=400,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=400, detail=f"Validation failed: {str(e)}")


@router.get(
    "/workspaces/{project_id}/audit-logs",
    response_model=List[AuditLogResponse],
    tags=["Test Governance"]
)
def get_workspace_audit_logs(project_id: str):
    """Retrieves immutable audit trail entries for the workspace."""
    events = governance_manager.get_audit_trail(project_id)
    return [
        AuditLogResponse(
            audit_id=e["audit_id"],
            project_id=e["project_id"],
            event_type=e["event_type"],
            performed_by=e["performed_by"],
            details=e.get("details", {}),
            created_at=e["created_at"]
        )
        for e in events
    ]


# ==========================================
# Phase 3: Simulated ECU & Test Execution Endpoints
# ==========================================

@router.get(
    "/workspaces/{project_id}/ecu-state",
    response_model=ECUStateResponse,
    tags=["Simulated ECU"]
)
def get_ecu_state(project_id: str):
    """Retrieves the current diagnostic state of the Virtual Simulated ECU."""
    snapshot = simulated_ecu.get_snapshot()
    return ECUStateResponse(**snapshot.model_dump())


@router.post(
    "/workspaces/{project_id}/ecu-state/reset",
    response_model=ECUStateResponse,
    tags=["Simulated ECU"]
)
def reset_ecu_state(project_id: str, request: Request = None):
    """Resets the Simulated ECU to default power-on state."""
    sess_id, uid, cip = _get_session_ctx(request)
    simulated_ecu.reset_state()
    snapshot = simulated_ecu.get_snapshot()

    activity_store.log_activity(
        session_id=sess_id,
        user_id=uid,
        project_id=project_id,
        action=ActivityAction.ECU_RESET,
        endpoint=f"/api/v1/workspaces/{project_id}/ecu-state/reset",
        http_method="POST",
        status="SUCCESS",
        client_ip=cip
    )

    return ECUStateResponse(**snapshot.model_dump())


@router.post(
    "/workspaces/{project_id}/test-cases/{test_case_id}/execute",
    response_model=TestCaseExecutionResponse,
    tags=["Test Execution Engine"]
)
def execute_test_case(project_id: str, test_case_id: str, req: TestExecuteRequest, request: Request = None):
    """
    Executes a formally APPROVED test case against the Virtual Simulated ECU.
    Enforces governance guardrail: DRAFT, RULE_VERIFIED, PENDING_REVIEW, and REJECTED tests
    are strictly BLOCKED with HTTP 403.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    tc = test_case_store.get_test_case(project_id, test_case_id)
    if not tc:
        raise HTTPException(status_code=404, detail=f"Test case '{test_case_id}' not found.")

    fault_prof = None
    if req.fault_profile:
        fault_prof = FaultProfile(**req.fault_profile.model_dump())

    try:
        result = execution_engine.execute_test_case(
            test_case=tc,
            fault_profile=fault_prof,
            operator_name=req.operator_name
        )
        execution_store.save_execution_result(result)

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.operator_name,
            project_id=project_id,
            action=ActivityAction.TEST_EXECUTED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/{test_case_id}/execute",
            http_method="POST",
            test_case_id=test_case_id,
            status="SUCCESS" if result.overall_verdict == "PASS" else "FAILURE",
            duration_ms=result.total_elapsed_ms,
            client_ip=cip,
            metadata={
                "verdict": result.overall_verdict,
                "operator_name": req.operator_name,
                "steps_count": len(result.step_results)
            }
        )

        return TestCaseExecutionResponse(**result.model_dump())
    except GovernanceError as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.operator_name,
            project_id=project_id,
            action=ActivityAction.TEST_EXECUTED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/{test_case_id}/execute",
            http_method="POST",
            test_case_id=test_case_id,
            status="FAILURE",
            http_status_code=403,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.operator_name,
            project_id=project_id,
            action=ActivityAction.TEST_EXECUTED,
            endpoint=f"/api/v1/workspaces/{project_id}/test-cases/{test_case_id}/execute",
            http_method="POST",
            test_case_id=test_case_id,
            status="ERROR",
            http_status_code=500,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get(
    "/workspaces/{project_id}/execution-runs",
    response_model=List[TestCaseExecutionResponse],
    tags=["Test Execution Engine"]
)
def list_execution_runs(project_id: str):
    """Lists all stored execution runs for the specified workspace."""
    runs = execution_store.list_execution_results(project_id)
    return [TestCaseExecutionResponse(**r.model_dump()) for r in runs]


@router.get(
    "/workspaces/{project_id}/execution-runs/{execution_id}",
    response_model=TestCaseExecutionResponse,
    tags=["Test Execution Engine"]
)
def get_execution_run(project_id: str, execution_id: str):
    """Retrieves a single test execution run by its execution ID."""
    run = execution_store.get_execution_result(project_id, execution_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Execution run '{execution_id}' not found.")
    return TestCaseExecutionResponse(**run.model_dump())


# ==========================================
# Phase 4: Automation Script Export & Test Optimization Endpoints
# ==========================================

@router.post(
    "/workspaces/{project_id}/export",
    response_model=TestExportResponse,
    tags=["Automation Script Export"]
)
def export_test_cases(project_id: str, req: TestExportRequest, request: Request = None):
    """
    Exports formally APPROVED test cases to production-grade automation scripts:
    1. Python using python-can / udsoncan approach.
    2. Vector CANoe CAPL (.can) test modules.

    Enforces mandatory governance guard: DRAFT, RULE_VERIFIED, PENDING_REVIEW,
    and REJECTED test cases CANNOT be exported (returns HTTP 403).
    """
    sess_id, uid, cip = _get_session_ctx(request)
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    test_cases: List[TestCase] = []
    missing_ids = []
    for tc_id in req.test_case_ids:
        tc = test_case_store.get_test_case(project_id, tc_id)
        if not tc:
            missing_ids.append(tc_id)
        else:
            test_cases.append(tc)

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Test case(s) not found in workspace '{project_id}': {', '.join(missing_ids)}"
        )

    try:
        artifact = script_exporter.export_test_suite(
            test_cases=test_cases,
            export_format=req.format,
            operator_name=req.operator_name,
            file_name=req.file_name,
            suite_title=f"Exported Suite - {ws.name}"
        )

        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.operator_name,
            project_id=project_id,
            action=ActivityAction.TEST_EXPORTED,
            endpoint=f"/api/v1/workspaces/{project_id}/export",
            http_method="POST",
            status="SUCCESS",
            client_ip=cip,
            metadata={
                "format": req.format,
                "exported_count": len(test_cases),
                "file_name": artifact.artifact_name
            }
        )

        return TestExportResponse(**artifact.model_dump())
    except GovernanceError as e:
        activity_store.log_activity(
            session_id=sess_id,
            user_id=uid or req.operator_name,
            project_id=project_id,
            action=ActivityAction.TEST_EXPORTED,
            endpoint=f"/api/v1/workspaces/{project_id}/export",
            http_method="POST",
            status="FAILURE",
            http_status_code=403,
            client_ip=cip,
            metadata={"error": str(e)}
        )
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get(
    "/workspaces/{project_id}/coverage",
    response_model=CoverageReportResponse,
    tags=["Test Optimization & Coverage"]
)
def get_workspace_coverage(project_id: str):
    """
    Calculates deterministic diagnostic test coverage across all 15 supported ISO 14229 services:
    Service x Positive/Negative x Session x Security level.
    """
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    test_cases = test_case_store.list_test_cases(project_id)
    matrix = test_optimizer.calculate_coverage(test_cases, project_id=project_id)
    return CoverageReportResponse(**matrix.model_dump())


@router.post(
    "/workspaces/{project_id}/optimize",
    response_model=OptimizationReportResponse,
    tags=["Test Optimization & Coverage"]
)
def optimize_test_cases(project_id: str, req: TestOptimizeRequest, request: Request = None):
    """
    Performs deterministic test deduplication and redundancy detection.
    Groups tests by service, scenario, session, security level, and step requests.
    Safely eliminates duplicates while preserving full test coverage.
    """
    sess_id, uid, cip = _get_session_ctx(request)
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    if req.test_case_ids:
        test_cases = []
        for tc_id in req.test_case_ids:
            tc = test_case_store.get_test_case(project_id, tc_id)
            if tc:
                test_cases.append(tc)
    else:
        test_cases = test_case_store.list_test_cases(project_id)

    report = test_optimizer.optimize_test_suite(test_cases)

    activity_store.log_activity(
        session_id=sess_id,
        user_id=uid,
        project_id=project_id,
        action=ActivityAction.TEST_OPTIMIZED,
        endpoint=f"/api/v1/workspaces/{project_id}/optimize",
        http_method="POST",
        status="SUCCESS",
        client_ip=cip,
        metadata={
            "original_count": report.original_count,
            "retained_count": report.retained_count,
            "removed_duplicates_count": report.removed_duplicates_count,
            "deduplication_ratio_pct": report.deduplication_ratio_pct
        }
    )

    return OptimizationReportResponse(
        original_count=report.original_count,
        retained_count=report.retained_count,
        removed_duplicates_count=report.removed_duplicates_count,
        deduplication_ratio_pct=report.deduplication_ratio_pct,
        retained_test_ids=report.retained_test_ids,
        removed_test_details=[
            RemovedTestDetailResponse(
                test_case_id=r.test_case_id,
                duplicate_of_id=r.duplicate_of_id,
                service_id=r.service_id,
                service_hex=r.service_hex,
                test_type=r.test_type,
                reason=r.reason
            )
            for r in report.removed_test_details
        ],
        coverage_impact=report.coverage_impact
    )


# ==========================================
# Phase 5: Graph Traceability & Analytics Endpoints
# ==========================================

@router.get(
    "/workspaces/{project_id}/lineage/{node_id}",
    response_model=GraphLineageResponse,
    tags=["Graph Traceability & Lineage"]
)
def get_node_lineage(project_id: str, node_id: str, direction: str = "BIDIRECTIONAL"):
    """
    Retrieves bidirectional graph lineage or impact analysis for any diagnostic artifact.
    Direction: UPSTREAM (lineage to source specs), DOWNSTREAM (impact analysis), or BIDIRECTIONAL.
    """
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    # Synchronize current test cases, execution runs, and audit logs
    test_cases = test_case_store.list_test_cases(project_id)
    runs = execution_store.list_execution_results(project_id)
    audit_trail = governance_manager.get_audit_trail(project_id)
    graph_store.sync_workspace_artifacts(project_id, test_cases, runs, audit_trail)

    report = graph_store.get_lineage(node_id, project_id, direction=direction)

    return GraphLineageResponse(
        root_node_id=report.root_node_id,
        direction=report.direction,
        total_nodes=report.total_nodes,
        total_edges=report.total_edges,
        nodes=[
            GraphNodeModel(
                node_id=n.node_id,
                node_type=n.node_type,
                label=n.label,
                metadata=n.metadata,
                project_id=n.project_id,
                created_at=n.created_at
            )
            for n in report.nodes
        ],
        edges=[
            GraphEdgeModel(
                edge_id=e.edge_id,
                source_id=e.source_id,
                target_id=e.target_id,
                relation_type=e.relation_type,
                project_id=e.project_id,
                created_at=e.created_at
            )
            for e in report.edges
        ]
    )


@router.get(
    "/workspaces/{project_id}/analytics/metrics",
    response_model=EnterpriseMetricsResponse,
    tags=["Enterprise Telemetry & Analytics"]
)
def get_enterprise_metrics(project_id: str):
    """
    Computes real-time telemetry analytics for the 5 company-specified success metrics:
    1. Test Design Time (measured vs manual baseline)
    2. Generation Accuracy (measured rule pass rate vs target)
    3. Coverage Improvement (measured negative-pairing ratio vs target)
    4. Reuse Rate (measured template reuse vs target)
    5. Defect Detection (measured simulation defects & zero false pass verification;
       explicitly marked as requiring formal enterprise normalization methodology)
    """
    ws = workspace_manager.get_workspace(project_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace '{project_id}' not found.")

    test_cases = test_case_store.list_test_cases(project_id)
    metrics = analytics_engine.compute_metrics(project_id, test_cases)

    def _map_scorecard(m) -> SingleMetricResponse:
        return SingleMetricResponse(
            metric_name=m.metric_name,
            description=m.description,
            measured_value=m.measured_value,
            unit=m.unit,
            target_value=m.target_value,
            target_label=m.target_label,
            status=m.status,
            analysis_note=m.analysis_note
        )

    return EnterpriseMetricsResponse(
        project_id=metrics.project_id,
        computed_at=metrics.computed_at,
        test_design_time=_map_scorecard(metrics.test_design_time),
        generation_accuracy=_map_scorecard(metrics.generation_accuracy),
        coverage_improvement=_map_scorecard(metrics.coverage_improvement),
        reuse_rate=_map_scorecard(metrics.reuse_rate),
        defect_detection=_map_scorecard(metrics.defect_detection),
        total_test_cases=metrics.total_test_cases,
        total_execution_runs=metrics.total_execution_runs
    )


# ==========================================
# Admin Activity Telemetry Endpoints
# ==========================================

def verify_admin_access(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    admin_key: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    """
    Validates administrator credentials via header or query parameter.
    Enforces that activity telemetry is not accessible to unauthenticated public callers.
    """
    if not config.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator access key is not configured on the server (UDS_ADMIN_KEY environment variable required)."
        )

    provided_key = x_admin_key or admin_key
    if not provided_key and authorization and authorization.startswith("Bearer "):
        provided_key = authorization.split("Bearer ", 1)[1].strip()

    if not provided_key or provided_key != config.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing administrator access key."
        )
    return True


@router.get(
    "/admin/activity",
    response_model=ActivityListResponse,
    dependencies=[Depends(verify_admin_access)],
    tags=["Admin Activity Telemetry"]
)
def get_admin_activity_records(
    project_id: Optional[str] = None,
    action: Optional[str] = None,
    session_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0)
):
    """
    Retrieves filtered user activity telemetry records for authorized administrators.
    Protected by X-Admin-Key header or admin_key query parameter.
    """
    records = activity_store.get_events(
        project_id=project_id,
        action=action,
        session_id=session_id,
        status=status_filter,
        start_time=start_time,
        end_time=end_time,
        search_query=search,
        limit=limit,
        offset=offset
    )
    return ActivityListResponse(
        total_count=len(records),
        limit=limit,
        offset=offset,
        records=[
            ActivityRecordResponse(
                event_id=r.event_id,
                timestamp_utc=r.timestamp_utc,
                session_id=r.session_id,
                user_id=r.user_id,
                is_authenticated=r.is_authenticated,
                project_id=r.project_id,
                action=r.action,
                endpoint=r.endpoint,
                http_method=r.http_method,
                query_text=r.query_text,
                test_case_id=r.test_case_id,
                status=r.status,
                http_status_code=r.http_status_code,
                duration_ms=r.duration_ms,
                client_ip=r.client_ip,
                metadata=r.metadata
            )
            for r in records
        ]
    )


@router.get(
    "/admin/activity/summary",
    response_model=ActivitySummaryResponse,
    dependencies=[Depends(verify_admin_access)],
    tags=["Admin Activity Telemetry"]
)
def get_admin_activity_summary(project_id: Optional[str] = None):
    """
    Retrieves aggregate activity KPIs and telemetry breakdown for administrator dashboard.
    Protected by X-Admin-Key header or admin_key query parameter.
    """
    stats = activity_store.get_summary_stats(project_id=project_id)
    return ActivitySummaryResponse(**stats)


@router.get(
    "/admin/activity/queries",
    response_model=KnowledgeQueryHistoryResponse,
    dependencies=[Depends(verify_admin_access)],
    tags=["Admin Activity Telemetry"]
)
def get_admin_knowledge_query_history(
    project_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500)
):
    """
    Retrieves dedicated Knowledge Query History:
    Session | Query | Result | Time
    Protected by X-Admin-Key header or admin_key query parameter.
    """
    history = activity_store.get_knowledge_query_history(
        project_id=project_id,
        search_term=search,
        limit=limit
    )
    return KnowledgeQueryHistoryResponse(
        total_queries=len(history),
        queries=[KnowledgeQueryHistoryItem(**h) for h in history]
    )


@router.get(
    "/admin/activity/{event_id}",
    response_model=ActivityRecordResponse,
    dependencies=[Depends(verify_admin_access)],
    tags=["Admin Activity Telemetry"]
)
def get_admin_activity_event_detail(event_id: str):
    """
    Retrieves full detail of a specific activity event record.
    Protected by X-Admin-Key header or admin_key query parameter.
    """
    r = activity_store.get_event_by_id(event_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Activity event '{event_id}' not found.")
    return ActivityRecordResponse(
        event_id=r.event_id,
        timestamp_utc=r.timestamp_utc,
        session_id=r.session_id,
        user_id=r.user_id,
        is_authenticated=r.is_authenticated,
        project_id=r.project_id,
        action=r.action,
        endpoint=r.endpoint,
        http_method=r.http_method,
        query_text=r.query_text,
        test_case_id=r.test_case_id,
        status=r.status,
        http_status_code=r.http_status_code,
        duration_ms=r.duration_ms,
        client_ip=r.client_ip,
        metadata=r.metadata
    )





