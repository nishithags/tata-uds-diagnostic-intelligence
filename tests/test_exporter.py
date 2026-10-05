"""
Unit and Integration Tests for Automation Script Exporter (Phase 4).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Tests:
- Export of approved test cases to Python (python-can / udsoncan approach).
- Export of approved test cases to Vector CANoe CAPL (.can).
- Strict governance guardrail: unapproved tests (DRAFT, RULE_VERIFIED, PENDING_REVIEW, REJECTED)
  CANNOT be exported and raise GovernanceError.
- Multi-test suite export with unapproved tests is strictly blocked.
- Traceability preservation: test IDs, titles, preconditions, citations, and reviewer attribution in code comments.
- Cryptographic SHA-256 integrity hash calculation and immutable audit logging (TEST_EXPORTED).
"""

import pytest
from src.core.exporter import AutomationScriptExporter, script_exporter, ExportArtifact
from src.core.generator import test_generator, TestCase
from src.core.governance import GovernanceError, governance_manager


class TestAutomationScriptExporter:
    """Test suite for Phase 4 automation script export and governance enforcement."""

    @pytest.fixture
    def sample_test_case(self):
        """Generates a positive 0x10 DiagnosticSessionControl test case."""
        return test_generator.generate_positive_test(0x10, project_id="export_test_proj", subfunction=3)

    @pytest.fixture
    def approved_test_case(self, sample_test_case):
        """Formally approves the sample test case."""
        approved_tc, _ = governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="Lead Validation Engineer",
            reviewer_role="Diagnostic Specialist",
            action="APPROVE",
            comments="Approved for automated Python and CAPL export."
        )
        return approved_tc

    # ==========================================
    # Governance Enforcement Tests
    # ==========================================

    def test_export_blocked_on_draft_test_case(self, sample_test_case):
        """Verify that DRAFT test case cannot be exported."""
        sample_test_case.review_status = "DRAFT"
        with pytest.raises(GovernanceError) as excinfo:
            script_exporter.export_test_case(sample_test_case, export_format="python_can_udsoncan")
        assert "Cannot export unapproved test cases" in str(excinfo.value)
        assert "DRAFT" in str(excinfo.value)

    def test_export_blocked_on_rule_verified_test_case(self, sample_test_case):
        """Verify that RULE_VERIFIED test case cannot be exported without human approval."""
        sample_test_case.review_status = "RULE_VERIFIED"
        with pytest.raises(GovernanceError) as excinfo:
            script_exporter.export_test_case(sample_test_case, export_format="python_can_udsoncan")
        assert "Cannot export unapproved test cases" in str(excinfo.value)

    def test_export_blocked_on_pending_review_test_case(self, sample_test_case):
        """Verify that PENDING_REVIEW test case cannot be exported."""
        assert sample_test_case.review_status == "PENDING_REVIEW"
        with pytest.raises(GovernanceError) as excinfo:
            script_exporter.export_test_case(sample_test_case, export_format="python_can_udsoncan")
        assert "Cannot export unapproved test cases" in str(excinfo.value)
        assert "PENDING_REVIEW" in str(excinfo.value)

    def test_export_blocked_on_rejected_test_case(self, sample_test_case):
        """Verify that REJECTED test case cannot be exported."""
        rejected_tc, _ = governance_manager.submit_review(
            test_case=sample_test_case,
            reviewer_name="QA Lead",
            reviewer_role="Tester",
            action="REJECT",
            comments="Rejecting due to incorrect baud rate."
        )
        assert rejected_tc.review_status == "REJECTED"
        with pytest.raises(GovernanceError) as excinfo:
            script_exporter.export_test_case(rejected_tc, export_format="python_can_udsoncan")
        assert "Cannot export unapproved test cases" in str(excinfo.value)
        assert "REJECTED" in str(excinfo.value)

    def test_export_suite_blocked_if_any_test_unapproved(self, approved_test_case):
        """Verify that exporting a suite containing even one unapproved test is completely blocked."""
        unapproved_tc = test_generator.generate_positive_test(0x22, project_id="export_test_proj")
        assert unapproved_tc.review_status == "PENDING_REVIEW"

        with pytest.raises(GovernanceError) as excinfo:
            script_exporter.export_test_suite(
                test_cases=[approved_test_case, unapproved_tc],
                export_format="python_can_udsoncan"
            )
        assert "Cannot export unapproved test cases" in str(excinfo.value)
        assert unapproved_tc.test_case_id in str(excinfo.value)

    # ==========================================
    # Python Script Export Tests
    # ==========================================

    def test_export_approved_python_script(self, approved_test_case):
        """Verify exporting approved test case to Python script."""
        artifact = script_exporter.export_test_case(
            test_case=approved_test_case,
            export_format="python_can_udsoncan",
            operator_name="Integration Engineer",
            file_name="test_session_control.py"
        )

        assert isinstance(artifact, ExportArtifact)
        assert artifact.export_format == "python_can_udsoncan"
        assert artifact.file_extension == ".py"
        assert artifact.artifact_name == "test_session_control.py"
        assert len(artifact.sha256_hash) == 64
        assert artifact.audit_id is not None

        code = artifact.code_content
        # Check standard python-can / udsoncan harness components
        assert "class UDSTestHarness:" in code
        assert "def send_raw_uds(" in code
        assert "python-can / udsoncan" in code

        # Check traceability and metadata
        assert approved_test_case.test_case_id in code
        assert approved_test_case.title in code
        assert "0x10" in code
        assert "DiagnosticSessionControl" in code

        # Check step assertions
        assert "req_bytes = bytes.fromhex" in code
        assert "assert resp_bytes[0] == 0x50" in code or "0x50" in code
        assert "run_full_suite()" in code

    def test_export_negative_defect_python_script(self):
        """Verify exporting negative defect test case with NRC assertions."""
        neg_tc = test_generator.generate_negative_test(
            service_id=0x10,
            defect_type="INVALID_SUBFUNCTION",
            project_id="export_test_proj"
        )
        approved_neg, _ = governance_manager.submit_review(
            test_case=neg_tc,
            reviewer_name="Safety Engineer",
            reviewer_role="QA Lead",
            action="APPROVE",
            comments="Approved negative defect verification test."
        )

        artifact = script_exporter.export_test_case(
            test_case=approved_neg,
            export_format="python_can_udsoncan"
        )
        code = artifact.code_content
        assert "Negative Response Verification (NRC 0x12)" in code
        assert "assert resp_bytes[0] == 0x7F" in code
        assert "assert resp_bytes[2] == 0x12" in code

    # ==========================================
    # Vector CANoe CAPL Script Export Tests
    # ==========================================

    def test_export_approved_capl_script(self, approved_test_case):
        """Verify exporting approved test case to Vector CANoe CAPL (.can)."""
        artifact = script_exporter.export_test_case(
            test_case=approved_test_case,
            export_format="canoe_capl",
            operator_name="CANoe Specialist",
            file_name="canoe_session_test.can"
        )

        assert isinstance(artifact, ExportArtifact)
        assert artifact.export_format == "canoe_capl"
        assert artifact.file_extension == ".can"
        assert artifact.artifact_name == "canoe_session_test.can"
        assert len(artifact.sha256_hash) == 64
        assert artifact.audit_id is not None

        capl_code = artifact.code_content
        # Check CANoe CAPL syntax elements
        assert "/*@!Encoding:1252*/" in capl_code
        assert "variables {" in capl_code
        assert "gDiagReqId  = 0x7E0;" in capl_code
        assert "gDiagRespId = 0x7E8;" in capl_code
        assert "testcase tc_" in capl_code
        assert "TestCaseTitle(" in capl_code
        assert "TestStep(" in capl_code
        assert "TestStepPass(" in capl_code
        assert "void MainTest()" in capl_code
        assert "TestGroupBegin(" in capl_code
        assert "TestGroupEnd();" in capl_code

        # Traceability
        assert approved_test_case.test_case_id in capl_code
        assert "ISO 14229" in capl_code

    def test_export_unsupported_format_raises_error(self, approved_test_case):
        """Verify that requesting an unsupported export format raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            script_exporter.export_test_case(
                test_case=approved_test_case,
                export_format="unsupported_format_xyz"
            )
        assert "Unsupported export format" in str(excinfo.value)

    # ==========================================
    # Audit Trail & Traceability
    # ==========================================

    def test_export_logs_immutable_audit_trail(self, approved_test_case):
        """Verify that every export operation logs a TEST_EXPORTED event in audit trail."""
        artifact = script_exporter.export_test_case(
            test_case=approved_test_case,
            export_format="python_can_udsoncan",
            operator_name="Audit Tester"
        )

        audit_trail = governance_manager.get_audit_trail("export_test_proj")
        export_events = [e for e in audit_trail if e["event_type"] == "TEST_EXPORTED"]
        assert len(export_events) >= 1
        latest = export_events[-1]
        assert latest["audit_id"] == artifact.audit_id
        assert latest["performed_by"] == "Audit Tester"
        assert latest["details"]["sha256_hash"] == artifact.sha256_hash
        assert latest["details"]["export_format"] == "python_can_udsoncan"
        assert approved_test_case.test_case_id in latest["details"]["test_case_ids"]
