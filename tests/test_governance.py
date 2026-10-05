"""
Unit and Integration Tests for Governance and Review Lifecycle (Phase 2).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Verifies:
- Review lifecycle: DRAFT -> RULE_VERIFIED -> PENDING_REVIEW -> APPROVED / EDITED / REJECTED.
- Mandatory reviewer identification and non-empty comment enforcement.
- Strict downstream export/execution blocking for unapproved tests.
- Immutable audit trail logging and cross-artifact traceability.
- Workspace-isolated test case store persistence.
"""

import pytest
from pathlib import Path
from src.core.generator import test_generator
from src.core.governance import GovernanceError, GovernanceManager, governance_manager
from src.core.test_case_store import TestCaseStore


class TestGovernanceLifecycle:
    """Test suite verifying human review governance, execution guards, and audit trail."""

    @pytest.fixture
    def sample_test_case(self):
        """Generates a sample test case for governance testing."""
        return test_generator.generate_positive_test(
            service_id=0x10,
            project_id="test_gov_proj"
        )

    def test_approve_lifecycle_transition(self, sample_test_case):
        """Verify that formal approval transitions test case to APPROVED state."""
        assert sample_test_case.review_status == "PENDING_REVIEW"

        updated_tc, review_rec = governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="A. Sharma",
            reviewer_role="Validation Lead",
            action="APPROVE",
            comments="Verified against ISO 14229-1 DiagnosticSessionControl requirements."
        )

        assert updated_tc.review_status == "APPROVED"
        assert review_rec.reviewer_name == "A. Sharma"
        assert review_rec.action == "APPROVE"

    def test_edit_and_approve_lifecycle_transition(self, sample_test_case):
        """Verify that EDIT_AND_APPROVE updates metadata and sets status to APPROVED."""
        updated_tc, review_rec = governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="M. Verma",
            reviewer_role="Diagnostic Specialist",
            action="EDIT_AND_APPROVE",
            comments="Refined test title for clarity in OEM release package.",
            edited_title="Custom OEM DiagnosticSessionControl Default Test"
        )

        assert updated_tc.review_status == "APPROVED"
        assert updated_tc.title == "Custom OEM DiagnosticSessionControl Default Test"

    def test_reject_lifecycle_transition(self, sample_test_case):
        """Verify that rejection transitions test case to REJECTED state."""
        updated_tc, review_rec = governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="K. Patel",
            reviewer_role="Senior QA",
            action="REJECT",
            comments="Precondition session does not match OEM ECU bootloader requirements."
        )

        assert updated_tc.review_status == "REJECTED"

    def test_reviewer_name_mandatory(self, sample_test_case):
        """Verify that submitting a review without reviewer name raises GovernanceError."""
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.submit_review(
                test_case=sample_test_case,
                reviewer_name="",
                reviewer_role="Engineer",
                action="APPROVE",
                comments="Valid test"
            )
        assert "Reviewer name is mandatory" in str(excinfo.value)

    def test_review_comments_mandatory(self, sample_test_case):
        """Verify that submitting a review without rationale/comments raises GovernanceError."""
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.submit_review(
                test_case=sample_test_case,
                reviewer_name="Engineer A",
                reviewer_role="Engineer",
                action="APPROVE",
                comments="   "
            )
        assert "comments/rationales are required" in str(excinfo.value)

    def test_invalid_action_rejected(self, sample_test_case):
        """Verify that an invalid action keyword raises GovernanceError."""
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.submit_review(
                test_case=sample_test_case,
                reviewer_name="Engineer A",
                reviewer_role="Engineer",
                action="INVALID_ACTION",
                comments="Valid"
            )
        assert "Unknown review action" in str(excinfo.value)

    def test_execution_guardrail_blocks_unapproved_tests(self, sample_test_case):
        """
        Verify that assert_can_export_or_execute strictly raises GovernanceError
        for any test case that is not in APPROVED status.
        """
        # 1. PENDING_REVIEW should be blocked
        sample_test_case.review_status = "PENDING_REVIEW"
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.assert_can_export_or_execute(sample_test_case)
        assert "cannot be exported or executed" in str(excinfo.value)

        # 2. DRAFT should be blocked
        sample_test_case.review_status = "DRAFT"
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.assert_can_export_or_execute(sample_test_case)
        assert "cannot be exported or executed" in str(excinfo.value)

        # 3. REJECTED should be blocked
        sample_test_case.review_status = "REJECTED"
        with pytest.raises(GovernanceError) as excinfo:
            governance_manager.assert_can_export_or_execute(sample_test_case)
        assert "cannot be exported or executed" in str(excinfo.value)

        # 4. APPROVED should be permitted
        sample_test_case.review_status = "APPROVED"
        # Should not raise exception
        governance_manager.assert_can_export_or_execute(sample_test_case)

    def test_immutable_audit_trail_recorded(self, sample_test_case):
        """Verify that review submission generates audit trail entries."""
        governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="Auditor One",
            reviewer_role="Auditor",
            action="APPROVE",
            comments="Audit verification test."
        )

        audit_trail = governance_manager.get_audit_trail(project_id="test_gov_proj")
        assert len(audit_trail) > 0
        latest = audit_trail[-1]
        assert latest["performed_by"] == "Auditor One"
        assert latest["event_type"] == "REVIEW_SUBMITTED"
        assert latest["details"]["test_case_id"] == sample_test_case.test_case_id

    def test_test_case_store_workspace_partitioning(self, tmp_path):
        """Verify that TestCaseStore partitions test cases cleanly by workspace project_id."""
        store = TestCaseStore(storage_dir=tmp_path)
        tc_p1 = test_generator.generate_positive_test(0x10, project_id="proj_alpha")
        tc_p2 = test_generator.generate_positive_test(0x22, project_id="proj_beta")

        store.save_test_case(tc_p1)
        store.save_test_case(tc_p2)

        p1_cases = store.list_test_cases("proj_alpha")
        p2_cases = store.list_test_cases("proj_beta")

        assert len(p1_cases) == 1
        assert p1_cases[0].test_case_id == tc_p1.test_case_id
        assert len(p2_cases) == 1
        assert p2_cases[0].test_case_id == tc_p2.test_case_id
