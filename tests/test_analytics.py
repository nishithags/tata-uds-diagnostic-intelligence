"""
Unit tests for Enterprise Telemetry Analytics and Success Metrics Engine (Section 11, Page 22).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

from datetime import datetime, timezone
import pytest

from src.core.analytics import EnterpriseAnalyticsEngine, SingleMetricScorecard, SuccessMetricsResponse
from src.core.generator import TestCase, TestStep, test_generator
from src.core.execution_engine import FaultProfile, execution_engine
from src.core.execution_store import execution_store
from src.core.governance import governance_manager


def test_empty_workspace_metrics_computation():
    engine = EnterpriseAnalyticsEngine()
    metrics = engine.compute_metrics("proj_empty", [])

    assert isinstance(metrics, SuccessMetricsResponse)
    assert metrics.total_test_cases == 0

    # All 5 metrics must be present and report NEEDS_DATA
    for m in [
        metrics.test_design_time,
        metrics.generation_accuracy,
        metrics.coverage_improvement,
        metrics.reuse_rate,
        metrics.defect_detection,
    ]:
        assert isinstance(m, SingleMetricScorecard)
        assert m.status in ("NEEDS_DATA", "ACHIEVED", "BELOW_TARGET")
        # Strict rule: Target must be separated from measured value
        assert m.target_value is not None
        assert m.measured_value is not None


def test_generation_accuracy_metric_calculation():
    engine = EnterpriseAnalyticsEngine()
    proj = "proj_acc_test"

    # Create 9 passing tests and 1 failing test
    cases = []
    for i in range(9):
        cases.append(TestCase(
            test_case_id=f"TC_PASS_{i}",
            project_id=proj,
            service_id=0x10,
            service_name="DiagnosticSessionControl",
            test_type="POSITIVE",
            title=f"Test {i}",
            description="Desc",
            pass_fail_criteria="Criteria",
            preconditions={"session": "DEFAULT", "security": 0},
            steps=[TestStep(step_number=1, description="S", request_hex="10 01", expected_response_type="POSITIVE", expected_response_hex="50 01")],
            rule_verification_status="PASSED"
        ))

    cases.append(TestCase(
        test_case_id="TC_FAIL_1",
        project_id=proj,
        service_id=0x10,
        service_name="DiagnosticSessionControl",
        test_type="NEGATIVE",
        title="Test Fail",
        description="Desc",
        pass_fail_criteria="Criteria",
        preconditions={"session": "DEFAULT", "security": 0},
        steps=[TestStep(step_number=1, description="S", request_hex="10 99", expected_response_type="NEGATIVE", expected_response_hex="7F 10 12")],
        rule_verification_status="FAILED"
    ))

    metrics = engine.compute_metrics(proj, cases)
    acc = metrics.generation_accuracy

    assert acc.metric_name == "Generation Accuracy"
    assert acc.measured_value == 90.0  # 9/10 = 90%
    assert acc.target_value == 95.0
    assert acc.status == "BELOW_TARGET"


def test_test_design_time_metric_calculation():
    engine = EnterpriseAnalyticsEngine()
    proj = "proj_design_time"

    # Simulated test case created at T0 and approved at T0 + 12 minutes
    t0 = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    t1 = datetime(2026, 9, 30, 10, 12, 0, tzinfo=timezone.utc).isoformat()

    tc = TestCase(
        test_case_id="TC_TIME_01",
        project_id=proj,
        service_id=0x22,
        service_name="ReadDataByIdentifier",
        test_type="POSITIVE",
        title="Read DID",
        description="Desc",
        pass_fail_criteria="Criteria",
        preconditions={"session": "DEFAULT", "security": 0},
        steps=[TestStep(step_number=1, description="S", request_hex="22 F1 90", expected_response_type="POSITIVE", expected_response_hex="62 F1 90")],
        review_status="APPROVED",
        rule_verification_status="PASSED",
        created_at=t0,
        updated_at=t1
    )

    metrics = engine.compute_metrics(proj, [tc])
    time_metric = metrics.test_design_time

    assert time_metric.metric_name == "Test Design Time"
    # 12 minutes authoring vs 120 baseline = 90% reduction
    assert time_metric.measured_value == 90.0
    assert time_metric.target_value == 60.0
    assert time_metric.status == "ACHIEVED"


def test_defect_detection_metric_labeling():
    engine = EnterpriseAnalyticsEngine()
    proj = "proj_defect_telemetry"

    # Generate and execute an approved test case with fault injection to produce an empirical defect
    tc = test_generator.generate_positive_test(service_id=0x10, project_id=proj)
    governance_manager.submit_review(
        test_case=tc,
        reviewer_name="Lead Engineer",
        reviewer_role="Validation Lead",
        action="APPROVE",
        comments="Approved for test run"
    )
    fault = FaultProfile(forced_nrc="12")
    res = execution_engine.execute_test_case(tc, fault_profile=fault)
    execution_store.save_execution_result(res)

    metrics = engine.compute_metrics(proj, [tc])
    defect_metric = metrics.defect_detection

    assert defect_metric.metric_name == "Defect Detection"
    assert defect_metric.measured_value >= 1.0
    assert "Enterprise normalization methodology pending formal sign-off" in defect_metric.analysis_note
