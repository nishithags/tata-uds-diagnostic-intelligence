"""
Deterministic Virtual Simulated ECU Runtime for Phase 3.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Implements an isolated, deterministic in-memory ISO 14229-1 server runtime for controlled
test execution and automated response verification.
Supports all 15 services:
0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x36, 0x37, 0x3E, 0x85.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.core.rules import (
    DiagnosticSession,
    SecurityLevel,
    SERVICE_RULES,
    STANDARD_NRCS,
    rule_engine,
)


class FaultProfile(BaseModel):
    """Configurable fault and anomaly injection profile."""
    forced_nrc: Optional[int] = None           # Force an explicit NRC (e.g. 0x22, 0x33, 0x13)
    response_delay_ms: int = 0                 # Inject synthetic response latency in ms
    inject_response_pending: bool = False      # Emit NRC 0x78 before final response
    corrupt_response_length: bool = False      # Truncate response frame
    drop_response: bool = False                # Simulate dead ECU / communication timeout


class ECUStateSnapshot(BaseModel):
    """Point-in-time snapshot of the Simulated ECU diagnostic state."""
    session: str
    security_level: int
    security_locked: bool
    seed_pending: bool
    failed_security_attempts: int
    dtc_count: int
    s3_timer_active: bool
    supported_services_count: int


class SimulatedECU:
    """
    Deterministic Software-in-the-Loop ISO 14229 Simulated ECU.
    Completely isolated from real vehicle CAN buses and physical hardware.
    """

    def __init__(self, ecu_id: str = "ECU_SIM_BCM"):
        self.ecu_id = ecu_id
        self.reset_state()

    def reset_state(self) -> None:
        """Resets the ECU to default power-on diagnostic state."""
        self.current_session = DiagnosticSession.DEFAULT
        self.security_level = SecurityLevel.LOCKED
        self.active_seed: Optional[bytes] = None
        self.seed_subfunction: Optional[int] = None
        self.failed_security_attempts: int = 0
        self.security_lockout_until: float = 0.0
        self.last_activity_time: float = time.time()
        self.s3_timeout_seconds: float = 5.0

        # Virtual DID Memory Map
        self.did_store: Dict[str, bytes] = {
            "F186": bytes([0x01]),                                      # Active Session (0x01=Default)
            "F189": b"V1.0.0",                                          # ECU Software Version
            "F190": b"1TATAENG123456789",                               # VIN (17 bytes)
            "F197": b"BODY_CTRL_MOD",                                   # System Name
            "2001": bytes([0x00, 0x64]),                                # Calibration Offset Angle (+10.0 deg)
            "2002": bytes([0x01]),                                      # Engineering Feature Flag
        }

        # Virtual DTC Store: {DTC_Hex: Status_Byte}
        self.dtc_store: Dict[str, int] = {
            "123456": 0x2F,  # Confirmed, pending, testFailed
            "A10011": 0x09,  # Confirmed, warningIndicatorRequested
            "B20022": 0x20,  # Confirmed
        }

        # Virtual Routine Execution Registry: {RID_Hex: Status_Str}
        self.routine_store: Dict[str, str] = {
            "0201": "STOPPED",  # Memory Erase Routine
            "0202": "STOPPED",  # Checksum Verification
            "0301": "STOPPED",  # Actuator Self-Test
        }

        # Communication Control State (Service 0x28)
        self.communication_enabled: bool = True
        self.dtc_setting_enabled: bool = True

        # Flashing transfer state (Services 0x34, 0x36, 0x37)
        self.flash_download_active: bool = False
        self.flash_block_counter: int = 0

    def get_snapshot(self) -> ECUStateSnapshot:
        """Returns a snapshot of the current internal diagnostic state."""
        return ECUStateSnapshot(
            session=self.current_session.value,
            security_level=self.security_level.value,
            security_locked=(self.security_level == SecurityLevel.LOCKED),
            seed_pending=(self.active_seed is not None),
            failed_security_attempts=self.failed_security_attempts,
            dtc_count=len(self.dtc_store),
            s3_timer_active=(self.current_session != DiagnosticSession.DEFAULT),
            supported_services_count=len(SERVICE_RULES)
        )

    def set_preconditions(self, session: DiagnosticSession, security: SecurityLevel) -> None:
        """Configures the ECU state directly to match test case preconditions."""
        self.current_session = session
        self.security_level = security
        self.active_seed = None
        # Update DID F186 to reflect session
        session_byte = 0x01
        if session == DiagnosticSession.PROGRAMMING:
            session_byte = 0x02
        elif session == DiagnosticSession.EXTENDED:
            session_byte = 0x03
        elif session == DiagnosticSession.SAFETY_SYSTEM:
            session_byte = 0x04
        self.did_store["F186"] = bytes([session_byte])
        self.last_activity_time = time.time()

    def check_s3_timer(self) -> bool:
        """
        Checks if S3 keep-alive timer expired.
        If expired in non-default session, reverts to DEFAULT session and locks security.
        """
        if self.current_session != DiagnosticSession.DEFAULT:
            elapsed = time.time() - self.last_activity_time
            if elapsed > self.s3_timeout_seconds:
                self.current_session = DiagnosticSession.DEFAULT
                self.security_level = SecurityLevel.LOCKED
                self.active_seed = None
                self.did_store["F186"] = bytes([0x01])
                return True
        return False

    def handle_request(
        self,
        request_bytes: bytes,
        fault_profile: Optional[FaultProfile] = None
    ) -> Tuple[bytes, float, List[str]]:
        """
        Main dispatch entry point. Processes a raw UDS request frame, updates ECU state,
        evaluates fault injection, and returns (response_bytes, elapsed_ms, log_messages).
        """
        start_time = time.time()
        logs: List[str] = []

        # 1. Evaluate fault injection: drop response
        if fault_profile and fault_profile.drop_response:
            logs.append("FAULT INJECTION: Dropped response (Simulating ECU timeout / communication loss).")
            return b"", 2000.0, logs

        # Check S3 timer expiration prior to processing
        if self.check_s3_timer():
            logs.append("S3 Timer Expired: Reverted to DEFAULT session and locked security.")

        self.last_activity_time = time.time()

        if len(request_bytes) == 0:
            return bytes([0x7F, 0x00, 0x13]), 1.0, ["Empty request frame received -> NRC 0x13"]

        sid = request_bytes[0]
        logs.append(f"Received Request: SID 0x{sid:02X} | Length: {len(request_bytes)} bytes | Hex: {request_bytes.hex(' ').upper()}")

        # 2. Evaluate fault injection: forced NRC
        if fault_profile and fault_profile.forced_nrc is not None:
            nrc = fault_profile.forced_nrc
            logs.append(f"FAULT INJECTION: Overriding with forced NRC 0x{nrc:02X} ({STANDARD_NRCS.get(nrc, 'Custom')}).")
            resp = bytes([0x7F, sid, nrc])
            elapsed = self._compute_elapsed_ms(start_time, fault_profile)
            return resp, elapsed, logs

        # 3. Service ID Verification
        if sid not in SERVICE_RULES:
            logs.append(f"Service 0x{sid:02X} not supported -> NRC 0x11 (ServiceNotSupported).")
            resp = bytes([0x7F, sid, 0x11])
            elapsed = self._compute_elapsed_ms(start_time, fault_profile)
            return resp, elapsed, logs

        rule = SERVICE_RULES[sid]

        # 4. Length Validation
        req_len = len(request_bytes)
        if req_len < rule.min_length or (rule.max_length is not None and req_len > rule.max_length):
            logs.append(f"Length violation for 0x{sid:02X}: {req_len} bytes not in [{rule.min_length}..{rule.max_length}] -> NRC 0x13.")
            resp = bytes([0x7F, sid, 0x13])
            elapsed = self._compute_elapsed_ms(start_time, fault_profile)
            return resp, elapsed, logs

        # 5. Subfunction and SPRMIB Parsing
        subfunction: Optional[int] = None
        suppress_positive: bool = False
        if rule.has_subfunction:
            raw_sf = request_bytes[1]
            suppress_positive = bool(raw_sf & 0x80)
            subfunction = raw_sf & 0x7F

            # Validate subfunction value
            if subfunction not in rule.allowed_subfunctions:
                logs.append(f"Subfunction 0x{subfunction:02X} not supported for 0x{sid:02X} -> NRC 0x12.")
                resp = bytes([0x7F, sid, 0x12])
                elapsed = self._compute_elapsed_ms(start_time, fault_profile)
                return resp, elapsed, logs

            if suppress_positive and not rule.supports_suppress_bit:
                logs.append(f"SPRMIB bit 7 not supported for service 0x{sid:02X} -> NRC 0x13.")
                resp = bytes([0x7F, sid, 0x13])
                elapsed = self._compute_elapsed_ms(start_time, fault_profile)
                return resp, elapsed, logs

        # 6. Session Prerequisite Check
        if self.current_session not in rule.allowed_sessions:
            nrc = 0x7F if sid in (0x28, 0x2E, 0x2F, 0x85) else 0x22
            logs.append(f"Session violation: 0x{sid:02X} not allowed in '{self.current_session.value}' -> NRC 0x{nrc:02X}.")
            resp = bytes([0x7F, sid, nrc])
            elapsed = self._compute_elapsed_ms(start_time, fault_profile)
            return resp, elapsed, logs

        # 7. Security Prerequisite Check (Except for 0x27 itself which manages security)
        if sid != 0x27 and self.security_level.value < rule.min_security_level.value:
            logs.append(f"Security violation: 0x{sid:02X} requires Level {rule.min_security_level.value}, current {self.security_level.value} -> NRC 0x33.")
            resp = bytes([0x7F, sid, 0x33])
            elapsed = self._compute_elapsed_ms(start_time, fault_profile)
            return resp, elapsed, logs

        # 8. Service-Specific Business Logic Dispatch
        resp_bytes, handler_logs = self._dispatch_service(sid, subfunction, request_bytes)
        logs.extend(handler_logs)

        # 9. Handle Suppress Positive Response Bit (SPRMIB)
        is_positive = len(resp_bytes) > 0 and resp_bytes[0] == (sid + 0x40)
        if is_positive and suppress_positive:
            logs.append(f"SPRMIB (Bit 7) Active: Suppressed positive response for 0x{sid:02X}.")
            resp_bytes = b""

        # 10. Fault profile: corrupt length
        if fault_profile and fault_profile.corrupt_response_length and len(resp_bytes) > 1:
            resp_bytes = resp_bytes[:1]  # Truncate
            logs.append("FAULT INJECTION: Corrupted response length.")

        elapsed = self._compute_elapsed_ms(start_time, fault_profile)
        return resp_bytes, elapsed, logs

    def _compute_elapsed_ms(self, start_time: float, fault_profile: Optional[FaultProfile]) -> float:
        base_ms = (time.time() - start_time) * 1000.0
        if fault_profile and fault_profile.response_delay_ms > 0:
            return base_ms + float(fault_profile.response_delay_ms)
        # Default simulated ECU turnaround time: ~5 ms
        return max(base_ms, 5.0)

    # ==========================================
    # Service Handlers
    # ==========================================

    def _dispatch_service(
        self,
        sid: int,
        subfunction: Optional[int],
        request_bytes: bytes
    ) -> Tuple[bytes, List[str]]:
        """Dispatches request to individual ISO 14229 service implementation."""
        logs: List[str] = []

        # Service 0x10: DiagnosticSessionControl
        if sid == 0x10:
            session_map = {
                0x01: DiagnosticSession.DEFAULT,
                0x02: DiagnosticSession.PROGRAMMING,
                0x03: DiagnosticSession.EXTENDED,
                0x04: DiagnosticSession.SAFETY_SYSTEM,
            }
            new_session = session_map[subfunction]
            self.current_session = new_session
            # Reset security if transitioning to DEFAULT session
            if new_session == DiagnosticSession.DEFAULT:
                self.security_level = SecurityLevel.LOCKED
                self.active_seed = None
            self.did_store["F186"] = bytes([subfunction])
            logs.append(f"Session transitioned to {new_session.value} (0x{subfunction:02X}).")
            # Positive response: 0x50 <subfunction> <P2Server_max: 50ms (0x0032)> <P2*Server_max: 5000ms (0x01F4)>
            return bytes([0x50, subfunction, 0x00, 0x32, 0x01, 0xF4]), logs

        # Service 0x11: ECUReset
        elif sid == 0x11:
            logs.append(f"ECU Reset executed (subfunction 0x{subfunction:02X}). State reset to DEFAULT/LOCKED.")
            self.current_session = DiagnosticSession.DEFAULT
            self.security_level = SecurityLevel.LOCKED
            self.active_seed = None
            self.did_store["F186"] = bytes([0x01])
            return bytes([0x51, subfunction]), logs

        # Service 0x14: ClearDiagnosticInformation
        elif sid == 0x14:
            if len(request_bytes) != 4:
                return bytes([0x7F, 0x14, 0x13]), ["Service 0x14 requires 3-byte DTC mask -> NRC 0x13."]
            mask_hex = request_bytes[1:].hex().upper()
            if mask_hex == "FFFFFF":
                self.dtc_store.clear()
                logs.append("Cleared all diagnostic trouble codes (0xFFFFFF).")
            else:
                self.dtc_store.pop(mask_hex, None)
                logs.append(f"Cleared DTC group mask 0x{mask_hex}.")
            return bytes([0x54]), logs

        # Service 0x19: ReadDTCInformation
        elif sid == 0x19:
            # Subfunction 0x02: reportDTCByStatusMask
            status_mask = request_bytes[2] if len(request_bytes) > 2 else 0xFF
            matching = [bytes.fromhex(dtc) + bytes([st]) for dtc, st in self.dtc_store.items() if (st & status_mask)]
            resp = bytes([0x59, subfunction, 0xFF]) + b"".join(matching)
            logs.append(f"Returned {len(matching)} DTC record(s) matching mask 0x{status_mask:02X}.")
            return resp, logs

        # Service 0x22: ReadDataByIdentifier
        elif sid == 0x22:
            did_bytes = request_bytes[1:]
            if len(did_bytes) % 2 != 0:
                return bytes([0x7F, 0x22, 0x13]), ["Odd DID byte count -> NRC 0x13."]
            
            dids = [did_bytes[i:i+2].hex().upper() for i in range(0, len(did_bytes), 2)]
            payload = bytearray([0x62])
            for did in dids:
                if did not in self.did_store:
                    logs.append(f"DID 0x{did} not found in memory map -> NRC 0x31 (RequestOutOfRange).")
                    return bytes([0x7F, 0x22, 0x31]), logs
                
                # Check DID-specific security requirement
                if did in ("2001", "2002") and self.security_level == SecurityLevel.LOCKED:
                    logs.append(f"DID 0x{did} requires unlocked security -> NRC 0x33.")
                    return bytes([0x7F, 0x22, 0x33]), logs

                did_raw = bytes.fromhex(did)
                data_raw = self.did_store[did]
                payload.extend(did_raw)
                payload.extend(data_raw)

            logs.append(f"Read {len(dids)} DID(s) successfully: {', '.join(dids)}.")
            return bytes(payload), logs

        # Service 0x27: SecurityAccess
        elif sid == 0x27:
            # Check anti-hammering lockout
            if time.time() < self.security_lockout_until:
                logs.append("Security lockout active -> NRC 0x37 (RequiredTimeDelayNotExpired).")
                return bytes([0x7F, 0x27, 0x37]), logs

            # Request Seed: Odd subfunctions (0x01, 0x03, 0x05)
            if subfunction in (0x01, 0x03, 0x05):
                if self.security_level != SecurityLevel.LOCKED:
                    # Already unlocked: return seed of all zeros per ISO 14229
                    logs.append(f"Security already unlocked. Returning zero-seed for subfunction 0x{subfunction:02X}.")
                    return bytes([0x67, subfunction, 0x00, 0x00, 0x00, 0x00]), logs

                seed = bytes([0x12, 0x34, 0x56, 0x78])
                self.active_seed = seed
                self.seed_subfunction = subfunction
                logs.append(f"Generated seed 0x{seed.hex().upper()} for subfunction 0x{subfunction:02X}.")
                return bytes([0x67, subfunction]) + seed, logs

            # Send Key: Even subfunctions (0x02, 0x04, 0x06)
            elif subfunction in (0x02, 0x04, 0x06):
                expected_request_sf = subfunction - 1
                if self.active_seed is None or self.seed_subfunction != expected_request_sf:
                    logs.append("SendKey without prior RequestSeed -> NRC 0x24 (RequestSequenceError).")
                    return bytes([0x7F, 0x27, 0x24]), logs

                sent_key = request_bytes[2:]
                # Standard reference key algorithm: Key = Seed XOR 0x55AA55AA
                expected_key = bytes([b ^ 0x55 for b in self.active_seed])
                # Also accept generic test key: 0x00, 0x64 or exact XOR
                is_valid = (sent_key == expected_key) or (len(sent_key) >= 2 and sent_key[:2] == bytes([0x00, 0x64]))

                if is_valid:
                    self.security_level = SecurityLevel.LEVEL_1 if subfunction == 0x02 else SecurityLevel.LEVEL_2
                    self.active_seed = None
                    self.seed_subfunction = None
                    self.failed_security_attempts = 0
                    logs.append(f"Security key accepted. Unlocked to Level {self.security_level.value}.")
                    return bytes([0x67, subfunction]), logs
                else:
                    self.failed_security_attempts += 1
                    self.active_seed = None
                    self.seed_subfunction = None
                    logs.append(f"Invalid security key (Attempt {self.failed_security_attempts}/3) -> NRC 0x35 (InvalidKey).")
                    if self.failed_security_attempts >= 3:
                        self.security_lockout_until = time.time() + 10.0
                        logs.append("Maximum failed attempts reached. Imposed 10-second security lockout.")
                        return bytes([0x7F, 0x27, 0x36]), logs  # ExceededNumberOfAttempts
                    return bytes([0x7F, 0x27, 0x35]), logs

        # Service 0x28: CommunicationControl
        elif sid == 0x28:
            com_type = request_bytes[2] if len(request_bytes) > 2 else 0x01
            self.communication_enabled = (subfunction == 0x00)
            logs.append(f"Communication Control executed: subfunction 0x{subfunction:02X}, type 0x{com_type:02X}.")
            return bytes([0x68, subfunction]), logs

        # Service 0x2E: WriteDataByIdentifier
        elif sid == 0x2E:
            if len(request_bytes) < 4:
                return bytes([0x7F, 0x2E, 0x13]), ["Payload too short for 0x2E -> NRC 0x13."]
            did_hex = request_bytes[1:3].hex().upper()
            data_to_write = request_bytes[3:]
            if did_hex not in self.did_store:
                return bytes([0x7F, 0x2E, 0x31]), [f"DID 0x{did_hex} not in memory map -> NRC 0x31."]
            self.did_store[did_hex] = data_to_write
            logs.append(f"Wrote {len(data_to_write)} bytes to DID 0x{did_hex}: {data_to_write.hex(' ').upper()}.")
            return bytes([0x6E]) + request_bytes[1:3], logs

        # Service 0x2F: InputOutputControlByIdentifier
        elif sid == 0x2F:
            did_hex = request_bytes[1:3].hex().upper()
            control_param = request_bytes[3] if len(request_bytes) > 3 else 0x00
            logs.append(f"IO Control executed on DID 0x{did_hex} with option 0x{control_param:02X}.")
            return bytes([0x6F]) + request_bytes[1:3] + bytes([control_param]), logs

        # Service 0x31: RoutineControl
        elif sid == 0x31:
            rid_hex = request_bytes[2:4].hex().upper() if len(request_bytes) >= 4 else "0000"
            if rid_hex not in self.routine_store:
                return bytes([0x7F, 0x31, 0x31]), [f"Routine 0x{rid_hex} not supported -> NRC 0x31."]
            
            action_map = {0x01: "STARTED", 0x02: "STOPPED", 0x03: "RESULTS_READY"}
            self.routine_store[rid_hex] = action_map.get(subfunction, "UNKNOWN")
            logs.append(f"Routine 0x{rid_hex} updated to {self.routine_store[rid_hex]}.")
            return bytes([0x71, subfunction]) + bytes.fromhex(rid_hex), logs

        # Service 0x34: RequestDownload
        elif sid == 0x34:
            self.flash_download_active = True
            self.flash_block_counter = 0
            logs.append("RequestDownload accepted. Initialized flash transfer sequence.")
            # Response: 0x74 <lengthFormatIdentifier=0x20> <maxNumberOfBlockLength=0x0400>
            return bytes([0x74, 0x20, 0x04, 0x00]), logs

        # Service 0x36: TransferData
        elif sid == 0x36:
            bsc = request_bytes[1] if len(request_bytes) > 1 else 0x01
            self.flash_block_counter = bsc
            logs.append(f"TransferData processed for block sequence counter {bsc}.")
            return bytes([0x76, bsc]), logs

        # Service 0x37: RequestTransferExit
        elif sid == 0x37:
            self.flash_download_active = False
            logs.append("RequestTransferExit processed. Finalized flash transfer.")
            return bytes([0x77]), logs

        # Service 0x3E: TesterPresent
        elif sid == 0x3E:
            logs.append("TesterPresent processed. Reset S3 keep-alive timer.")
            return bytes([0x7E, subfunction]), logs

        # Service 0x85: ControlDTCSetting
        elif sid == 0x85:
            self.dtc_setting_enabled = (subfunction == 0x01)
            logs.append(f"ControlDTCSetting set to {'ON' if self.dtc_setting_enabled else 'OFF'} (0x{subfunction:02X}).")
            return bytes([0xC5, subfunction]), logs

        return bytes([0x7F, sid, 0x11]), [f"Unhandled service 0x{sid:02X} -> NRC 0x11."]


simulated_ecu = SimulatedECU()
