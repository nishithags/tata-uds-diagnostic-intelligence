"""
Pydantic API Schemas for Phase 1 & Phase 2.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==========================================
# Workspace & Ingestion Models
# ==========================================

class WorkspaceCreateRequest(BaseModel):
    project_id: str = Field(..., description="Unique workspace/project identifier, e.g. 'proj_uds_bcm'")
    name: str = Field(..., description="Project human-readable title")
    description: Optional[str] = Field(default="", description="Optional project description")
    oem_name: Optional[str] = Field(default="Generic OEM", description="Target OEM name")
    ecu_model: Optional[str] = Field(default="Generic ECU", description="Target ECU model name")


class WorkspaceResponse(BaseModel):
    project_id: str
    name: str
    description: str
    oem_name: str
    ecu_model: str
    created_at: str
    documents_count: int = 0
    chunks_count: int = 0


class DocumentMetadataResponse(BaseModel):
    doc_id: str
    project_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    file_hash_sha256: str
    total_pages: int
    total_chunks: int
    ingested_at: str
    authorization_status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    status: str
    message: str
    document: DocumentMetadataResponse


class DocumentListResponse(BaseModel):
    project_id: str
    total_documents: int
    documents: List[DocumentMetadataResponse]


class CitationResponseModel(BaseModel):
    chunk_id: str
    doc_id: str
    project_id: str
    document_name: str
    page_number: int
    section_title: str
    text_snippet: str
    relevance_score: float
    distance: float
    source_hash_sha256: str


class KnowledgeQueryRequest(BaseModel):
    project_id: str = Field(..., description="Workspace ID to restrict query scope")
    query: str = Field(..., description="Diagnostic query text, e.g. 'ReadDataByIdentifier extended session rules'")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of citations to retrieve")


class KnowledgeQueryResponse(BaseModel):
    project_id: str
    query: str
    answer: str
    citations: List[CitationResponseModel]
    total_citations: int
    model_identifier: str
    llm_decision_status: str
    disclaimer: str


# ==========================================
# Phase 2: Rule Engine & Test Generation Models
# ==========================================

class RuleCheckItem(BaseModel):
    rule_code: str
    rule_name: str
    passed: bool
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class ValidationReportResponse(BaseModel):
    overall_verdict: str  # "PASS" or "FAIL"
    service_id: int
    service_hex: str
    service_name: str
    checks: List[RuleCheckItem]
    errors: List[str]
    warnings: List[str]


class TestStepModel(BaseModel):
    step_number: int
    description: str
    request_hex: str
    expected_response_type: str
    expected_response_hex: str
    expected_nrc: Optional[str] = None
    timeout_ms: int = 2000
    suppress_pos_rsp: bool = False


class TestCaseResponse(BaseModel):
    test_case_id: str
    project_id: str
    service_id: int
    service_name: str
    test_type: str
    title: str
    description: str
    preconditions: Dict[str, Any]
    steps: List[TestStepModel]
    pass_fail_criteria: str
    rule_verification_status: str
    rule_verification_report: Optional[ValidationReportResponse] = None
    review_status: str
    citation_references: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class TestGenerateRequest(BaseModel):
    service_id: int = Field(..., description="ISO 14229 Service ID, e.g. 0x10, 0x22, 0x27, 0x2E")
    test_scenario: str = Field(
        default="POSITIVE",
        description="Scenario: 'POSITIVE', 'NEGATIVE_SUBFUNCTION', 'NEGATIVE_LENGTH', 'NEGATIVE_SESSION', 'NEGATIVE_SECURITY', 'SUITE'"
    )
    subfunction: Optional[int] = Field(default=None, description="Optional subfunction byte")
    did_hex: Optional[str] = Field(default=None, description="Optional DID hex, e.g. 'F190'")
    session: str = Field(default="DEFAULT", description="Precondition session: 'DEFAULT', 'EXTENDED', 'PROGRAMMING'")
    security: int = Field(default=0, description="Precondition security level (0=Locked, 1=Level 1)")


class TestReviewRequest(BaseModel):
    reviewer_name: str = Field(..., description="Name of authorized diagnostic engineer")
    reviewer_role: str = Field(default="Diagnostic Validation Specialist", description="Engineering role")
    action: str = Field(..., description="Action: 'APPROVE', 'EDIT_AND_APPROVE', 'REJECT'")
    comments: str = Field(..., description="Mandatory engineering rationale or review notes")
    edited_title: Optional[str] = None
    edited_description: Optional[str] = None


class CustomValidateRequest(BaseModel):
    request_hex: str = Field(..., description="Raw hex request frame, e.g. '22 F1 90'")
    session: str = Field(default="DEFAULT", description="Active session: 'DEFAULT', 'EXTENDED', 'PROGRAMMING'")
    security: int = Field(default=0, description="Active security level: 0, 1, 2")
    expected_response_type: str = Field(default="POSITIVE", description="'POSITIVE' or 'NEGATIVE'")
    expected_nrc: Optional[str] = Field(default=None, description="Expected NRC if NEGATIVE, e.g. '0x33'")


class AuditLogResponse(BaseModel):
    audit_id: str
    project_id: str
    event_type: str
    performed_by: str
    details: Dict[str, Any]
    created_at: str


# ==========================================
# Phase 3: Simulated ECU & Execution Models
# ==========================================

class FaultProfileModel(BaseModel):
    forced_nrc: Optional[int] = Field(default=None, description="Optional forced NRC, e.g. 0x22 or 0x33")
    response_delay_ms: int = Field(default=0, description="Synthetic latency in ms")
    inject_response_pending: bool = Field(default=False, description="Emit NRC 0x78 before response")
    corrupt_response_length: bool = Field(default=False, description="Simulate corrupted response length")
    drop_response: bool = Field(default=False, description="Simulate dropped frame / timeout")


class TestExecuteRequest(BaseModel):
    operator_name: str = Field(default="Automated Test Runner", description="Executing engineer / system identity")
    fault_profile: Optional[FaultProfileModel] = None


class ECUStateResponse(BaseModel):
    session: str
    security_level: int
    security_locked: bool
    seed_pending: bool
    failed_security_attempts: int
    dtc_count: int
    s3_timer_active: bool
    supported_services_count: int


class StepExecutionResponse(BaseModel):
    step_number: int
    description: str
    request_hex: str
    actual_response_hex: str
    expected_response_type: str
    expected_response_hex: str
    expected_nrc: Optional[str] = None
    actual_nrc: Optional[str] = None
    elapsed_ms: float
    timeout_ms: int
    timing_verdict: str
    step_verdict: str
    error_message: Optional[str] = None
    trace_logs: List[str] = Field(default_factory=list)


class TestCaseExecutionResponse(BaseModel):
    execution_id: str
    test_case_id: str
    project_id: str
    title: str
    test_type: str
    overall_verdict: str
    preconditions: Dict[str, Any]
    initial_ecu_state: ECUStateResponse
    final_ecu_state: ECUStateResponse
    total_elapsed_ms: float
    steps_total: int
    steps_passed: int
    step_results: List[StepExecutionResponse]
    governance_verified: bool
    executed_at: str
    audit_id: Optional[str] = None


# ==========================================
# Phase 4: Automation Export & Optimization Models
# ==========================================

class TestExportRequest(BaseModel):
    test_case_ids: List[str] = Field(..., description="List of approved test case IDs to export")
    format: str = Field(default="python_can_udsoncan", description="Export target: python_can_udsoncan or canoe_capl")
    operator_name: str = Field(default="Validation Engineer", description="Engineer performing the export")
    file_name: Optional[str] = Field(default=None, description="Optional custom export file name")


class TestExportResponse(BaseModel):
    artifact_name: str
    export_format: str
    file_extension: str
    code_content: str
    test_case_ids: List[str]
    total_steps: int
    generated_at: str
    exported_by: str
    sha256_hash: str
    audit_id: Optional[str] = None


class ServiceCoverageResponse(BaseModel):
    service_id: int
    service_hex: str
    service_name: str
    positive_count: int
    negative_count: int
    total_tests: int
    tested_sessions: List[str]
    tested_security_levels: List[int]
    defect_types_covered: List[str]
    status: str
    missing_aspects: List[str]


class CoverageReportResponse(BaseModel):
    project_id: str
    total_services_in_scope: int
    services_with_tests: int
    services_full_coverage: int
    services_partial_coverage: int
    services_uncovered: int
    service_coverage_pct: float
    total_tests: int
    positive_tests_count: int
    negative_tests_count: int
    sessions_exercised: List[str]
    security_levels_exercised: List[int]
    service_breakdown: List[ServiceCoverageResponse]
    uncovered_combinations: List[Dict[str, Any]]


class TestOptimizeRequest(BaseModel):
    test_case_ids: Optional[List[str]] = Field(default=None, description="Optional subset of test IDs to optimize; defaults to all workspace tests")


class RemovedTestDetailResponse(BaseModel):
    test_case_id: str
    duplicate_of_id: str
    service_id: int
    service_hex: str
    test_type: str
    reason: str


class OptimizationReportResponse(BaseModel):
    original_count: int
    retained_count: int
    removed_duplicates_count: int
    deduplication_ratio_pct: float
    retained_test_ids: List[str]
    removed_test_details: List[RemovedTestDetailResponse]
    coverage_impact: str


# ==========================================
# Phase 5: Graph Traceability & Analytics Models
# ==========================================

class GraphNodeModel(BaseModel):
    node_id: str
    node_type: str
    label: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    project_id: str
    created_at: str


class GraphEdgeModel(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relation_type: str
    project_id: str
    created_at: str


class GraphLineageResponse(BaseModel):
    root_node_id: str
    direction: str
    total_nodes: int
    total_edges: int
    nodes: List[GraphNodeModel]
    edges: List[GraphEdgeModel]


class SingleMetricResponse(BaseModel):
    metric_name: str
    description: str
    measured_value: float
    unit: str
    target_value: float
    target_label: str
    status: str
    analysis_note: str


class EnterpriseMetricsResponse(BaseModel):
    project_id: str
    computed_at: str
    test_design_time: SingleMetricResponse
    generation_accuracy: SingleMetricResponse
    coverage_improvement: SingleMetricResponse
    reuse_rate: SingleMetricResponse
    defect_detection: SingleMetricResponse
    total_test_cases: int
    total_execution_runs: int


# ==========================================
# Phase Activity & Admin Dashboard Models
# ==========================================

class ActivityRecordResponse(BaseModel):
    event_id: str
    timestamp_utc: str
    session_id: str
    user_id: Optional[str] = None
    is_authenticated: bool = False
    project_id: Optional[str] = None
    action: str
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    query_text: Optional[str] = None
    test_case_id: Optional[str] = None
    status: str
    http_status_code: Optional[int] = None
    duration_ms: float = 0.0
    client_ip: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActivityListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    records: List[ActivityRecordResponse]


class ActivitySummaryResponse(BaseModel):
    total_events: int
    unique_sessions: int
    unique_authenticated_users: int
    unique_anonymous_sessions: int
    knowledge_queries_count: int
    tests_generated_count: int
    tests_executed_count: int
    exports_count: int
    success_count: int
    failure_count: int
    action_breakdown: Dict[str, int]


class KnowledgeQueryHistoryItem(BaseModel):
    event_id: str
    session_id: str
    user_id: str
    is_authenticated: bool
    query: str
    result: str
    citations_count: int
    time: str
    timestamp_utc: str
    project_id: str
    status: str
    duration_ms: float


class KnowledgeQueryHistoryResponse(BaseModel):
    total_queries: int
    queries: List[KnowledgeQueryHistoryItem]




