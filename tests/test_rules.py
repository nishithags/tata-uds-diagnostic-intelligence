"""
Unit and Integration Tests for Deterministic UDS Rule Engine (Phase 2).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Verifies strict mathematical ISO 14229-1 compliance across all 15 services:
0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x36, 0x37, 0x3E, 0x85.
"""

import pytest
from src.core.rules import (
    DiagnosticSession,
    SecurityLevel,
    SERVICE_RULES,
    rule_engine,
    STANDARD_NRCS,
    SUPPORTED_SPEC_DIDS,
)


class TestUDSRuleEngine:
    """Test suite verifying deterministic rule validation for all 15 ISO 14229 services."""

    def test_all_15_services_registered(self):
        """Ensure all 15 mandated ISO 14229 services are registered in the rule engine."""
        expected_sids = {
            0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E,
            0x2F, 0x31, 0x34, 0x36, 0x37, 0x3E, 0x85
        }
        assert set(SERVICE_RULES.keys()) == expected_sids
        assert len(SERVICE_RULES) == 15

    @pytest.mark.parametrize("sid,nominal_hex,session,security", [
        (0x10, "10 01", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x11, "11 01", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x14, "14 FF FF FF", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x19, "19 02 08", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x22, "22 F1 90", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x27, "27 01", DiagnosticSession.EXTENDED, SecurityLevel.LOCKED),
        (0x28, "28 00 01", DiagnosticSession.EXTENDED, SecurityLevel.LOCKED),
        (0x2E, "2E 20 01 00 64", DiagnosticSession.EXTENDED, SecurityLevel.LEVEL_1),
        (0x2F, "2F 20 01 03 01", DiagnosticSession.EXTENDED, SecurityLevel.LEVEL_1),
        (0x31, "31 01 02 01", DiagnosticSession.EXTENDED, SecurityLevel.LEVEL_1),
        (0x34, "34 00 44 00 01 00 00 00 00 10 00", DiagnosticSession.PROGRAMMING, SecurityLevel.LEVEL_1),
        (0x36, "36 01 AA BB CC DD", DiagnosticSession.PROGRAMMING, SecurityLevel.LEVEL_1),
        (0x37, "37", DiagnosticSession.PROGRAMMING, SecurityLevel.LEVEL_1),
        (0x3E, "3E 00", DiagnosticSession.DEFAULT, SecurityLevel.LOCKED),
        (0x85, "85 01", DiagnosticSession.EXTENDED, SecurityLevel.LOCKED),
    ])
    def test_nominal_positive_request_passes_all_checks(self, sid, nominal_hex, session, security):
        """Verifies that each of the 15 services with nominal compliant frame passes all rule checks."""
        report = rule_engine.validate_request(
            request_hex=nominal_hex,
            current_session=session,
            current_security=security,
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "PASS", f"Service 0x{sid:02X} failed: {report.errors}"
        assert report.service_id == sid
        assert len(report.errors) == 0

    def test_subfunction_sprmib_bit_extraction(self):
        """Verifies parsing of subfunction and SPRMIB (bit 7) flag."""
        # 0x10 with subfunction 0x81 (bit 7 set = Suppress Positive Response)
        raw_bytes, sid, subfunc, suppressed = rule_engine.parse_request("10 81")
        assert sid == 0x10
        assert subfunc == 0x01
        assert suppressed is True

        # 0x10 with subfunction 0x01 (bit 7 cleared = Standard Positive Response)
        raw_bytes, sid, subfunc, suppressed = rule_engine.parse_request("10 01")
        assert sid == 0x10
        assert subfunc == 0x01
        assert suppressed is False

        # Validate request with SPRMIB passes
        report = rule_engine.validate_request("10 81", current_session=DiagnosticSession.DEFAULT)
        assert report.overall_verdict == "PASS"

    def test_invalid_subfunction_rejection(self):
        """Verifies that an unsupported subfunction fails validation and maps to NRC 0x12."""
        # 0x10 DiagnosticSessionControl does not support subfunction 0x7A
        report = rule_engine.validate_request(
            request_hex="10 7A",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "FAIL"
        assert any("0x7A" in err or "Subfunction" in err for err in report.errors)

        # Complementary negative validation: expecting NRC 0x12 yields PASS
        neg_report = rule_engine.validate_request(
            request_hex="10 7A",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="NEGATIVE",
            expected_nrc="0x12"
        )
        assert neg_report.overall_verdict == "PASS"

    def test_incorrect_message_length_rejection(self):
        """Verifies that truncated or oversized requests fail length checks and map to NRC 0x13."""
        # 0x10 requires at least 2 bytes (SID + Subfunction); sending only "10" is invalid
        report = rule_engine.validate_request(
            request_hex="10",
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "FAIL"
        assert any("length" in err.lower() for err in report.errors)

        # Negative test expecting NRC 0x13 succeeds
        neg_report = rule_engine.validate_request(
            request_hex="10",
            expected_response_type="NEGATIVE",
            expected_nrc="0x13"
        )
        assert neg_report.overall_verdict == "PASS"

    def test_session_prerequisite_enforcement(self):
        """Verifies session gating: e.g. 0x28 CommunicationControl is prohibited in DEFAULT session."""
        # 0x28 in DEFAULT session should fail positive test
        report = rule_engine.validate_request(
            request_hex="28 00 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "FAIL"
        assert any("session" in err.lower() for err in report.errors)

        # 0x28 in EXTENDED session succeeds
        report_ext = rule_engine.validate_request(
            request_hex="28 00 01",
            current_session=DiagnosticSession.EXTENDED,
            expected_response_type="POSITIVE"
        )
        assert report_ext.overall_verdict == "PASS"

    def test_security_level_gating(self):
        """Verifies security gating: 0x2E WriteDataByIdentifier requires Security Level >= 1."""
        # 0x2E when LOCKED should fail positive test
        report_locked = rule_engine.validate_request(
            request_hex="2E 20 01 00 64",
            current_session=DiagnosticSession.EXTENDED,
            current_security=SecurityLevel.LOCKED,
            expected_response_type="POSITIVE"
        )
        assert report_locked.overall_verdict == "FAIL"
        assert any("security" in err.lower() for err in report_locked.errors)

        # 0x2E when UNLOCKED (Level 1) succeeds
        report_unlocked = rule_engine.validate_request(
            request_hex="2E 20 01 00 64",
            current_session=DiagnosticSession.EXTENDED,
            current_security=SecurityLevel.LEVEL_1,
            expected_response_type="POSITIVE"
        )
        assert report_unlocked.overall_verdict == "PASS"

    def test_service_not_supported_nrc11(self):
        """Verifies that an unregistered SID fails with ServiceNotSupported (NRC 0x11)."""
        report = rule_engine.validate_request(
            request_hex="99 01 02",
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "FAIL"
        assert any("0x99" in err for err in report.errors)

        # In negative test, expecting NRC 0x11 yields PASS
        neg_report = rule_engine.validate_request(
            request_hex="99 01 02",
            expected_response_type="NEGATIVE",
            expected_nrc="0x11"
        )
        assert neg_report.overall_verdict == "PASS"

    def test_did_alignment_rule_service_0x22(self):
        """Verifies that Service 0x22 enforces 2-byte alignment for DIDs."""
        # 3 bytes total: SID (1) + 2 bytes DID -> Valid
        rep_valid = rule_engine.validate_request("22 F1 90")
        assert rep_valid.overall_verdict == "PASS"

        # 2 bytes total: SID (1) + 1 byte DID -> Odd remainder, Invalid
        rep_invalid = rule_engine.validate_request("22 F1", expected_response_type="POSITIVE")
        assert rep_invalid.overall_verdict == "FAIL"
        assert any("multiple of 2" in err for err in rep_invalid.errors)

    def test_dtc_group_mask_rule_service_0x14(self):
        """Verifies that Service 0x14 ClearDiagnosticInformation requires exactly 3 DTC group mask bytes."""
        # 14 + 3 bytes = 4 bytes total -> Valid
        rep_valid = rule_engine.validate_request("14 FF FF FF")
        assert rep_valid.overall_verdict == "PASS"

        # 14 + 2 bytes = 3 bytes total -> Invalid
        rep_invalid = rule_engine.validate_request("14 FF FF", expected_response_type="POSITIVE")
        assert rep_invalid.overall_verdict == "FAIL"
        assert any("3-byte" in err for err in rep_invalid.errors)

    def test_unsupported_did_0201_rejected_for_positive_read_data_by_id(self):
        """Verifies that Routine ID 0x0201 cannot pass as a positive ReadDataByIdentifier DID."""
        report = rule_engine.validate_request(
            request_hex="22 02 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="POSITIVE"
        )
        assert report.overall_verdict == "FAIL"
        did_checks = [c for c in report.checks if c.rule_code == "RULE_DID_SUPPORT"]
        assert len(did_checks) == 1
        assert did_checks[0].passed is False
        assert "0x0201 is not supported" in did_checks[0].message
        assert "Routine Identifier" in did_checks[0].message
        assert any("0x0201" in err for err in report.errors)

    def test_unsupported_did_permitted_for_targeted_negative_nrc31(self):
        """Verifies that unsupported DIDs are permitted ONLY for intentional negative NRC 0x31 tests."""
        # 0x0201 targeting NRC 0x31 -> Valid negative scenario
        report_neg_31 = rule_engine.validate_request(
            request_hex="22 02 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="NEGATIVE",
            expected_nrc="0x31"
        )
        assert report_neg_31.overall_verdict == "PASS"
        assert len(report_neg_31.errors) == 0
        assert any("RULE_DID_SUPPORT" == c.rule_code and c.passed for c in report_neg_31.checks)

        # 0xFFFF targeting NRC 0x31 -> Valid negative scenario
        report_ffff = rule_engine.validate_request(
            request_hex="22 FF FF",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="NEGATIVE",
            expected_nrc="0x31"
        )
        assert report_ffff.overall_verdict == "PASS"

        # 0x0201 targeting wrong NRC (0x12) -> Invalid, must fail
        report_neg_wrong_nrc = rule_engine.validate_request(
            request_hex="22 02 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="NEGATIVE",
            expected_nrc="0x12"
        )
        assert report_neg_wrong_nrc.overall_verdict == "FAIL"
        assert any("0x0201" in err for err in report_neg_wrong_nrc.errors)

    def test_authoritative_dids_pass_positive_validation(self):
        """Verifies that all authoritative specification DIDs pass positive validation in DEFAULT session."""
        for did_hex in ("F186", "F189", "F190"):
            report = rule_engine.validate_request(
                request_hex=f"22 {did_hex}",
                current_session=DiagnosticSession.DEFAULT,
                expected_response_type="POSITIVE"
            )
            assert report.overall_verdict == "PASS", f"DID 0x{did_hex} unexpectedly failed: {report.errors}"
            assert len(report.errors) == 0

        # Multi-DID request: F186 and F190 combined
        report_multi = rule_engine.validate_request(
            request_hex="22 F1 86 F1 90",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="POSITIVE"
        )
        assert report_multi.overall_verdict == "PASS"

    def test_did_2001_session_prerequisite_enforcement(self):
        """Verifies that DID 0x2001 strictly enforces EXTENDED diagnostic session prerequisite."""
        # DID 0x2001 in DEFAULT session for positive test -> Must fail session prerequisite
        report_default = rule_engine.validate_request(
            request_hex="22 20 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="POSITIVE"
        )
        assert report_default.overall_verdict == "FAIL"
        assert any("RULE_DID_SESSION_PREREQUISITE" == c.rule_code and not c.passed for c in report_default.checks)
        assert any("EXTENDED" in err for err in report_default.errors)

        # DID 0x2001 in EXTENDED session for positive test -> Must PASS
        report_extended = rule_engine.validate_request(
            request_hex="22 20 01",
            current_session=DiagnosticSession.EXTENDED,
            expected_response_type="POSITIVE"
        )
        assert report_extended.overall_verdict == "PASS"

        # DID 0x2001 in DEFAULT session targeting negative NRC 0x22 (ConditionsNotCorrect) -> Valid negative scenario
        report_neg_22 = rule_engine.validate_request(
            request_hex="22 20 01",
            current_session=DiagnosticSession.DEFAULT,
            expected_response_type="NEGATIVE",
            expected_nrc="0x22"
        )
        assert report_neg_22.overall_verdict == "PASS"

    def test_unsupported_dids_f197_and_2002_rejected_from_spec(self):
        """Demonstrates strict reconciliation: DIDs F197 and 2002 not in spec must be rejected for positive tests."""
        assert 0xF197 not in SUPPORTED_SPEC_DIDS
        assert 0x2002 not in SUPPORTED_SPEC_DIDS

        for unspec_did in ("F197", "2002"):
            report = rule_engine.validate_request(
                request_hex=f"22 {unspec_did}",
                current_session=DiagnosticSession.DEFAULT,
                expected_response_type="POSITIVE"
            )
            assert report.overall_verdict == "FAIL"
            assert any(f"0x{unspec_did}" in err for err in report.errors)

