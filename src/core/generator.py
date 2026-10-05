"""
Test Case Generator Module for Phase 2.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Generates structured Pydantic test cases for ISO 14229 services with both positive
and negative test scenarios. Every generated test case is deterministically validated
through the UDSRuleEngine immediately upon creation.
"""

from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.core.rules import (
    DiagnosticSession,
    SecurityLevel,
    SERVICE_RULES,
    rule_engine,
    ValidationReport,
)


class TestStep(BaseModel):
    """Atomic diagnostic test step."""
    __test__ = False
    step_number: int
    description: str
    request_hex: str
    expected_response_type: str = "POSITIVE"  # "POSITIVE" or "NEGATIVE"
    expected_response_hex: str = ""
    expected_nrc: Optional[str] = None
    timeout_ms: int = 2000
    suppress_pos_rsp: bool = False


class TestCase(BaseModel):
    """Structured UDS Diagnostic Test Case."""
    __test__ = False  # Inform pytest this is a data model, not a test suite
    test_case_id: str
    project_id: str
    service_id: int
    service_name: str
    test_type: str  # "POSITIVE", "NEGATIVE_SUBFUNCTION", "NEGATIVE_LENGTH", "NEGATIVE_SESSION", "NEGATIVE_SECURITY"
    title: str
    description: str
    preconditions: Dict[str, Any] = Field(default_factory=dict)
    steps: List[TestStep] = Field(default_factory=list)
    pass_fail_criteria: str
    rule_verification_status: str = "PENDING_VERIFICATION"  # "PASSED", "FAILED_RULE_VIOLATION"
    rule_verification_report: Optional[ValidationReport] = None
    review_status: str = "DRAFT"  # DRAFT -> RULE_VERIFIED -> PENDING_REVIEW -> APPROVED / EDITED / REJECTED
    citation_references: List[str] = Field(default_factory=list)
    generation_source: str = "DETERMINISTIC_RULE_TEMPLATE"  # "LOCAL_OLLAMA_LLM", "FALLBACK_TEMPLATE_MOCK", "DETERMINISTIC_RULE_TEMPLATE"
    generation_model: Optional[str] = "rule-template-v1"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AssembledPrompt(BaseModel):
    """Encapsulates an assembled, LLM-agnostic prompt package for AI test generation."""
    system_prompt: str
    user_prompt: str
    target_schema_json: Dict[str, Any]
    service_id: int
    service_name: str
    test_scenario: str


class UDSTestGenerator:
    """
    Automated diagnostic test case generator.
    Produces compliant positive test cases and complementary negative fault-injection scenarios.
    Applies deterministic protocol rules immediately to verify every generated frame.
    """

    def __init__(self):
        self.engine = rule_engine

    def generate_positive_test(
        self,
        service_id: int,
        project_id: str = "tata_uds_pilot",
        subfunction: Optional[int] = None,
        did_hex: Optional[str] = None,
        session: DiagnosticSession = DiagnosticSession.DEFAULT,
        security: SecurityLevel = SecurityLevel.LOCKED,
        citations: Optional[List[str]] = None
    ) -> TestCase:
        """Generates a nominal positive test scenario for a service."""
        if service_id not in SERVICE_RULES:
            raise ValueError(f"Service ID 0x{service_id:02X} is not supported.")

        rule = SERVICE_RULES[service_id]
        
        # Build request frame
        if rule.has_subfunction:
            sf = subfunction if subfunction is not None else sorted(list(rule.allowed_subfunctions))[0]
            if service_id == 0x28:
                req_hex = f"{service_id:02X} {sf:02X} 01"  # normalCommunication
            elif service_id == 0x31:
                rid = did_hex or "0201"
                req_hex = f"{service_id:02X} {sf:02X} {rid}"
            elif service_id == 0x85:
                req_hex = f"{service_id:02X} {sf:02X}"
            else:
                req_hex = f"{service_id:02X} {sf:02X}"
        else:
            if service_id == 0x22:
                target_did = did_hex.replace("0x", "").replace(" ", "") if did_hex else "F190"
                req_hex = f"22 {target_did}"
            elif service_id == 0x2E:
                target_did = did_hex.replace("0x", "").replace(" ", "") if did_hex else "2001"
                req_hex = f"2E {target_did} 00 64"
            elif service_id == 0x14:
                req_hex = "14 FF FF FF"  # All DTCs
            elif service_id == 0x2F:
                target_did = did_hex.replace("0x", "").replace(" ", "") if did_hex else "2001"
                req_hex = f"2F {target_did} 03 01"  # shortTermAdjustment
            elif service_id == 0x34:
                req_hex = "34 00 44 00 01 00 00 00 00 10 00"
            elif service_id == 0x36:
                req_hex = "36 01 AA BB CC DD"
            elif service_id == 0x37:
                req_hex = "37"
            else:
                req_hex = f"{service_id:02X}"

        # Expected positive response starts with SID + 0x40
        resp_sid = f"{(service_id + 0x40):02X}"
        expected_resp = f"{resp_sid} ..."

        step = TestStep(
            step_number=1,
            description=f"Send positive request for {rule.service_name} (0x{service_id:02X})",
            request_hex=req_hex,
            expected_response_type="POSITIVE",
            expected_response_hex=expected_resp,
            timeout_ms=50 if service_id == 0x10 else 2000
        )

        test_id = f"TC_UDS_0x{service_id:02X}_POS_{uuid.uuid4().hex[:6].upper()}"
        test_case = TestCase(
            test_case_id=test_id,
            project_id=project_id,
            service_id=service_id,
            service_name=rule.service_name,
            test_type="POSITIVE",
            title=f"Positive Test for {rule.service_name} (0x{service_id:02X})",
            description=f"Verify ECU positive response (0x{resp_sid}) for valid {rule.service_name} request.",
            preconditions={"session": session.value, "security": security.value},
            steps=[step],
            pass_fail_criteria=f"ECU must respond with positive response SID 0x{resp_sid} within timeout threshold.",
            citation_references=citations or []
        )

        # Immediate deterministic rule verification
        report = self.engine.validate_request(
            request_hex=req_hex,
            current_session=session,
            current_security=security,
            expected_response_type="POSITIVE"
        )
        test_case.rule_verification_report = report
        if report.overall_verdict == "PASS":
            test_case.rule_verification_status = "PASSED"
            test_case.review_status = "PENDING_REVIEW"
        else:
            test_case.rule_verification_status = "FAILED_RULE_VIOLATION"
            test_case.review_status = "DRAFT"

        return test_case

    def generate_negative_test(
        self,
        service_id: int,
        defect_type: str,
        project_id: str = "tata_uds_pilot",
        session: DiagnosticSession = DiagnosticSession.DEFAULT,
        security: SecurityLevel = SecurityLevel.LOCKED,
        citations: Optional[List[str]] = None
    ) -> TestCase:
        """
        Generates a targeted negative test case.
        Supported defect types:
        - 'INVALID_SUBFUNCTION' -> Expected NRC 0x12 (SubFunctionNotSupported)
        - 'INCORRECT_LENGTH'    -> Expected NRC 0x13 (IncorrectMessageLength)
        - 'SESSION_VIOLATION'   -> Expected NRC 0x7E/0x7F or 0x22 (ConditionsNotCorrect)
        - 'SECURITY_LOCKED'     -> Expected NRC 0x33 (SecurityAccessDenied)
        - 'DID_OUT_OF_RANGE'    -> Expected NRC 0x31 (RequestOutOfRange)
        """
        if service_id not in SERVICE_RULES:
            raise ValueError(f"Service ID 0x{service_id:02X} is not supported.")

        rule = SERVICE_RULES[service_id]
        expected_nrc = "0x22"
        description = ""
        req_hex = f"{service_id:02X}"

        if defect_type == "INVALID_SUBFUNCTION" and rule.has_subfunction:
            expected_nrc = "0x12"
            invalid_sf = 0x7A  # Out of range subfunction
            req_hex = f"{service_id:02X} {invalid_sf:02X}"
            description = f"Send {rule.service_name} with unsupported subfunction 0x{invalid_sf:02X}. Verify NRC 0x12."

        elif defect_type == "INCORRECT_LENGTH":
            expected_nrc = "0x13"
            if rule.min_length > 1:
                # Truncate
                req_hex = f"{service_id:02X}"
            else:
                # Append junk
                req_hex = f"{service_id:02X} 00 11 22 33 44 55"
            description = f"Send truncated/invalid length payload for {rule.service_name}. Verify NRC 0x13."

        elif defect_type == "SESSION_VIOLATION":
            expected_nrc = "0x7F" if service_id in (0x2E, 0x28, 0x85) else "0x22"
            session = DiagnosticSession.DEFAULT  # Force default session where prohibited
            req_hex = f"{service_id:02X} 01"
            description = f"Send {rule.service_name} in prohibited DEFAULT session. Verify NRC {expected_nrc}."

        elif defect_type == "SECURITY_LOCKED":
            expected_nrc = "0x33"
            security = SecurityLevel.LOCKED
            session = DiagnosticSession.EXTENDED
            if service_id == 0x2E:
                req_hex = "2E 20 01 00 64"
            else:
                req_hex = f"{service_id:02X} 01"
            description = f"Attempt secured service {rule.service_name} while locked. Verify NRC 0x33 (SecurityAccessDenied)."

        elif defect_type == "DID_OUT_OF_RANGE" and service_id == 0x22:
            expected_nrc = "0x31"
            req_hex = "22 FF FF"  # Unsupported DID
            description = "Request non-existent DID 0xFFFF. Verify NRC 0x31 (RequestOutOfRange)."

        else:
            # Default fallback negative condition
            expected_nrc = "0x22"
            req_hex = f"{service_id:02X} FF"
            description = f"Send invalid condition request for {rule.service_name}. Verify NRC 0x22."

        step = TestStep(
            step_number=1,
            description=description,
            request_hex=req_hex,
            expected_response_type="NEGATIVE",
            expected_response_hex=f"7F {service_id:02X} {expected_nrc.replace('0x', '')}",
            expected_nrc=expected_nrc,
            timeout_ms=2000
        )

        test_id = f"TC_UDS_0x{service_id:02X}_NEG_{defect_type[:3]}_{uuid.uuid4().hex[:6].upper()}"
        test_case = TestCase(
            test_case_id=test_id,
            project_id=project_id,
            service_id=service_id,
            service_name=rule.service_name,
            test_type=f"NEGATIVE_{defect_type}",
            title=f"Negative Test ({defect_type}) for {rule.service_name}",
            description=description,
            preconditions={"session": session.value, "security": security.value},
            steps=[step],
            pass_fail_criteria=f"ECU must reject invalid request and respond with NRC {expected_nrc} ({rule.service_name}).",
            citation_references=citations or []
        )

        # Immediate deterministic rule verification
        report = self.engine.validate_request(
            request_hex=req_hex,
            current_session=session,
            current_security=security,
            expected_response_type="NEGATIVE",
            expected_nrc=expected_nrc
        )
        test_case.rule_verification_report = report
        # In a negative test case, if the rule engine confirms the expected NRC and format -> PASSED
        if report.overall_verdict == "PASS":
            test_case.rule_verification_status = "PASSED"
            test_case.review_status = "PENDING_REVIEW"
        else:
            test_case.rule_verification_status = "FAILED_RULE_VIOLATION"
            test_case.review_status = "DRAFT"

        return test_case

    def generate_suite_for_service(
        self,
        service_id: int,
        project_id: str = "tata_uds_pilot",
        citations: Optional[List[str]] = None
    ) -> List[TestCase]:
        """Generates a complete pair of positive and complementary negative test scenarios."""
        rule = SERVICE_RULES[service_id]
        suite: List[TestCase] = []

        # 1. Nominal Positive Case
        session = sorted(list(rule.allowed_sessions), key=lambda s: s.value)[0]
        pos_case = self.generate_positive_test(
            service_id=service_id,
            project_id=project_id,
            session=session,
            security=rule.min_security_level,
            citations=citations
        )
        suite.append(pos_case)

        # 2. Complementary Negative Case: Incorrect Length
        neg_len = self.generate_negative_test(
            service_id=service_id,
            defect_type="INCORRECT_LENGTH",
            project_id=project_id,
            session=session,
            security=rule.min_security_level,
            citations=citations
        )
        suite.append(neg_len)

        # 3. Complementary Negative Case: Invalid Subfunction (if applicable)
        if rule.has_subfunction:
            neg_sf = self.generate_negative_test(
                service_id=service_id,
                defect_type="INVALID_SUBFUNCTION",
                project_id=project_id,
                session=session,
                security=rule.min_security_level,
                citations=citations
            )
            suite.append(neg_sf)

        # 4. Complementary Negative Case: Security Lockout (if service requires security)
        if rule.min_security_level.value > 0:
            neg_sec = self.generate_negative_test(
                service_id=service_id,
                defect_type="SECURITY_LOCKED",
                project_id=project_id,
                session=session,
                security=SecurityLevel.LOCKED,
                citations=citations
            )
            suite.append(neg_sec)

        return suite

    def build_test_generation_prompt(
        self,
        service_id: int,
        test_scenario: str = "POSITIVE",
        context_text: Optional[str] = None,
        citations: Optional[List[str]] = None,
        session: str = "DEFAULT",
        security_level: int = 0,
        target_did: Optional[str] = None,
        subfunction: Optional[int] = None
    ) -> AssembledPrompt:
        """Exposes prompt assembly through the generator instance."""
        return build_test_generation_prompt(
            service_id=service_id,
            test_scenario=test_scenario,
            context_text=context_text,
            citations=citations,
            session=session,
            security_level=security_level,
            target_did=target_did,
            subfunction=subfunction
        )


def build_test_generation_prompt(
    service_id: int,
    test_scenario: str = "POSITIVE",
    context_text: Optional[str] = None,
    citations: Optional[List[str]] = None,
    session: str = "DEFAULT",
    security_level: int = 0,
    target_did: Optional[str] = None,
    subfunction: Optional[int] = None
) -> AssembledPrompt:
    """
    Pure prompt-assembly utility for AI test generation.
    Constructs an LLM-agnostic prompt package with:
    - Engineer role definition.
    - Specification context and source citation requirements.
    - Requested UDS test scenario and preconditions.
    - Strict Pydantic TestCase JSON Schema contract.
    Does NOT invoke, download, or select any LLM runtime.
    """
    if service_id not in SERVICE_RULES:
        raise ValueError(f"Service ID 0x{service_id:02X} is not supported in ISO 14229 registry.")

    rule = SERVICE_RULES[service_id]
    schema = TestCase.model_json_schema()
    schema_str = json.dumps(schema, indent=2)

    system_prompt = (
        "You are an expert Automotive Diagnostic Validation Specialist and ISO 14229-1 (UDS) Test Engineer "
        "at Tata Technologies.\n"
        "Your task is to generate structured diagnostic test cases strictly grounded in authorized vehicle "
        "specifications and compliant with ISO 14229 standards.\n\n"
        "MANDATORY GOVERNANCE & PROTOCOL RULES:\n"
        "1. Every generated request frame must adhere strictly to ISO 14229-1 byte formatting, subfunction legality, "
        "and timing parameters.\n"
        "2. All generated test cases will be validated immediately by the deterministic UDSRuleEngine. "
        "Any protocol error (e.g. incorrect length, invalid subfunction, session prerequisite violation) will cause "
        "instant rejection.\n"
        "3. Output MUST be valid JSON adhering strictly to the JSON Schema provided below. "
        "Do NOT include preamble, markdown formatting outside of ```json, explanations, or extraneous keys.\n\n"
        f"TARGET JSON SCHEMA (Pydantic TestCase):\n{schema_str}"
    )

    context_section = ""
    if context_text and context_text.strip():
        context_section = f"\n### AUTHORIZED SPECIFICATION EXCERPT:\n{context_text.strip()}\n"
    elif citations:
        context_section = f"\n### CITATION REFERENCES:\n{', '.join(citations)}\n"
    else:
        context_section = "\n### SPECIFICATION CONTEXT:\nUse standard ISO 14229-1 specification rules for this service.\n"

    target_details = []
    if rule.has_subfunction:
        sf_str = f"0x{subfunction:02X}" if subfunction is not None else f"One of {[f'0x{s:02X}' for s in sorted(rule.allowed_subfunctions)]}"
        target_details.append(f"- Subfunction: {sf_str}")
    if target_did:
        target_details.append(f"- Target Identifier / DID: {target_did}")

    target_details_str = "\n".join(target_details) if target_details else "- Standard Service Parameters"

    user_prompt = (
        f"Generate a diagnostic test case for the following UDS requirement:\n"
        f"- Target Service: 0x{service_id:02X} ({rule.service_name})\n"
        f"- Test Scenario: {test_scenario}\n"
        f"- Active Diagnostic Session Precondition: {session}\n"
        f"- Active Security Level Precondition: Level {security_level} ({'Locked' if security_level == 0 else 'Unlocked'})\n"
        f"{target_details_str}\n"
        f"{context_section}\n"
        "Generate the complete JSON test case object conforming to the schema."
    )

    return AssembledPrompt(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        target_schema_json=schema,
        service_id=service_id,
        service_name=rule.service_name,
        test_scenario=test_scenario
    )


test_generator = UDSTestGenerator()

