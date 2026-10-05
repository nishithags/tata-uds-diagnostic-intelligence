"""
Governance and Human-in-the-Loop Review Manager for Phase 2.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Enforces company governance principle (Reference Solution Document, Section 13, Page 23):
"AI-generated content must be traceable to approved source material and reviewed by authorized
engineering specialists before it is used for compliance, design approval, software release,
or vehicle validation."

Lifecycle:
DRAFT -> RULE_VERIFIED -> PENDING_REVIEW -> APPROVED / EDITED / REJECTED

Strictly prevents unapproved tests from being exported or executed.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.core.config import config
from src.core.generator import TestCase


class GovernanceError(Exception):
    """Raised when an action violates the mandatory governance lifecycle or approval rules."""
    pass


class ReviewRecord(BaseModel):
    approval_id: str
    test_case_id: str
    reviewer_name: str
    reviewer_role: str
    action: str  # "APPROVED", "EDITED_AND_APPROVED", "REJECTED"
    review_comments: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditEvent(BaseModel):
    audit_id: str
    project_id: str
    event_type: str  # "TEST_GENERATED", "RULE_VERIFIED", "REVIEW_SUBMITTED", "EXPORT_ATTEMPT"
    performed_by: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TraceabilityEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relationship: str  # "VERIFIED_BY_RULE", "DERIVED_FROM_SPEC", "REVIEWED_BY_ENGINEER"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GovernanceManager:
    """
    Manages test case lifecycle states, reviewer sign-offs, immutable audit logs,
    and cross-artifact traceability.
    """

    def __init__(self, audit_dir: Optional[Path] = None):
        self.audit_dir = audit_dir or (config.data_dir / "audit_logs")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.audit_dir / "audit_trail.jsonl"
        self.traceability_file = self.audit_dir / "traceability_edges.jsonl"

    def log_audit(self, project_id: str, event_type: str, performed_by: str, details: Dict[str, Any]) -> AuditEvent:
        """Records an immutable audit event for regulatory and compliance tracking."""
        audit_id = f"aud_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        event = AuditEvent(
            audit_id=audit_id,
            project_id=project_id,
            event_type=event_type,
            performed_by=performed_by,
            details=details
        )
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
        return event

    def log_traceability_link(self, source_id: str, target_id: str, relationship: str) -> TraceabilityEdge:
        """Records a cross-artifact traceability link."""
        edge = TraceabilityEdge(
            edge_id=f"edge_{source_id}_{target_id}",
            source_id=source_id,
            target_id=target_id,
            relationship=relationship
        )
        with open(self.traceability_file, "a", encoding="utf-8") as f:
            f.write(edge.model_dump_json() + "\n")
        return edge

    def submit_review(
        self,
        test_case: TestCase,
        reviewer_name: str,
        reviewer_role: str,
        action: str,  # "APPROVE", "EDIT_AND_APPROVE", "REJECT"
        comments: str,
        edited_title: Optional[str] = None,
        edited_description: Optional[str] = None
    ) -> Tuple[TestCase, ReviewRecord]:
        """
        Processes formal engineer review and advances the lifecycle state.
        Enforces reviewer identification and non-empty engineering comments.
        """
        if not reviewer_name or not reviewer_name.strip():
            raise GovernanceError("Reviewer name is mandatory for formal sign-off.")
        if not comments or not comments.strip():
            raise GovernanceError("Engineering review comments/rationales are required.")

        normalized_action = action.upper().strip()
        approval_id = f"appr_{test_case.test_case_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if normalized_action == "APPROVE":
            test_case.review_status = "APPROVED"
        elif normalized_action == "EDIT_AND_APPROVE":
            test_case.review_status = "APPROVED"
            if edited_title:
                test_case.title = edited_title
            if edited_description:
                test_case.description = edited_description
        elif normalized_action == "REJECT":
            test_case.review_status = "REJECTED"
        else:
            raise GovernanceError(f"Unknown review action '{action}'. Must be APPROVE, EDIT_AND_APPROVE, or REJECT.")

        test_case.updated_at = datetime.now(timezone.utc).isoformat()

        review_record = ReviewRecord(
            approval_id=approval_id,
            test_case_id=test_case.test_case_id,
            reviewer_name=reviewer_name.strip(),
            reviewer_role=reviewer_role.strip() or "Diagnostic Validation Engineer",
            action=normalized_action,
            review_comments=comments.strip()
        )

        # Record audit log & traceability link
        self.log_audit(
            project_id=test_case.project_id,
            event_type="REVIEW_SUBMITTED",
            performed_by=reviewer_name.strip(),
            details={
                "test_case_id": test_case.test_case_id,
                "action": normalized_action,
                "new_status": test_case.review_status,
                "comments": comments.strip()
            }
        )
        self.log_traceability_link(
            source_id=test_case.test_case_id,
            target_id=reviewer_name.strip(),
            relationship="REVIEWED_BY_ENGINEER"
        )

        return test_case, review_record

    def assert_can_export_or_execute(self, test_case: TestCase) -> None:
        """
        Enforces company governance rule: unapproved tests cannot be exported or executed.
        Raises GovernanceError if review_status is not APPROVED.
        """
        if test_case.review_status != "APPROVED":
            self.log_audit(
                project_id=test_case.project_id,
                event_type="UNAPPROVED_EXECUTION_BLOCKED",
                performed_by="System Governance Guard",
                details={
                    "test_case_id": test_case.test_case_id,
                    "attempted_status": test_case.review_status
                }
            )
            raise GovernanceError(
                f"Governance Enforcement: Test case '{test_case.test_case_id}' cannot be exported or executed "
                f"because its status is '{test_case.review_status}'. "
                f"Only tests with status 'APPROVED' may be exported or scheduled for execution."
            )

    def get_audit_trail(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves audit trail entries, optionally filtered by project_id."""
        if not self.audit_file.exists():
            return []
        events = []
        with open(self.audit_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    ev = json.loads(line)
                    if project_id is None or ev.get("project_id") == project_id:
                        events.append(ev)
        return events


governance_manager = GovernanceManager()
