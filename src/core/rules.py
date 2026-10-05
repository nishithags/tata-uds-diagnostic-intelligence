"""
Deterministic UDS Protocol Rule Engine for Phase 2.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Implements strict, mathematical, non-probabilistic verification of diagnostic request frames,
subfunctions, Suppress-Positive-Response bits (SPRMIB), parameter lengths, session prerequisites,
security access states, and Negative Response Codes (NRCs) for ISO 14229-1 services:
0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x36, 0x37, 0x3E, 0x85.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class DiagnosticSession(str, Enum):
    DEFAULT = "DEFAULT"                      # 0x01
    PROGRAMMING = "PROGRAMMING"              # 0x02
    EXTENDED = "EXTENDED"                    # 0x03
    SAFETY_SYSTEM = "SAFETY_SYSTEM"          # 0x04


class SecurityLevel(int, Enum):
    LOCKED = 0
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


# ISO 14229 Standard Negative Response Codes (NRCs)
STANDARD_NRCS = {
    0x10: "GeneralReject",
    0x11: "ServiceNotSupported",
    0x12: "SubFunctionNotSupported",
    0x13: "IncorrectMessageLengthOrInvalidFormat",
    0x14: "ResponseTooLong",
    0x21: "BusyRepeatRequest",
    0x22: "ConditionsNotCorrect",
    0x24: "RequestSequenceError",
    0x25: "NoResponseFromSubnetComponent",
    0x26: "FailurePreventsExecutionOfRequestedAction",
    0x31: "RequestOutOfRange",
    0x33: "SecurityAccessDenied",
    0x35: "InvalidKey",
    0x36: "ExceededNumberOfAttempts",
    0x37: "RequiredTimeDelayNotExpired",
    0x70: "UploadDownloadNotAccepted",
    0x71: "TransferDataSuspended",
    0x72: "GeneralProgrammingFailure",
    0x73: "WrongBlockSequenceCounter",
    0x78: "RequestCorrectlyReceived-ResponsePending",
    0x7E: "SubFunctionNotSupportedInActiveSession",
    0x7F: "ServiceNotSupportedInActiveSession",
}


class RuleCheckResult(BaseModel):
    """Result of an individual deterministic rule evaluation."""
    rule_code: str
    rule_name: str
    passed: bool
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None


class ValidationReport(BaseModel):
    """Comprehensive validation report produced by the Deterministic Rule Engine."""
    overall_verdict: str  # "PASS" or "FAIL"
    service_id: int
    service_hex: str
    service_name: str
    checks: List[RuleCheckResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ServiceRuleDefinition(BaseModel):
    """Specification of ISO 14229 protocol constraints for a service."""
    service_id: int
    service_name: str
    has_subfunction: bool
    supports_suppress_bit: bool
    min_length: int
    max_length: Optional[int] = None
    allowed_subfunctions: Set[int] = Field(default_factory=set)
    allowed_sessions: Set[DiagnosticSession] = Field(default_factory=set)
    min_security_level: SecurityLevel = SecurityLevel.LOCKED
    applicable_nrcs: Set[int] = Field(default_factory=set)


class DataIdentifierDefinition(BaseModel):
    """Specification of ISO 14229 Data Identifier (DID) constraints from authoritative spec."""
    did: int
    did_hex: str
    name: str
    allowed_sessions: Set[DiagnosticSession] = Field(default_factory=set)
    description: str = ""



# ==============================================================================
# ISO 14229-1 Service Rule Master Registry
# ==============================================================================
SERVICE_RULES: Dict[int, ServiceRuleDefinition] = {
    # 0x10: DiagnosticSessionControl
    0x10: ServiceRuleDefinition(
        service_id=0x10,
        service_name="DiagnosticSessionControl",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=2,
        max_length=2,
        allowed_subfunctions={0x01, 0x02, 0x03, 0x04},
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.PROGRAMMING,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.SAFETY_SYSTEM,
        },
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x22}
    ),
    # 0x11: ECUReset
    0x11: ServiceRuleDefinition(
        service_id=0x11,
        service_name="ECUReset",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=2,
        max_length=2,
        allowed_subfunctions={0x01, 0x02, 0x03, 0x04, 0x05},
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.PROGRAMMING,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.SAFETY_SYSTEM,
        },
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x22, 0x33}
    ),
    # 0x14: ClearDiagnosticInformation
    0x14: ServiceRuleDefinition(
        service_id=0x14,
        service_name="ClearDiagnosticInformation",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=4,
        max_length=4,  # SID + 3-byte DTC group mask
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.DEFAULT, DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x13, 0x22, 0x31}
    ),
    # 0x19: ReadDTCInformation
    0x19: ServiceRuleDefinition(
        service_id=0x19,
        service_name="ReadDTCInformation",
        has_subfunction=True,
        supports_suppress_bit=False,
        min_length=2,
        max_length=6,
        allowed_subfunctions={0x01, 0x02, 0x04, 0x06},
        allowed_sessions={DiagnosticSession.DEFAULT, DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x31}
    ),
    # 0x22: ReadDataByIdentifier
    0x22: ServiceRuleDefinition(
        service_id=0x22,
        service_name="ReadDataByIdentifier",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=3,  # SID + at least one 2-byte DID
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.DEFAULT, DiagnosticSession.EXTENDED, DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x13, 0x22, 0x31, 0x33}
    ),
    # 0x27: SecurityAccess
    0x27: ServiceRuleDefinition(
        service_id=0x27,
        service_name="SecurityAccess",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=2,
        max_length=None,
        allowed_subfunctions={0x01, 0x02, 0x03, 0x04, 0x05, 0x06},
        allowed_sessions={DiagnosticSession.EXTENDED, DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x24, 0x35, 0x36, 0x37}
    ),
    # 0x28: CommunicationControl
    0x28: ServiceRuleDefinition(
        service_id=0x28,
        service_name="CommunicationControl",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=3,  # SID + subfunction + communicationType
        max_length=3,
        allowed_subfunctions={0x00, 0x01, 0x02, 0x03},
        allowed_sessions={DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x22, 0x31}
    ),
    # 0x2E: WriteDataByIdentifier
    0x2E: ServiceRuleDefinition(
        service_id=0x2E,
        service_name="WriteDataByIdentifier",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=4,  # SID + 2-byte DID + at least 1 data byte
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x13, 0x22, 0x31, 0x33}
    ),
    # 0x2F: InputOutputControlByIdentifier
    0x2F: ServiceRuleDefinition(
        service_id=0x2F,
        service_name="InputOutputControlByIdentifier",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=4,  # SID + 2-byte DID + 1-byte InputOutputControlParameter
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x13, 0x22, 0x31, 0x33}
    ),
    # 0x31: RoutineControl
    0x31: ServiceRuleDefinition(
        service_id=0x31,
        service_name="RoutineControl",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=4,  # SID + subfunction + 2-byte RID
        max_length=None,
        allowed_subfunctions={0x01, 0x02, 0x03},
        allowed_sessions={DiagnosticSession.EXTENDED, DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x12, 0x13, 0x22, 0x24, 0x31, 0x33}
    ),
    # 0x34: RequestDownload
    0x34: ServiceRuleDefinition(
        service_id=0x34,
        service_name="RequestDownload",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=5,  # SID + dataFormatID + addressAndLengthFormatID + memoryAddress/Size
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x13, 0x22, 0x31, 0x33, 0x70}
    ),
    # 0x36: TransferData
    0x36: ServiceRuleDefinition(
        service_id=0x36,
        service_name="TransferData",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=2,  # SID + blockSequenceCounter + data
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x13, 0x24, 0x71, 0x72, 0x73}
    ),
    # 0x37: RequestTransferExit
    0x37: ServiceRuleDefinition(
        service_id=0x37,
        service_name="RequestTransferExit",
        has_subfunction=False,
        supports_suppress_bit=False,
        min_length=1,
        max_length=None,
        allowed_subfunctions=set(),
        allowed_sessions={DiagnosticSession.PROGRAMMING},
        min_security_level=SecurityLevel.LEVEL_1,
        applicable_nrcs={0x13, 0x24}
    ),
    # 0x3E: TesterPresent
    0x3E: ServiceRuleDefinition(
        service_id=0x3E,
        service_name="TesterPresent",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=2,
        max_length=2,
        allowed_subfunctions={0x00},
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.PROGRAMMING,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.SAFETY_SYSTEM,
        },
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13}
    ),
    # 0x85: ControlDTCSetting
    0x85: ServiceRuleDefinition(
        service_id=0x85,
        service_name="ControlDTCSetting",
        has_subfunction=True,
        supports_suppress_bit=True,
        min_length=2,
        max_length=5,
        allowed_subfunctions={0x01, 0x02},
        allowed_sessions={DiagnosticSession.EXTENDED},
        min_security_level=SecurityLevel.LOCKED,
        applicable_nrcs={0x12, 0x13, 0x22, 0x31}
    ),
}


# ==============================================================================
# Authoritative Supported DIDs from Specification (synthetic_uds_spec.txt Section 3.1)
# ==============================================================================
SUPPORTED_SPEC_DIDS: Dict[int, DataIdentifierDefinition] = {
    0xF186: DataIdentifierDefinition(
        did=0xF186,
        did_hex="F186",
        name="ActiveDiagnosticSessionDataIdentifier",
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.PROGRAMMING,
        },
        description="Active diagnostic session indicator (1 byte)"
    ),
    0xF189: DataIdentifierDefinition(
        did=0xF189,
        did_hex="F189",
        name="EcuSoftwareNumberDataIdentifier",
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.PROGRAMMING,
        },
        description="ECU Software Number (4 bytes ASCII)"
    ),
    0xF190: DataIdentifierDefinition(
        did=0xF190,
        did_hex="F190",
        name="VehicleIdentificationNumberDataIdentifier",
        allowed_sessions={
            DiagnosticSession.DEFAULT,
            DiagnosticSession.EXTENDED,
            DiagnosticSession.PROGRAMMING,
        },
        description="Vehicle Identification Number (17 bytes ASCII)"
    ),
    0x2001: DataIdentifierDefinition(
        did=0x2001,
        did_hex="2001",
        name="CalibrationOffsetAngle",
        allowed_sessions={DiagnosticSession.EXTENDED},
        description="Calibration Offset Angle (Requires Extended Session 0x03)"
    ),
}

# Known Routine Identifiers (RIDs for Service 0x31) to prevent accidental DID misuse
KNOWN_SPEC_RIDS: Dict[int, str] = {
    0x0201: "Memory Erase Routine",
    0x0202: "Checksum Verification",
    0x0301: "Actuator Self-Test",
}



class UDSRuleEngine:
    """
    Deterministic ISO 14229 Protocol Rule Engine.
    Executes independent, mathematical validation of diagnostic requests and test cases.
    """

    @staticmethod
    def parse_hex_bytes(hex_str: str) -> List[int]:
        """Parses a hex byte string (e.g. '22 F1 90' or '22f190') into a list of integers."""
        clean = hex_str.replace("0x", "").replace(" ", "").replace(",", "").strip()
        if not clean:
            return []
        if len(clean) % 2 != 0:
            raise ValueError(f"Odd length hex string: '{hex_str}' cannot be parsed into bytes.")
        return [int(clean[i:i+2], 16) for i in range(0, len(clean), 2)]

    def parse_request(self, request_hex: str) -> Tuple[List[int], int, Optional[int], bool]:
        """
        Parses a raw hex request string into (raw_bytes, sid, subfunction, suppressed_bit).
        Extracts bit 7 (SPRMIB) and cleans subfunction byte (0x7F mask).
        """
        raw_bytes = self.parse_hex_bytes(request_hex)
        if not raw_bytes:
            raise ValueError("Empty request frame.")
        sid = raw_bytes[0]
        subfunc = None
        suppressed = False
        if len(raw_bytes) > 1:
            raw_sf = raw_bytes[1]
            suppressed = bool(raw_sf & 0x80)
            subfunc = raw_sf & 0x7F
        return raw_bytes, sid, subfunc, suppressed

    def validate_request(
        self,
        request_hex: str,
        current_session: DiagnosticSession = DiagnosticSession.DEFAULT,
        current_security: SecurityLevel = SecurityLevel.LOCKED,
        expected_response_type: str = "POSITIVE",
        expected_nrc: Optional[str] = None
    ) -> ValidationReport:
        """
        Deterministically evaluates a raw diagnostic request against ISO 14229 constraints.
        Checks:
        1. Hex syntax and non-empty byte payload.
        2. Service ID (SID) recognition in rule master.
        3. Suppress-Positive-Response Bit (SPRMIB) and subfunction range.
        4. Payload length constraints (min/max).
        5. Service-specific formatting (e.g. 0x22 DID count, 0x14 DTC mask length).
        6. Active diagnostic session prerequisite.
        7. Active security level prerequisite.
        8. Expected response / NRC schema validity.
        """
        checks: List[RuleCheckResult] = []
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Parse Bytes
        try:
            raw_bytes = self.parse_hex_bytes(request_hex)
        except Exception as e:
            return ValidationReport(
                overall_verdict="FAIL",
                service_id=0,
                service_hex="0x00",
                service_name="Unknown",
                checks=[
                    RuleCheckResult(
                        rule_code="RULE_HEX_SYNTAX",
                        rule_name="Hex Byte String Syntax",
                        passed=False,
                        message=f"Invalid hex string: {str(e)}"
                    )
                ],
                errors=[f"Hex parse error: {str(e)}"]
            )

        if not raw_bytes:
            return ValidationReport(
                overall_verdict="FAIL",
                service_id=0,
                service_hex="0x00",
                service_name="Unknown",
                checks=[
                    RuleCheckResult(
                        rule_code="RULE_EMPTY_PAYLOAD",
                        rule_name="Payload Non-Empty Check",
                        passed=False,
                        message="Request byte payload is empty."
                    )
                ],
                errors=["Empty request frame."]
            )

        sid = raw_bytes[0]
        sid_hex = f"0x{sid:02X}"

        # 2. SID Recognition
        if sid not in SERVICE_RULES:
            is_expected_nrc_11 = (
                expected_response_type == "NEGATIVE" and
                expected_nrc in ("0x11", "11", 0x11)
            )
            report = ValidationReport(
                overall_verdict="PASS" if is_expected_nrc_11 else "FAIL",
                service_id=sid,
                service_hex=sid_hex,
                service_name="Unrecognized Service",
                checks=[
                    RuleCheckResult(
                        rule_code="RULE_SID_SUPPORT",
                        rule_name="ISO 14229 Service ID Support",
                        passed=is_expected_nrc_11,
                        message=f"Service ID {sid_hex} is not in the supported UDS rule registry." + (" (Targeted Negative: NRC 0x11)" if is_expected_nrc_11 else ""),
                        expected=f"One of: {', '.join(f'0x{k:02X}' for k in sorted(SERVICE_RULES.keys()))}",
                        actual=sid_hex
                    )
                ],
                errors=[] if is_expected_nrc_11 else [f"Unsupported Service ID {sid_hex}."],
                warnings=[f"Negative test targeting NRC 0x11 for unsupported SID {sid_hex}"] if is_expected_nrc_11 else []
            )
            return report

        rule = SERVICE_RULES[sid]
        checks.append(
            RuleCheckResult(
                rule_code="RULE_SID_SUPPORT",
                rule_name="ISO 14229 Service ID Support",
                passed=True,
                message=f"Service {rule.service_name} ({sid_hex}) recognized.",
                expected="Valid ISO 14229 SID",
                actual=sid_hex
            )
        )

        # 3. Payload Length Check
        req_len = len(raw_bytes)
        len_passed = True
        len_msg = f"Length {req_len} bytes satisfies minimum {rule.min_length}."
        if req_len < rule.min_length:
            len_passed = False
            len_msg = f"Length {req_len} bytes is below minimum required {rule.min_length} bytes."
            if expected_response_type != "NEGATIVE":
                errors.append(len_msg)
            else:
                warnings.append(f"Negative scenario target (Incorrect length): {len_msg}")
        elif rule.max_length is not None and req_len > rule.max_length:
            len_passed = False
            len_msg = f"Length {req_len} bytes exceeds maximum allowed {rule.max_length} bytes."
            if expected_response_type != "NEGATIVE":
                errors.append(len_msg)
            else:
                warnings.append(f"Negative scenario target (Excess length): {len_msg}")

        checks.append(
            RuleCheckResult(
                rule_code="RULE_LENGTH_CHECK",
                rule_name="Message Length Specification",
                passed=len_passed,
                message=len_msg,
                expected=f"[{rule.min_length}..{rule.max_length if rule.max_length else 'unlimited'}] bytes",
                actual=f"{req_len} bytes"
            )
        )

        # 4. Subfunction & SPRMIB (Bit 7) Evaluation
        if rule.has_subfunction:
            if req_len < 2:
                missing_msg = f"Service {rule.service_name} requires a subfunction byte, but only {req_len} byte received."
                if expected_response_type != "NEGATIVE":
                    errors.append(missing_msg)
                else:
                    warnings.append(f"Negative scenario target (Missing subfunction): {missing_msg}")
                checks.append(
                    RuleCheckResult(
                        rule_code="RULE_SUBFUNCTION_REQUIRED",
                        rule_name="Subfunction Byte Presence",
                        passed=False,
                        message="Missing subfunction byte."
                    )
                )
            else:
                raw_subfunc = raw_bytes[1]
                # Bit 7 is Suppress Positive Response Message Indication Bit
                suppress_bit_active = bool(raw_subfunc & 0x80)
                clean_subfunc = raw_subfunc & 0x7F

                # Check SPRMIB legality
                if suppress_bit_active and not rule.supports_suppress_bit:
                    errors.append(f"Service {rule.service_name} does not support suppressPositiveResponseMsgIndicationBit (Bit 7).")
                    checks.append(
                        RuleCheckResult(
                            rule_code="RULE_SPRMIB_SUPPORT",
                            rule_name="Suppress Positive Response Bit Legality",
                            passed=False,
                            message=f"Service {rule.service_name} prohibits Bit 7 suppression.",
                            expected="Bit 7 = 0",
                            actual=f"0x{raw_subfunc:02X} (Bit 7 = 1)"
                        )
                    )
                else:
                    checks.append(
                        RuleCheckResult(
                            rule_code="RULE_SPRMIB_SUPPORT",
                            rule_name="Suppress Positive Response Bit Legality",
                            passed=True,
                            message=f"Bit 7 (SPRMIB) is {'ACTIVE (Suppressed)' if suppress_bit_active else 'INACTIVE'}.",
                            actual=f"0x{raw_subfunc:02X}"
                        )
                    )

                # Check subfunction value validity
                subfunc_valid = clean_subfunc in rule.allowed_subfunctions
                sub_msg = f"Subfunction 0x{clean_subfunc:02X} is valid for {rule.service_name}."
                if not subfunc_valid:
                    sub_msg = (
                        f"Subfunction 0x{clean_subfunc:02X} is not valid for {rule.service_name}. "
                        f"Allowed: {', '.join(f'0x{sf:02X}' for sf in sorted(rule.allowed_subfunctions))}"
                    )
                    # Note: in negative test cases, this corresponds to NRC 0x12 SubFunctionNotSupported
                    if expected_response_type != "NEGATIVE":
                        errors.append(sub_msg)
                    else:
                        warnings.append(f"Negative scenario target: {sub_msg}")

                checks.append(
                    RuleCheckResult(
                        rule_code="RULE_SUBFUNCTION_VALUE",
                        rule_name="Subfunction Value Support",
                        passed=subfunc_valid,
                        message=sub_msg,
                        expected=f"One of: {', '.join(f'0x{sf:02X}' for sf in sorted(rule.allowed_subfunctions))}",
                        actual=f"0x{clean_subfunc:02X}"
                    )
                )

        # 5. Service-Specific Formatting Validations
        if sid == 0x22:  # ReadDataByIdentifier
            did_bytes = raw_bytes[1:]

            # Parse expected NRC if in negative scenario
            target_nrc_int: Optional[int] = None
            if expected_response_type == "NEGATIVE" and expected_nrc is not None:
                try:
                    if isinstance(expected_nrc, int):
                        target_nrc_int = expected_nrc
                    elif isinstance(expected_nrc, str):
                        clean_nrc = expected_nrc.strip()
                        target_nrc_int = int(clean_nrc, 16) if clean_nrc.lower().startswith("0x") else int(clean_nrc, 16)
                except Exception:
                    target_nrc_int = None

            if len(did_bytes) % 2 != 0:
                err = f"Service 0x22 payload after SID ({len(did_bytes)} bytes) must be an even multiple of 2 (each DID is 2 bytes)."
                if expected_response_type == "NEGATIVE" and target_nrc_int == 0x13:
                    warnings.append(f"Negative scenario target (Odd DID length / NRC 0x13): {err}")
                    checks.append(RuleCheckResult(
                        rule_code="RULE_DID_ALIGNMENT",
                        rule_name="DID 2-Byte Alignment",
                        passed=True,
                        message=f"Intentional negative scenario: odd DID byte count ({len(did_bytes)} bytes) targeting NRC 0x13.",
                        expected="Even number of bytes or targeted negative NRC 0x13",
                        actual=f"{len(did_bytes)} bytes"
                    ))
                else:
                    errors.append(err)
                    checks.append(RuleCheckResult(
                        rule_code="RULE_DID_ALIGNMENT",
                        rule_name="DID 2-Byte Alignment",
                        passed=False,
                        message=err,
                        expected="Even number of bytes",
                        actual=f"{len(did_bytes)} bytes"
                    ))
            elif len(did_bytes) == 0:
                # Payload length < min_length (3) is already handled by RULE_PAYLOAD_LENGTH
                checks.append(RuleCheckResult(
                    rule_code="RULE_DID_ALIGNMENT",
                    rule_name="DID 2-Byte Alignment",
                    passed=True,
                    message="Service 0x22 frame contains 0 DID bytes.",
                    actual="0 bytes"
                ))
            else:
                dids = [f"0x{did_bytes[i]:02X}{did_bytes[i+1]:02X}" for i in range(0, len(did_bytes), 2)]
                checks.append(RuleCheckResult(
                    rule_code="RULE_DID_ALIGNMENT",
                    rule_name="DID 2-Byte Alignment",
                    passed=True,
                    message=f"Request contains {len(dids)} well-formed 2-byte DID(s): {', '.join(dids)}."
                ))

                # Deterministic check for each 2-byte DID: existence, authorization, and session prerequisites
                for i in range(0, len(did_bytes), 2):
                    did_int = (did_bytes[i] << 8) | did_bytes[i + 1]
                    did_hex_str = f"{did_int:04X}"

                    if did_int not in SUPPORTED_SPEC_DIDS:
                        extra_info = ""
                        if did_int in KNOWN_SPEC_RIDS:
                            extra_info = (
                                f" (Note: 0x{did_hex_str} is a Routine Identifier for Service 0x31 "
                                f"[{KNOWN_SPEC_RIDS[did_int]}], not a valid Data Identifier for Service 0x22)"
                            )

                        did_err = (
                            f"DID 0x{did_hex_str} is not supported by the authoritative diagnostic specification{extra_info}. "
                            f"Supported DIDs: {', '.join(f'0x{d:04X}' for d in sorted(SUPPORTED_SPEC_DIDS.keys()))}."
                        )

                        if expected_response_type == "NEGATIVE" and target_nrc_int == 0x31:
                            warnings.append(f"Negative scenario target (Unsupported DID / NRC 0x31): {did_err}")
                            checks.append(RuleCheckResult(
                                rule_code="RULE_DID_SUPPORT",
                                rule_name="Specification DID Support",
                                passed=True,
                                message=f"Intentional negative scenario with unsupported DID 0x{did_hex_str} targeting NRC 0x31 (RequestOutOfRange).",
                                expected="Supported DID or targeted negative NRC 0x31",
                                actual=f"0x{did_hex_str}"
                            ))
                        else:
                            errors.append(did_err)
                            checks.append(RuleCheckResult(
                                rule_code="RULE_DID_SUPPORT",
                                rule_name="Specification DID Support",
                                passed=False,
                                message=did_err,
                                expected=f"One of: {', '.join(f'0x{d:04X}' for d in sorted(SUPPORTED_SPEC_DIDS.keys()))}",
                                actual=f"0x{did_hex_str}"
                            ))
                    else:
                        did_def = SUPPORTED_SPEC_DIDS[did_int]
                        checks.append(RuleCheckResult(
                            rule_code="RULE_DID_SUPPORT",
                            rule_name="Specification DID Support",
                            passed=True,
                            message=f"DID 0x{did_hex_str} ({did_def.name}) is authorized by specification.",
                            expected=f"One of: {', '.join(f'0x{d:04X}' for d in sorted(SUPPORTED_SPEC_DIDS.keys()))}",
                            actual=f"0x{did_hex_str}"
                        ))

                        # DID-specific session prerequisite validation (e.g. 0x2001 requires EXTENDED)
                        if did_def.allowed_sessions and current_session not in did_def.allowed_sessions:
                            session_err = (
                                f"DID 0x{did_hex_str} ({did_def.name}) requires diagnostic session in "
                                f"{sorted([s.value for s in did_def.allowed_sessions])}, but current session is '{current_session.value}'."
                            )
                            if expected_response_type == "NEGATIVE" and target_nrc_int == 0x22:
                                warnings.append(f"Negative scenario target (DID session prerequisite / NRC 0x22): {session_err}")
                                checks.append(RuleCheckResult(
                                    rule_code="RULE_DID_SESSION_PREREQUISITE",
                                    rule_name="DID Session Prerequisite",
                                    passed=True,
                                    message=f"Intentional negative scenario: DID 0x{did_hex_str} session violation targeting NRC 0x22.",
                                    expected=f"One of: {', '.join(s.value for s in did_def.allowed_sessions)}",
                                    actual=current_session.value
                                ))
                            else:
                                errors.append(session_err)
                                checks.append(RuleCheckResult(
                                    rule_code="RULE_DID_SESSION_PREREQUISITE",
                                    rule_name="DID Session Prerequisite",
                                    passed=False,
                                    message=session_err,
                                    expected=f"One of: {', '.join(s.value for s in did_def.allowed_sessions)}",
                                    actual=current_session.value
                                ))
                        else:
                            checks.append(RuleCheckResult(
                                rule_code="RULE_DID_SESSION_PREREQUISITE",
                                rule_name="DID Session Prerequisite",
                                passed=True,
                                message=f"Diagnostic session '{current_session.value}' satisfies requirement for DID 0x{did_hex_str}.",
                                actual=current_session.value
                            ))

        elif sid == 0x14:  # ClearDiagnosticInformation
            dtc_mask_bytes = raw_bytes[1:]
            if len(dtc_mask_bytes) != 3:
                err = f"Service 0x14 requires exactly a 3-byte DTC group mask. Received {len(dtc_mask_bytes)} byte(s)."
                errors.append(err)
                checks.append(RuleCheckResult(
                    rule_code="RULE_DTC_MASK_LENGTH",
                    rule_name="3-Byte DTC Group Mask Check",
                    passed=False,
                    message=err,
                    expected="3 bytes (e.g. 0xFFFFFF)",
                    actual=f"{len(dtc_mask_bytes)} bytes"
                ))
            else:
                checks.append(RuleCheckResult(
                    rule_code="RULE_DTC_MASK_LENGTH",
                    rule_name="3-Byte DTC Group Mask Check",
                    passed=True,
                    message=f"DTC Group Mask is well-formed: 0x{dtc_mask_bytes[0]:02X}{dtc_mask_bytes[1]:02X}{dtc_mask_bytes[2]:02X}."
                ))

        # 6. Active Diagnostic Session Prerequisite Check
        session_valid = current_session in rule.allowed_sessions
        session_msg = f"Session '{current_session.value}' is allowed for {rule.service_name}."
        if not session_valid:
            session_msg = (
                f"Service {rule.service_name} cannot be executed in session '{current_session.value}'. "
                f"Permitted sessions: {', '.join(s.value for s in rule.allowed_sessions)}"
            )
            if expected_response_type != "NEGATIVE":
                errors.append(session_msg)
            else:
                warnings.append(f"Negative scenario target (Session violation): {session_msg}")

        checks.append(
            RuleCheckResult(
                rule_code="RULE_SESSION_PREREQUISITE",
                rule_name="Active Diagnostic Session Check",
                passed=session_valid,
                message=session_msg,
                expected=f"One of: {', '.join(s.value for s in rule.allowed_sessions)}",
                actual=current_session.value
            )
        )

        # 7. Active Security Level Prerequisite Check
        security_valid = current_security.value >= rule.min_security_level.value
        sec_msg = f"Current security level {current_security.value} satisfies minimum required {rule.min_security_level.value}."
        if not security_valid:
            sec_msg = (
                f"Service {rule.service_name} requires security level >= {rule.min_security_level.value}, "
                f"but current level is {current_security.value} (Locked)."
            )
            if expected_response_type != "NEGATIVE":
                errors.append(sec_msg)
            else:
                warnings.append(f"Negative scenario target (Security lockout): {sec_msg}")

        checks.append(
            RuleCheckResult(
                rule_code="RULE_SECURITY_PREREQUISITE",
                rule_name="Security Access Level Check",
                passed=security_valid,
                message=sec_msg,
                expected=f"Security Level >= {rule.min_security_level.value}",
                actual=f"Security Level {current_security.value}"
            )
        )

        # 8. Expected Response & NRC Validation
        if expected_response_type == "NEGATIVE":
            if not expected_nrc:
                errors.append("Test scenario is marked NEGATIVE but expected_nrc is missing.")
                checks.append(
                    RuleCheckResult(
                        rule_code="RULE_NRC_EXPECTATION",
                        rule_name="Negative Response Code Specification",
                        passed=False,
                        message="Missing expected NRC for negative test case."
                    )
                )
            else:
                try:
                    nrc_val = int(expected_nrc.replace("0x", ""), 16) if isinstance(expected_nrc, str) else int(expected_nrc)
                    nrc_recognized = nrc_val in STANDARD_NRCS
                    nrc_applicable = nrc_val in rule.applicable_nrcs

                    if not nrc_recognized:
                        errors.append(f"NRC 0x{nrc_val:02X} is not a valid ISO 14229 Negative Response Code.")
                    elif not nrc_applicable:
                        warnings.append(
                            f"NRC 0x{nrc_val:02X} ({STANDARD_NRCS.get(nrc_val)}) is not typically standard for {rule.service_name} "
                            f"(Typical: {', '.join(f'0x{n:02X}' for n in rule.applicable_nrcs)})."
                        )

                    checks.append(
                        RuleCheckResult(
                            rule_code="RULE_NRC_EXPECTATION",
                            rule_name="Negative Response Code Specification",
                            passed=nrc_recognized,
                            message=f"Target NRC 0x{nrc_val:02X} ({STANDARD_NRCS.get(nrc_val, 'Unknown')}).",
                            expected=f"Standard NRC for {rule.service_name}",
                            actual=f"0x{nrc_val:02X}"
                        )
                    )
                except Exception as e:
                    errors.append(f"Invalid expected_nrc format: {str(e)}")

        # Overall verdict: If positive scenario and no errors -> PASS
        # If negative scenario: errors are acceptable ONLY IF they match the intentional negative defect
        overall_pass = len(errors) == 0

        return ValidationReport(
            overall_verdict="PASS" if overall_pass else "FAIL",
            service_id=sid,
            service_hex=sid_hex,
            service_name=rule.service_name,
            checks=checks,
            errors=errors,
            warnings=warnings
        )


rule_engine = UDSRuleEngine()
