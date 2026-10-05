"""
Unit and Integration Tests for Controlled Test Execution Engine (Phase 3).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Verifies:
- Mandatory Governance Guard: strictly blocks execution of DRAFT, RULE_VERIFIED,
  PENDING_REVIEW, and REJECTED tests, raising GovernanceError.
- Execution of APPROVED positive test cases (0x10, 0x22, 0x27, etc.) with PASS verdict.
- Controlled negative test execution across all Phase 2 defect models:
  INVALID_SUBFUNCTION (NRC 0x12), INCORRECT_LENGTH (NRC 0x13),
  SESSION_VIOLATION (NRC 0x22 / 0x7F), SECURITY_LOCKED (NRC 0x33),
  DID_OUT_OF_RANGE (NRC 0x31).
- P2 / P2* response timing compliance and timeout detection.
- Fault injection: forced NRC, response drops, and timing delays.
- Immutable audit trail logging (TEST_EXECUTED) and ExecutionStore persistence.
"""

import pytest
import time
from src.core.generator import test_generator, TestCase, TestStep
from src.core.governance import GovernanceError, governance_manager
from src.core.rules import DiagnosticSession, SecurityLevel
from src.core.simulator import FaultProfile, SimulatedECU
from src.core.execution_engine import (
    TestExecutionEngine,
    SimulatedECUAdapter,
    TestCaseExecutionResult,
    StepExecutionResult,
)
from src.core.execution_store import ExecutionStore


class TestExecutionGovernanceGuard:
    """Verifies that the execution engine strictly blocks unapproved test cases."""

    @pytest.fixture
    def engine(self):
        ecu = SimulatedECU()
        adapter = SimulatedECUAdapter(ecu=ecu)
        return TestExecutionEngine(adapter=adapter)

    def test_block_draft_test_case_execution(self, engine):
        """Verify DRAFT test case cannot execute."""
        tc = test_generator.generate_positive_test(0x10, project_id="exec_gov_proj")
        tc.review_status = "DRAFT"
        with pytest.raises(GovernanceError) as excinfo:
            engine.execute_test_case(tc)
        assert "cannot be exported or executed" in str(excinfo.value)
        assert "DRAFT" in str(excinfo.value)

    def test_block_rule_verified_test_case_execution(self, engine):
        """Verify RULE_VERIFIED test case cannot execute without human review."""
        tc = test_generator.generate_positive_test(0x10, project_id="exec_gov_proj")
        tc.review_status = "RULE_VERIFIED"
        with pytest.raises(GovernanceError) as excinfo:
            engine.execute_test_case(tc)
        assert "cannot be exported or executed" in str(excinfo.value)

    def test_block_pending_review_test_case_execution(self, engine):
        """Verify PENDING_REVIEW test case cannot execute."""
        tc = test_generator.generate_positive_test(0x10, project_id="exec_gov_proj")
        assert tc.review_status == "PENDING_REVIEW"
        with pytest.raises(GovernanceError) as excinfo:
            engine.execute_test_case(tc)
        assert "cannot be exported or executed" in str(excinfo.value)

    def test_block_rejected_test_case_execution(self, engine):
        """Verify REJECTED test case cannot execute."""
        tc = test_generator.generate_positive_test(0x10, project_id="exec_gov_proj")
        tc_rejected, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="QA Lead",
            reviewer_role="Validation Engineer",
            action="REJECT",
            comments="Rejected due to invalid timing configuration."
        )
        assert tc_rejected.review_status == "REJECTED"
        with pytest.raises(GovernanceError) as excinfo:
            engine.execute_test_case(tc_rejected)
        assert "cannot be exported or executed" in str(excinfo.value)

    def test_allow_approved_test_case_execution(self, engine):
        """Verify that formally APPROVED test case successfully executes."""
        tc = test_generator.generate_positive_test(0x10, project_id="exec_gov_proj")
        tc_approved, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="Lead Engineer",
            reviewer_role="Diagnostic Lead",
            action="APPROVE",
            comments="Verified against ISO 14229 specification."
        )
        assert tc_approved.review_status == "APPROVED"
        result = engine.execute_test_case(tc_approved)
        assert result.overall_verdict == "PASS"
        assert result.governance_verified is True
        assert result.steps_passed == len(tc_approved.steps)


class TestControlledExecutionPositiveScenarios:
    """Verifies execution of approved positive test cases across UDS services."""

    @pytest.fixture
    def setup_engine(self):
        ecu = SimulatedECU()
        adapter = SimulatedECUAdapter(ecu=ecu)
        engine = TestExecutionEngine(adapter=adapter)
        return engine, ecu

    def _approve_test_case(self, tc: TestCase) -> TestCase:
        approved, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="System Engineer",
            reviewer_role="Test Specialist",
            action="APPROVE",
            comments="Approved for automated execution."
        )
        return approved

    def test_execute_session_control_positive(self, setup_engine):
        """Verify execution of positive 0x10 DiagnosticSessionControl."""
        engine, ecu = setup_engine
        tc = test_generator.generate_positive_test(0x10, project_id="exec_pos_proj", subfunction=3)
        approved_tc = self._approve_test_case(tc)

        result = engine.execute_test_case(approved_tc)
        assert result.overall_verdict == "PASS"
        assert result.steps_total == 1
        assert result.steps_passed == 1
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.timing_verdict == "PASS"
        assert step.actual_response_hex.startswith("50 03")
        assert result.final_ecu_state.session == "EXTENDED"

    def test_execute_read_did_positive(self, setup_engine):
        """Verify execution of positive 0x22 ReadDataByIdentifier."""
        engine, ecu = setup_engine
        tc = test_generator.generate_positive_test(0x22, project_id="exec_pos_proj")
        approved_tc = self._approve_test_case(tc)

        result = engine.execute_test_case(approved_tc)
        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_response_hex.startswith("62 F1 90")

    def test_execute_tester_present_positive(self, setup_engine):
        """Verify execution of positive 0x3E TesterPresent."""
        engine, ecu = setup_engine
        tc = test_generator.generate_positive_test(0x3E, project_id="exec_pos_proj")
        approved_tc = self._approve_test_case(tc)

        result = engine.execute_test_case(approved_tc)
        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_response_hex == "7E 00"

    def test_execute_security_access_seed_and_key(self, setup_engine):
        """Verify execution of 0x27 SecurityAccess request seed followed by send key."""
        engine, ecu = setup_engine
        # Create a test case: request seed (0x01)
        step1 = TestStep(
            step_number=1,
            description="Request Seed (Level 1)",
            request_hex="27 01",
            expected_response_type="POSITIVE",
            expected_response_hex="67 01",
            timeout_ms=500
        )
        tc = TestCase(
            test_case_id="tc_sec_flow_001",
            project_id="exec_pos_proj",
            service_id=0x27,
            service_name="SecurityAccess",
            test_type="POSITIVE",
            title="Security Access Seed Flow",
            description="Request seed from ECU",
            preconditions={"session": "EXTENDED", "security": 0},
            steps=[step1],
            pass_fail_criteria="ECU shall return positive response 0x67 0x01 with 4-byte seed.",
            rule_verification_status="PASSED",
            review_status="APPROVED"
        )
        result = engine.execute_test_case(tc)
        assert result.overall_verdict == "PASS"
        assert result.step_results[0].step_verdict == "PASS"
        assert result.step_results[0].actual_response_hex.startswith("67 01")


class TestControlledExecutionDefectModels:
    """Verifies negative test execution against all Phase 2 defect models."""

    @pytest.fixture
    def setup_engine(self):
        ecu = SimulatedECU()
        adapter = SimulatedECUAdapter(ecu=ecu)
        engine = TestExecutionEngine(adapter=adapter)
        return engine, ecu

    def _approve_test_case(self, tc: TestCase) -> TestCase:
        approved, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="Defect Analyst",
            reviewer_role="Safety Engineer",
            action="APPROVE",
            comments="Approved negative defect verification test."
        )
        return approved

    def test_negative_invalid_subfunction_nrc12(self, setup_engine):
        """Defect Model: INVALID_SUBFUNCTION -> NRC 0x12."""
        engine, _ = setup_engine
        tc = test_generator.generate_negative_test(
            service_id=0x10,
            defect_type="INVALID_SUBFUNCTION",
            project_id="exec_neg_proj"
        )
        approved_tc = self._approve_test_case(tc)
        result = engine.execute_test_case(approved_tc)

        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_nrc == "0x12"
        assert step.actual_response_hex == "7F 10 12"

    def test_negative_incorrect_length_nrc13(self, setup_engine):
        """Defect Model: INCORRECT_LENGTH -> NRC 0x13."""
        engine, _ = setup_engine
        tc = test_generator.generate_negative_test(
            service_id=0x10,
            defect_type="INCORRECT_LENGTH",
            project_id="exec_neg_proj"
        )
        approved_tc = self._approve_test_case(tc)
        result = engine.execute_test_case(approved_tc)

        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_nrc == "0x13"
        assert step.actual_response_hex == "7F 10 13"

    def test_negative_session_violation_nrc22(self, setup_engine):
        """Defect Model: SESSION_VIOLATION -> NRC 0x7F / 0x22 (ConditionsNotCorrect)."""
        engine, _ = setup_engine
        tc = test_generator.generate_negative_test(
            service_id=0x27,
            defect_type="SESSION_VIOLATION",
            project_id="exec_neg_proj",
            session=DiagnosticSession.DEFAULT
        )
        approved_tc = self._approve_test_case(tc)
        result = engine.execute_test_case(approved_tc)

        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_nrc in ("0x7F", "0x22")
        assert step.actual_response_hex.startswith("7F 27")

    def test_negative_security_locked_nrc33(self, setup_engine):
        """Defect Model: SECURITY_LOCKED -> NRC 0x33 (SecurityAccessDenied)."""
        engine, _ = setup_engine
        tc = test_generator.generate_negative_test(
            service_id=0x2E,
            defect_type="SECURITY_LOCKED",
            project_id="exec_neg_proj",
            session=DiagnosticSession.EXTENDED,
            security=SecurityLevel.LOCKED
        )
        approved_tc = self._approve_test_case(tc)
        result = engine.execute_test_case(approved_tc)

        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_nrc == "0x33"
        assert step.actual_response_hex == "7F 2E 33"

    def test_negative_did_out_of_range_nrc31(self, setup_engine):
        """Defect Model: DID_OUT_OF_RANGE -> NRC 0x31 (RequestOutOfRange)."""
        engine, _ = setup_engine
        tc = test_generator.generate_negative_test(
            service_id=0x22,
            defect_type="DID_OUT_OF_RANGE",
            project_id="exec_neg_proj"
        )
        approved_tc = self._approve_test_case(tc)
        result = engine.execute_test_case(approved_tc)

        assert result.overall_verdict == "PASS"
        step = result.step_results[0]
        assert step.step_verdict == "PASS"
        assert step.actual_nrc == "0x31"
        assert step.actual_response_hex == "7F 22 31"


class TestFaultInjectionAndTiming:
    """Verifies runtime fault injection and P2/P2* timeout detection."""

    @pytest.fixture
    def setup_engine(self):
        ecu = SimulatedECU()
        adapter = SimulatedECUAdapter(ecu=ecu)
        engine = TestExecutionEngine(adapter=adapter)
        return engine, ecu

    def _approve_test_case(self, tc: TestCase) -> TestCase:
        approved, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="Fault Injector",
            reviewer_role="Test Specialist",
            action="APPROVE",
            comments="Approved for fault injection verification."
        )
        return approved

    def test_fault_injection_forced_nrc_causes_positive_test_to_fail(self, setup_engine):
        """When an unexpected NRC is injected into a positive test, execution must FAIL."""
        engine, _ = setup_engine
        tc = test_generator.generate_positive_test(0x10, project_id="fault_proj")
        approved_tc = self._approve_test_case(tc)

        # Force NRC 0x10 (GeneralReject)
        fault = FaultProfile(forced_nrc=0x10)
        result = engine.execute_test_case(approved_tc, fault_profile=fault)

        assert result.overall_verdict == "FAIL"
        step = result.step_results[0]
        assert step.step_verdict == "FAIL"
        assert step.actual_nrc == "0x10"
        assert "Expected positive response" in (step.error_message or "")

    def test_fault_injection_dropped_response_causes_fail(self, setup_engine):
        """When ECU drops the response frame, execution must FAIL."""
        engine, _ = setup_engine
        tc = test_generator.generate_positive_test(0x10, project_id="fault_proj")
        approved_tc = self._approve_test_case(tc)

        fault = FaultProfile(drop_response=True)
        result = engine.execute_test_case(approved_tc, fault_profile=fault)

        assert result.overall_verdict == "FAIL"
        step = result.step_results[0]
        assert step.step_verdict == "FAIL"
        assert step.actual_response_hex == ""

    def test_response_timeout_timing_verdict(self, setup_engine):
        """When response elapsed time exceeds step.timeout_ms, timing_verdict is TIMEOUT and step FAILS."""
        engine, _ = setup_engine
        tc = test_generator.generate_positive_test(0x10, project_id="fault_proj")
        # Set artificially small timeout (10ms)
        tc.steps[0].timeout_ms = 10
        approved_tc = self._approve_test_case(tc)

        # Inject 30ms latency (> 10ms timeout)
        fault = FaultProfile(response_delay_ms=30)
        result = engine.execute_test_case(approved_tc, fault_profile=fault)

        assert result.overall_verdict == "FAIL"
        step = result.step_results[0]
        assert step.timing_verdict == "TIMEOUT"
        assert step.step_verdict == "FAIL"
        assert "Response timeout" in (step.error_message or "")


class TestExecutionStoreAndAudit:
    """Verifies persistence of execution runs and immutable audit logging."""

    def test_execution_store_save_and_retrieve(self, tmp_path):
        """Verify ExecutionStore correctly persists and loads execution runs."""
        store = ExecutionStore(storage_dir=tmp_path)
        ecu = SimulatedECU()
        adapter = SimulatedECUAdapter(ecu=ecu)
        engine = TestExecutionEngine(adapter=adapter)

        tc = test_generator.generate_positive_test(0x10, project_id="store_test_proj")
        approved_tc, _ = governance_manager.submit_review(
            test_case=tc,
            reviewer_name="Audit Auditor",
            reviewer_role="QA Lead",
            action="APPROVE",
            comments="Approved for store verification."
        )

        result = engine.execute_test_case(approved_tc)
        store.save_execution_result(result)

        # Retrieve
        loaded = store.get_execution_result("store_test_proj", result.execution_id)
        assert loaded is not None
        assert loaded.execution_id == result.execution_id
        assert loaded.overall_verdict == "PASS"
        assert len(loaded.step_results) == 1

        # List
        runs = store.list_execution_results("store_test_proj")
        assert len(runs) == 1
        assert runs[0].execution_id == result.execution_id

        # Verify audit log was recorded
        audit_trail = governance_manager.get_audit_trail("store_test_proj")
        exec_events = [e for e in audit_trail if e["event_type"] == "TEST_EXECUTED"]
        assert len(exec_events) >= 1
        assert exec_events[-1]["details"]["test_case_id"] == approved_tc.test_case_id
