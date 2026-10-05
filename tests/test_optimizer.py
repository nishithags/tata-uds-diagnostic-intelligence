"""
Unit and Integration Tests for Test Suite Optimizer, Deduplication Engine, and Coverage Matrix (Phase 4).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Tests:
- Deduplication of exact functional duplicate test cases with explicit audit rationale.
- Non-removal of functionally diverse test cases (different subfunctions, defect types, DIDs, sessions).
- Deterministic diagnostic coverage matrix across all 15 supported ISO 14229 services.
- Gap identification for uncovered services, missing positive cases, and missing negative cases.
- Zero coverage loss verification.
"""

import pytest
from src.core.generator import test_generator, TestCase, TestStep
from src.core.optimizer import (
    TestOptimizationEngine,
    test_optimizer,
    OptimizationReport,
    CoverageMatrixReport,
)
from src.core.rules import DiagnosticSession, SecurityLevel


class TestOptimizationAndDeduplication:
    """Test suite verifying deterministic deduplication and coverage preservation."""

    def test_deduplicate_exact_functional_duplicates(self):
        """Verify that identical test cases are deduplicated with explicit reason."""
        tc1 = test_generator.generate_positive_test(0x10, project_id="opt_proj", subfunction=1)
        # Duplicate with different ID but identical functional payload & preconditions
        tc2 = test_generator.generate_positive_test(0x10, project_id="opt_proj", subfunction=1)
        
        report = test_optimizer.optimize_test_suite([tc1, tc2])
        assert isinstance(report, OptimizationReport)
        assert report.original_count == 2
        assert report.retained_count == 1
        assert report.removed_duplicates_count == 1
        assert report.deduplication_ratio_pct == 50.0
        assert report.retained_test_ids == [tc1.test_case_id]

        assert len(report.removed_test_details) == 1
        detail = report.removed_test_details[0]
        assert detail.test_case_id == tc2.test_case_id
        assert detail.duplicate_of_id == tc1.test_case_id
        assert detail.service_hex == "0x10"
        assert "Identical functional test" in detail.reason

    def test_preserve_different_subfunctions(self):
        """Verify tests with different subfunctions (e.g. 0x01 Default vs 0x03 Extended) are NOT deduplicated."""
        tc_default = test_generator.generate_positive_test(0x10, project_id="opt_proj", subfunction=1)
        tc_extended = test_generator.generate_positive_test(0x10, project_id="opt_proj", subfunction=3)

        report = test_optimizer.optimize_test_suite([tc_default, tc_extended])
        assert report.original_count == 2
        assert report.retained_count == 2
        assert report.removed_duplicates_count == 0
        assert report.deduplication_ratio_pct == 0.0

    def test_preserve_different_defect_models(self):
        """Verify tests for different defect models (e.g. INVALID_SUBFUNCTION vs INCORRECT_LENGTH) are NOT deduplicated."""
        tc_neg_sf = test_generator.generate_negative_test(0x10, defect_type="INVALID_SUBFUNCTION", project_id="opt_proj")
        tc_neg_len = test_generator.generate_negative_test(0x10, defect_type="INCORRECT_LENGTH", project_id="opt_proj")

        report = test_optimizer.optimize_test_suite([tc_neg_sf, tc_neg_len])
        assert report.original_count == 2
        assert report.retained_count == 2
        assert report.removed_duplicates_count == 0

    def test_preserve_different_dids(self):
        """Verify ReadDID tests with different DIDs (0xF190 VIN vs 0x2001 Battery Voltage) are NOT deduplicated."""
        tc_vin = test_generator.generate_positive_test(0x22, project_id="opt_proj", did_hex="F190")
        tc_batt = test_generator.generate_positive_test(0x22, project_id="opt_proj", did_hex="2001")

        report = test_optimizer.optimize_test_suite([tc_vin, tc_batt])
        assert report.original_count == 2
        assert report.retained_count == 2
        assert report.removed_duplicates_count == 0

    def test_preserve_different_sessions(self):
        """Verify tests with different session preconditions are NOT deduplicated."""
        tc1 = test_generator.generate_positive_test(0x22, project_id="opt_proj", session=DiagnosticSession.DEFAULT)
        tc2 = test_generator.generate_positive_test(0x22, project_id="opt_proj", session=DiagnosticSession.EXTENDED)

        report = test_optimizer.optimize_test_suite([tc1, tc2])
        assert report.original_count == 2
        assert report.retained_count == 2
        assert report.removed_duplicates_count == 0

    def test_empty_test_collection_optimization(self):
        """Verify optimizer handles empty list safely."""
        report = test_optimizer.optimize_test_suite([])
        assert report.original_count == 0
        assert report.retained_count == 0
        assert report.removed_duplicates_count == 0
        assert report.deduplication_ratio_pct == 0.0


class TestDeterministicCoverageMatrix:
    """Test suite verifying coverage calculation across Service x Pos/Neg x Session x Security."""

    def test_coverage_matrix_all_15_services_registered(self):
        """Verify coverage matrix evaluates against all 15 supported ISO 14229 services."""
        matrix = test_optimizer.calculate_coverage([], project_id="cov_proj")
        assert isinstance(matrix, CoverageMatrixReport)
        assert matrix.total_services_in_scope == 15
        assert len(matrix.service_breakdown) == 15
        assert matrix.services_with_tests == 0
        assert matrix.service_coverage_pct == 0.0
        assert matrix.services_uncovered == 15

    def test_coverage_matrix_full_and_partial_tracking(self):
        """Verify full coverage (both positive and negative) vs partial coverage tracking."""
        # Service 0x10: both positive and negative tests
        tc_10_pos = test_generator.generate_positive_test(0x10, project_id="cov_proj")
        tc_10_neg = test_generator.generate_negative_test(0x10, defect_type="INVALID_SUBFUNCTION", project_id="cov_proj")

        # Service 0x22: only positive test
        tc_22_pos = test_generator.generate_positive_test(0x22, project_id="cov_proj")

        matrix = test_optimizer.calculate_coverage([tc_10_pos, tc_10_neg, tc_22_pos], project_id="cov_proj")
        assert matrix.total_tests == 3
        assert matrix.positive_tests_count == 2
        assert matrix.negative_tests_count == 1
        assert matrix.services_with_tests == 2
        assert matrix.services_full_coverage == 1  # 0x10
        assert matrix.services_partial_coverage == 1  # 0x22
        assert matrix.services_uncovered == 13

        # Check service 0x10 details
        s10 = next(s for s in matrix.service_breakdown if s.service_id == 0x10)
        assert s10.status == "FULL"
        assert s10.positive_count == 1
        assert s10.negative_count == 1
        assert len(s10.missing_aspects) == 0

        # Check service 0x22 details
        s22 = next(s for s in matrix.service_breakdown if s.service_id == 0x22)
        assert s22.status == "PARTIAL"
        assert s22.positive_count == 1
        assert s22.negative_count == 0
        assert any("Missing negative" in m for m in s22.missing_aspects)

    def test_coverage_gap_identification(self):
        """Verify uncovered combinations and gap detection without inventing data."""
        tc_10_pos = test_generator.generate_positive_test(0x10, project_id="cov_proj")
        matrix = test_optimizer.calculate_coverage([tc_10_pos], project_id="cov_proj")

        # Gaps should include missing negative for 0x10, plus missing positive and negative for uncovered services
        gaps = matrix.uncovered_combinations
        assert len(gaps) > 0
        s10_neg_gap = next((g for g in gaps if g["service_hex"] == "0x10" and g["gap_type"] == "MISSING_NEGATIVE"), None)
        assert s10_neg_gap is not None

        s27_pos_gap = next((g for g in gaps if g["service_hex"] == "0x27" and g["gap_type"] == "MISSING_POSITIVE"), None)
        assert s27_pos_gap is not None
