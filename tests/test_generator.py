"""
Unit and Integration Tests for UDS Test Generator Module (Phase 2).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Verifies:
- Positive and negative scenario generation across ISO 14229 services.
- Immediate deterministic rule engine validation of generated frames.
- Proper NRC mapping for complementary negative test scenarios.
- Suite generation with complete fault-injection permutations.
- Specification citation reference preservation.
"""

import pytest
from src.core.generator import (
    AssembledPrompt,
    build_test_generation_prompt,
    test_generator,
    TestCase,
)
from src.core.rules import DiagnosticSession, SecurityLevel


class TestUDSTestGenerator:
    """Test suite verifying automated positive and negative test generation."""

    def test_generate_positive_test_session_control(self):
        """Verify nominal positive test generation for 0x10 DiagnosticSessionControl."""
        tc = test_generator.generate_positive_test(
            service_id=0x10,
            project_id="test_proj_01",
            subfunction=0x01
        )
        assert isinstance(tc, TestCase)
        assert tc.service_id == 0x10
        assert tc.test_type == "POSITIVE"
        assert tc.rule_verification_status == "PASSED"
        assert tc.review_status == "PENDING_REVIEW"
        assert len(tc.steps) == 1
        assert tc.steps[0].request_hex == "10 01"
        assert tc.steps[0].expected_response_type == "POSITIVE"
        assert tc.rule_verification_report is not None
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_positive_test_read_data_by_id(self):
        """Verify nominal positive test generation for 0x22 ReadDataByIdentifier."""
        tc = test_generator.generate_positive_test(
            service_id=0x22,
            project_id="test_proj_01",
            did_hex="F190"
        )
        assert tc.service_id == 0x22
        assert tc.steps[0].request_hex == "22 F190"
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_positive_test_write_data_by_id(self):
        """Verify nominal positive test generation for 0x2E WriteDataByIdentifier with security."""
        tc = test_generator.generate_positive_test(
            service_id=0x2E,
            project_id="test_proj_01",
            did_hex="2001",
            session=DiagnosticSession.EXTENDED,
            security=SecurityLevel.LEVEL_1
        )
        assert tc.service_id == 0x2E
        assert tc.steps[0].request_hex == "2E 2001 00 64"
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_negative_subfunction_nrc12(self):
        """Verify negative test generation for invalid subfunction mapping to NRC 0x12."""
        tc = test_generator.generate_negative_test(
            service_id=0x10,
            defect_type="INVALID_SUBFUNCTION",
            project_id="test_proj_01"
        )
        assert tc.test_type == "NEGATIVE_INVALID_SUBFUNCTION"
        assert tc.steps[0].expected_response_type == "NEGATIVE"
        assert tc.steps[0].expected_nrc == "0x12"
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_negative_length_nrc13(self):
        """Verify negative test generation for incorrect payload length mapping to NRC 0x13."""
        tc = test_generator.generate_negative_test(
            service_id=0x22,
            defect_type="INCORRECT_LENGTH",
            project_id="test_proj_01"
        )
        assert tc.test_type == "NEGATIVE_INCORRECT_LENGTH"
        assert tc.steps[0].expected_response_type == "NEGATIVE"
        assert tc.steps[0].expected_nrc == "0x13"
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_negative_session_violation(self):
        """Verify negative test generation for prohibited session violation."""
        tc = test_generator.generate_negative_test(
            service_id=0x28,
            defect_type="SESSION_VIOLATION",
            project_id="test_proj_01"
        )
        assert tc.test_type == "NEGATIVE_SESSION_VIOLATION"
        assert tc.steps[0].expected_response_type == "NEGATIVE"
        assert tc.steps[0].expected_nrc in ("0x7F", "0x22")
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_negative_security_locked(self):
        """Verify negative test generation for security lockout mapping to NRC 0x33."""
        tc = test_generator.generate_negative_test(
            service_id=0x2E,
            defect_type="SECURITY_LOCKED",
            project_id="test_proj_01"
        )
        assert tc.test_type == "NEGATIVE_SECURITY_LOCKED"
        assert tc.steps[0].expected_response_type == "NEGATIVE"
        assert tc.steps[0].expected_nrc == "0x33"
        assert tc.rule_verification_status == "PASSED"
        assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_suite_for_service_0x10(self):
        """Verify full suite generation for 0x10: positive, incorrect length, invalid subfunction."""
        suite = test_generator.generate_suite_for_service(
            service_id=0x10,
            project_id="test_proj_01"
        )
        assert len(suite) >= 3  # POSITIVE, INCORRECT_LENGTH, INVALID_SUBFUNCTION
        types = [tc.test_type for tc in suite]
        assert "POSITIVE" in types
        assert "NEGATIVE_INCORRECT_LENGTH" in types
        assert "NEGATIVE_INVALID_SUBFUNCTION" in types
        for tc in suite:
            assert tc.rule_verification_status == "PASSED"
            assert tc.rule_verification_report.overall_verdict == "PASS"

    def test_generate_suite_for_service_0x2e(self):
        """Verify full suite generation for 0x2E: positive, incorrect length, security locked."""
        suite = test_generator.generate_suite_for_service(
            service_id=0x2E,
            project_id="test_proj_01"
        )
        assert len(suite) >= 3  # POSITIVE, INCORRECT_LENGTH, SECURITY_LOCKED
        types = [tc.test_type for tc in suite]
        assert "POSITIVE" in types
        assert "NEGATIVE_INCORRECT_LENGTH" in types
        assert "NEGATIVE_SECURITY_LOCKED" in types
        for tc in suite:
            assert tc.rule_verification_status == "PASSED"

    def test_citation_references_preserved(self):
        """Verify that specification chunk citations are preserved on generated test cases."""
        sample_citations = ["chunk_uds_spec_sec3_p12", "chunk_oem_bcm_table4_p8"]
        tc = test_generator.generate_positive_test(
            service_id=0x3E,
            project_id="test_proj_01",
            citations=sample_citations
        )
        assert tc.citation_references == sample_citations

    def test_unsupported_service_id_error(self):
        """Verify that attempting to generate a test case for an unregistered SID raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            test_generator.generate_positive_test(service_id=0x99)
        assert "0x99" in str(excinfo.value)

    def test_build_prompt_role_and_governance_rules(self):
        """Verify prompt assembly defines engineer role and mandatory governance rules."""
        prompt = build_test_generation_prompt(service_id=0x10, test_scenario="POSITIVE")
        assert isinstance(prompt, AssembledPrompt)
        assert "Automotive Diagnostic Validation Specialist" in prompt.system_prompt
        assert "ISO 14229-1 (UDS) Test Engineer at Tata Technologies" in prompt.system_prompt
        assert "UDSRuleEngine" in prompt.system_prompt
        assert "MANDATORY GOVERNANCE & PROTOCOL RULES" in prompt.system_prompt

    def test_build_prompt_schema_enforcement(self):
        """Verify prompt assembly embeds strict Pydantic TestCase JSON Schema contract."""
        prompt = build_test_generation_prompt(service_id=0x22, test_scenario="POSITIVE")
        assert prompt.target_schema_json["title"] == "TestCase"
        props = prompt.target_schema_json["properties"]
        assert "test_case_id" in props
        assert "steps" in props
        assert "preconditions" in props
        assert "pass_fail_criteria" in props
        assert "TARGET JSON SCHEMA (Pydantic TestCase):" in prompt.system_prompt

    def test_build_prompt_scenario_and_context_injection(self):
        """Verify prompt assembly injects requested scenario, preconditions, and citations."""
        sample_context = "Service 0x2E WriteDataByIdentifier requires Extended Session (0x03) and Security Level 1."
        prompt = test_generator.build_test_generation_prompt(
            service_id=0x2E,
            test_scenario="NEGATIVE_LENGTH",
            context_text=sample_context,
            session="EXTENDED",
            security_level=1,
            target_did="2001"
        )
        assert "Target Service: 0x2E (WriteDataByIdentifier)" in prompt.user_prompt
        assert "Test Scenario: NEGATIVE_LENGTH" in prompt.user_prompt
        assert "Active Diagnostic Session Precondition: EXTENDED" in prompt.user_prompt
        assert "Active Security Level Precondition: Level 1 (Unlocked)" in prompt.user_prompt
        assert "Target Identifier / DID: 2001" in prompt.user_prompt
        assert sample_context in prompt.user_prompt

    def test_build_prompt_unsupported_service_error(self):
        """Verify prompt assembly raises ValueError for unregistered service IDs."""
        with pytest.raises(ValueError) as excinfo:
            build_test_generation_prompt(service_id=0x99)
        assert "0x99" in str(excinfo.value)

