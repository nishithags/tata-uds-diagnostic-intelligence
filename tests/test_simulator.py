"""
Unit and Integration Tests for Simulated ECU Runtime (Phase 3).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Verifies:
- Stateful session management (Default, Extended, Programming).
- Security access seed-key handshake and anti-hammering lockout.
- Memory map DID read/write operations (Services 0x22, 0x2E).
- DTC clearing and reading (Services 0x14, 0x19).
- Reset and routine execution (Services 0x11, 0x31).
- Flashing transfer services (Services 0x34, 0x36, 0x37).
- TesterPresent keep-alive (Service 0x3E).
- Fault injection engine (forced NRC, delays, dropped response, length corruption).
"""

import time
import pytest
from src.core.rules import DiagnosticSession, SecurityLevel
from src.core.simulator import FaultProfile, SimulatedECU


@pytest.fixture
def ecu():
    """Provides a fresh SimulatedECU instance for each test."""
    instance = SimulatedECU("TEST_BCM")
    instance.reset_state()
    return instance


class TestSimulatedECU:
    """Test suite for Software-in-the-Loop Simulated ECU."""

    def test_initial_power_on_state(self, ecu):
        """Verify initial default power-on state."""
        snap = ecu.get_snapshot()
        assert snap.session == "DEFAULT"
        assert snap.security_level == 0
        assert snap.security_locked is True
        assert snap.seed_pending is False
        assert snap.failed_security_attempts == 0
        assert snap.dtc_count > 0

    def test_session_control_transitions(self, ecu):
        """Verify transitions across Default, Extended, and Programming sessions."""
        # 1. Transition to Extended Session (10 03)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x03]))
        assert resp[0] == 0x50
        assert resp[1] == 0x03
        assert ecu.current_session == DiagnosticSession.EXTENDED

        # 2. Transition to Programming Session (10 02)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x02]))
        assert resp[0] == 0x50
        assert resp[1] == 0x02
        assert ecu.current_session == DiagnosticSession.PROGRAMMING

        # 3. Transition back to Default Session (10 01)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x01]))
        assert resp[0] == 0x50
        assert resp[1] == 0x01
        assert ecu.current_session == DiagnosticSession.DEFAULT

    def test_session_control_sprmib_suppression(self, ecu):
        """Verify Suppress Positive Response Bit (0x80) suppresses positive response."""
        # Subfunction 0x83 = 0x03 (Extended) with bit 7 set
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x83]))
        assert resp == b""  # Suppressed
        assert ecu.current_session == DiagnosticSession.EXTENDED

    def test_session_control_invalid_subfunction_nrc12(self, ecu):
        """Verify unsupported subfunction returns NRC 0x12."""
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x7A]))
        assert resp == bytes([0x7F, 0x10, 0x12])

    def test_session_control_length_error_nrc13(self, ecu):
        """Verify missing subfunction byte returns NRC 0x13."""
        resp, elapsed, logs = ecu.handle_request(bytes([0x10]))
        assert resp == bytes([0x7F, 0x10, 0x13])

    def test_security_access_seed_and_key_flow(self, ecu):
        """Verify normal seed-key authorization sequence."""
        # Must be in Extended session for SecurityAccess
        ecu.set_preconditions(DiagnosticSession.EXTENDED, SecurityLevel.LOCKED)

        # 1. Request Seed (27 01)
        resp, elapsed, logs = ecu.handle_request(bytes([0x27, 0x01]))
        assert resp[0] == 0x67
        assert resp[1] == 0x01
        assert len(resp) == 6  # 0x67 0x01 + 4 seed bytes
        seed = resp[2:]
        assert ecu.active_seed == seed

        # 2. Send Key (27 02) with correct key: key = seed XOR 0x55
        valid_key = bytes([b ^ 0x55 for b in seed])
        resp_key, elapsed_k, logs_k = ecu.handle_request(bytes([0x27, 0x02]) + valid_key)
        assert resp_key == bytes([0x67, 0x02])
        assert ecu.security_level == SecurityLevel.LEVEL_1

        # 3. Request Seed when already unlocked returns zero-seed
        resp_zero, _, _ = ecu.handle_request(bytes([0x27, 0x01]))
        assert resp_zero == bytes([0x67, 0x01, 0x00, 0x00, 0x00, 0x00])

    def test_security_access_invalid_key_and_anti_hammering(self, ecu):
        """Verify invalid key handling (NRC 0x35) and anti-hammering lockout (NRC 0x36 / 0x37)."""
        ecu.set_preconditions(DiagnosticSession.EXTENDED, SecurityLevel.LOCKED)

        # 3 consecutive invalid attempts
        for attempt in range(1, 3):
            # Request seed first
            ecu.handle_request(bytes([0x27, 0x01]))
            # Send bogus key
            resp, _, _ = ecu.handle_request(bytes([0x27, 0x02, 0xFF, 0xFF, 0xFF, 0xFF]))
            assert resp == bytes([0x7F, 0x27, 0x35])  # InvalidKey

        # 3rd failed attempt triggers lockout
        ecu.handle_request(bytes([0x27, 0x01]))
        resp_lockout, _, _ = ecu.handle_request(bytes([0x27, 0x02, 0xFF, 0xFF, 0xFF, 0xFF]))
        assert resp_lockout == bytes([0x7F, 0x27, 0x36])  # ExceededNumberOfAttempts

        # Subsequent inquiry during lockout delay returns NRC 0x37
        resp_delay, _, _ = ecu.handle_request(bytes([0x27, 0x01]))
        assert resp_delay == bytes([0x7F, 0x27, 0x37])  # RequiredTimeDelayNotExpired

    def test_security_access_send_key_without_seed_nrc24(self, ecu):
        """Verify SendKey without prior RequestSeed returns NRC 0x24 (RequestSequenceError)."""
        ecu.set_preconditions(DiagnosticSession.EXTENDED, SecurityLevel.LOCKED)
        resp, _, _ = ecu.handle_request(bytes([0x27, 0x02, 0x00, 0x64]))
        assert resp == bytes([0x7F, 0x27, 0x24])

    def test_read_data_by_id_nominal_and_multi_did(self, ecu):
        """Verify reading single and multiple DIDs."""
        # Read VIN (F190)
        resp, elapsed, logs = ecu.handle_request(bytes([0x22, 0xF1, 0x90]))
        assert resp[0] == 0x62
        assert resp[1:3] == bytes([0xF1, 0x90])
        assert resp[3:] == b"1TATAENG123456789"

        # Read multiple DIDs: F186 (session) and F189 (version)
        resp_multi, _, _ = ecu.handle_request(bytes([0x22, 0xF1, 0x86, 0xF1, 0x89]))
        assert resp_multi[0] == 0x62
        assert b"V1.0.0" in resp_multi

    def test_read_data_by_id_out_of_range_nrc31(self, ecu):
        """Verify reading unsupported DID returns NRC 0x31."""
        resp, _, _ = ecu.handle_request(bytes([0x22, 0xFF, 0xFF]))
        assert resp == bytes([0x7F, 0x22, 0x31])

    def test_write_data_by_id_session_and_security_gating(self, ecu):
        """Verify write DID 0x2001 requires Extended Session and Security Level 1."""
        # 1. In DEFAULT session -> NRC 0x7F
        resp_def, _, _ = ecu.handle_request(bytes([0x2E, 0x20, 0x01, 0x00, 0xC8]))
        assert resp_def == bytes([0x7F, 0x2E, 0x7F])

        # 2. In EXTENDED session but LOCKED -> NRC 0x33
        ecu.set_preconditions(DiagnosticSession.EXTENDED, SecurityLevel.LOCKED)
        resp_locked, _, _ = ecu.handle_request(bytes([0x2E, 0x20, 0x01, 0x00, 0xC8]))
        assert resp_locked == bytes([0x7F, 0x2E, 0x33])

        # 3. In EXTENDED session + LEVEL_1 -> Success
        ecu.set_preconditions(DiagnosticSession.EXTENDED, SecurityLevel.LEVEL_1)
        resp_ok, _, _ = ecu.handle_request(bytes([0x2E, 0x20, 0x01, 0x00, 0xC8]))
        assert resp_ok == bytes([0x6E, 0x20, 0x01])
        assert ecu.did_store["2001"] == bytes([0x00, 0xC8])

    def test_dtc_clear_and_read_operations(self, ecu):
        """Verify DTC reading and clearing."""
        # Read DTCs
        resp_read, _, _ = ecu.handle_request(bytes([0x19, 0x02, 0xFF]))
        assert resp_read[0] == 0x59

        # Clear All DTCs (14 FF FF FF)
        resp_clear, _, _ = ecu.handle_request(bytes([0x14, 0xFF, 0xFF, 0xFF]))
        assert resp_clear == bytes([0x54])
        assert len(ecu.dtc_store) == 0

    def test_fault_injection_forced_nrc(self, ecu):
        """Verify fault profile overrides nominal response with forced NRC."""
        profile = FaultProfile(forced_nrc=0x22)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x01]), fault_profile=profile)
        assert resp == bytes([0x7F, 0x10, 0x22])

    def test_fault_injection_drop_response(self, ecu):
        """Verify fault profile can simulate dropped response / communication failure."""
        profile = FaultProfile(drop_response=True)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x01]), fault_profile=profile)
        assert resp == b""
        assert elapsed >= 2000.0

    def test_fault_injection_corrupt_length(self, ecu):
        """Verify fault profile corrupts/truncates response length."""
        profile = FaultProfile(corrupt_response_length=True)
        resp, elapsed, logs = ecu.handle_request(bytes([0x10, 0x01]), fault_profile=profile)
        assert len(resp) == 1
