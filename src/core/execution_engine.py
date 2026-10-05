"""
Controlled Diagnostic Test Execution Engine for Phase 3.
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.

Enforces:
1. Strict Governance Gate: Only test cases with review_status == "APPROVED" may execute.
   Attempts to execute DRAFT, RULE_VERIFIED, PENDING_REVIEW, or REJECTED tests are BLOCKED.
2. Abstract Test Bus Layer: Keeps bus execution decoupled from underlying communication transport
   (In-Process Simulated Adapter vs Virtual CAN Socket remains PENDING APPROVAL).
3. ISO 14229 Response Comparator: Evaluates timing (P2/P2* thresholds), positive PRPR frames,
   and Negative Response Codes (NRCs).
4. Fault Injection Support: Controlled negative-test verification across all Phase 2 defect models.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from src.core.generator import TestCase, TestStep
from src.core.governance import GovernanceError, governance_manager
from src.core.rules import DiagnosticSession, SecurityLevel, rule_engine
from src.core.simulator import FaultProfile, SimulatedECU, simulated_ecu, ECUStateSnapshot


# ==========================================
# Execution Data Models
# ==========================================

class StepExecutionResult(BaseModel):
    """Result of an individual diagnostic test step execution."""
    __test__ = False
    step_number: int
    description: str
    request_hex: str
    actual_response_hex: str
    expected_response_type: str
    expected_response_hex: str
    expected_nrc: Optional[str] = None
    actual_nrc: Optional[str] = None
    elapsed_ms: float
    timeout_ms: int
    timing_verdict: str  # "PASS" or "TIMEOUT"
    step_verdict: str    # "PASS" or "FAIL"
    error_message: Optional[str] = None
    trace_logs: List[str] = Field(default_factory=list)


class TestCaseExecutionResult(BaseModel):
    """Aggregated execution report for a diagnostic test case."""
    __test__ = False
    execution_id: str
    test_case_id: str
    project_id: str
    title: str
    test_type: str
    overall_verdict: str  # "PASS" or "FAIL"
    preconditions: Dict[str, Any]
    initial_ecu_state: ECUStateSnapshot
    final_ecu_state: ECUStateSnapshot
    total_elapsed_ms: float
    steps_total: int
    steps_passed: int
    step_results: List[StepExecutionResult]
    governance_verified: bool = True
    adapter_used: str = "SimulatedECUAdapter"
    executed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    audit_id: Optional[str] = None


# ==========================================
# Abstract Test Bus Interface
# ==========================================

class BaseDiagnosticBusAdapter(ABC):
    """
    Abstract communication adapter for sending and receiving diagnostic frames.
    Preserves bus independence without permanently committing to a specific CAN driver
    (DirectSimulator vs Virtual CAN Socket remains PENDING FORMAL USER APPROVAL).
    """

    @abstractmethod
    def send_and_receive(
        self,
        request_bytes: bytes,
        timeout_ms: int = 2000,
        fault_profile: Optional[FaultProfile] = None
    ) -> Tuple[bytes, float, List[str]]:
        """Sends a request frame and returns (response_bytes, elapsed_ms, logs)."""
        pass

    @abstractmethod
    def reset_target(self) -> None:
        """Resets the execution target to default diagnostic state."""
        pass

    @abstractmethod
    def configure_preconditions(self, session: str, security: int) -> None:
        """Configures target preconditions prior to test execution."""
        pass

    @abstractmethod
    def get_state(self) -> ECUStateSnapshot:
        """Retrieves target diagnostic state."""
        pass


class SimulatedECUAdapter(BaseDiagnosticBusAdapter):
    """
    In-memory communication adapter binding the execution engine to SimulatedECU.
    Completely isolated from real vehicle CAN networks.
    """

    def __init__(self, ecu: Optional[SimulatedECU] = None):
        self.ecu = ecu or simulated_ecu

    def send_and_receive(
        self,
        request_bytes: bytes,
        timeout_ms: int = 2000,
        fault_profile: Optional[FaultProfile] = None
    ) -> Tuple[bytes, float, List[str]]:
        return self.ecu.handle_request(request_bytes, fault_profile=fault_profile)

    def reset_target(self) -> None:
        self.ecu.reset_state()

    def configure_preconditions(self, session: str, security: int) -> None:
        try:
            sess_enum = DiagnosticSession(session)
        except Exception:
            sess_enum = DiagnosticSession.DEFAULT
        try:
            sec_enum = SecurityLevel(security)
        except Exception:
            sec_enum = SecurityLevel.LOCKED
        self.ecu.set_preconditions(sess_enum, sec_enum)

    def get_state(self) -> ECUStateSnapshot:
        return self.ecu.get_snapshot()


class VirtualCANBusAdapter(BaseDiagnosticBusAdapter):
    """
    Optional secondary diagnostic bus adapter operating over python-can virtual channels.
    Provides external toolchain interoperability (Vector CANoe / virtual bus taps).
    Retains SimulatedECUAdapter as the primary default regression runner per approved AD-03.
    """
    __test__ = False

    def __init__(
        self,
        channel: str = "vcan0",
        tx_id: int = 0x7E0,
        rx_id: int = 0x7E8,
        ecu: Optional[SimulatedECU] = None
    ):
        self.channel = channel
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.ecu = ecu or simulated_ecu
        self._bus = None

    def _ensure_bus(self):
        if self._bus is None:
            try:
                import can
                self._bus = can.interface.Bus(interface="virtual", channel=self.channel)
            except Exception:
                self._bus = None

    def send_and_receive(
        self,
        request_bytes: bytes,
        timeout_ms: int = 2000,
        fault_profile: Optional[FaultProfile] = None
    ) -> Tuple[bytes, float, List[str]]:
        self._ensure_bus()
        start = time.time()
        logs: List[str] = [f"Virtual CAN Bus ({self.channel}): Transmitting frame TX ID 0x{self.tx_id:03X}."]

        if self._bus is not None:
            try:
                import can
                msg = can.Message(arbitration_id=self.tx_id, data=request_bytes, is_extended_id=False)
                self._bus.send(msg)
                logs.append(f"Virtual CAN Bus: Emitted CAN frame with DLC={len(request_bytes)}.")
            except Exception as e:
                logs.append(f"Virtual CAN Bus Warning: Virtual bus send failed ({e}). Routed in-process.")

        resp_bytes, ecu_elapsed, ecu_logs = self.ecu.handle_request(request_bytes, fault_profile=fault_profile)
        logs.extend(ecu_logs)

        if self._bus is not None and resp_bytes:
            try:
                import can
                resp_msg = can.Message(arbitration_id=self.rx_id, data=resp_bytes, is_extended_id=False)
                self._bus.send(resp_msg)
                logs.append(f"Virtual CAN Bus: Simulated ECU response frame RX ID 0x{self.rx_id:03X} received.")
            except Exception:
                pass

        total_elapsed = max((time.time() - start) * 1000.0, ecu_elapsed)
        return resp_bytes, total_elapsed, logs

    def reset_target(self) -> None:
        self.ecu.reset_state()

    def configure_preconditions(self, session: str, security: int) -> None:
        try:
            sess_enum = DiagnosticSession(session)
        except Exception:
            sess_enum = DiagnosticSession.DEFAULT
        try:
            sec_enum = SecurityLevel(security)
        except Exception:
            sec_enum = SecurityLevel.LOCKED
        self.ecu.set_preconditions(sess_enum, sec_enum)

    def get_state(self) -> ECUStateSnapshot:
        return self.ecu.get_snapshot()


# ==========================================
# Execution Engine
# ==========================================

class TestExecutionEngine:
    """
    Controls and audits test execution against the diagnostic bus adapter.
    Enforces the mandatory Tata Technologies governance guard: only APPROVED tests can execute.
    Maintains SimulatedECUAdapter as the primary default regression runner.
    """
    __test__ = False

    def __init__(self, adapter: Optional[BaseDiagnosticBusAdapter] = None):
        self.adapter = adapter or SimulatedECUAdapter()

    def execute_test_case(
        self,
        test_case: TestCase,
        fault_profile: Optional[FaultProfile] = None,
        operator_name: str = "Automated Test Runner",
        adapter_override: Optional[BaseDiagnosticBusAdapter] = None
    ) -> TestCaseExecutionResult:
        """
        Executes an approved test case, validating each step's response and timing.
        Raises GovernanceError if test case is not APPROVED.
        Defaults to SimulatedECUAdapter unless adapter_override is explicitly provided.
        """
        # 1. MANDATORY GOVERNANCE GUARDRAIL: Strict approval check
        governance_manager.assert_can_export_or_execute(test_case)

        active_adapter = adapter_override or self.adapter
        execution_id = f"exec_{test_case.test_case_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        # 2. Configure Preconditions
        req_session = test_case.preconditions.get("session", "DEFAULT")
        req_security = test_case.preconditions.get("security", 0)
        active_adapter.configure_preconditions(session=req_session, security=req_security)
        initial_state = active_adapter.get_state()

        step_results: List[StepExecutionResult] = []
        overall_pass = True
        total_start = time.time()

        # 3. Execute Steps Sequentially
        for step in test_case.steps:
            step_result = self._execute_step(step, fault_profile, active_adapter)
            step_results.append(step_result)
            if step_result.step_verdict != "PASS":
                overall_pass = False

        total_elapsed = (time.time() - total_start) * 1000.0
        final_state = active_adapter.get_state()
        steps_passed = sum(1 for s in step_results if s.step_verdict == "PASS")

        # 4. Record Audit Event
        overall_verdict_str = "PASS" if overall_pass else "FAIL"
        audit_event = governance_manager.log_audit(
            project_id=test_case.project_id,
            event_type="TEST_EXECUTED",
            performed_by=operator_name,
            details={
                "execution_id": execution_id,
                "test_case_id": test_case.test_case_id,
                "test_type": test_case.test_type,
                "overall_verdict": overall_verdict_str,
                "steps_total": len(test_case.steps),
                "steps_passed": steps_passed,
                "total_elapsed_ms": round(total_elapsed, 2),
                "adapter_used": type(active_adapter).__name__,
                "fault_profile": fault_profile.model_dump() if fault_profile else None
            }
        )

        return TestCaseExecutionResult(
            execution_id=execution_id,
            test_case_id=test_case.test_case_id,
            project_id=test_case.project_id,
            title=test_case.title,
            test_type=test_case.test_type,
            overall_verdict=overall_verdict_str,
            preconditions=test_case.preconditions,
            initial_ecu_state=initial_state,
            final_ecu_state=final_state,
            total_elapsed_ms=round(total_elapsed, 2),
            steps_total=len(test_case.steps),
            steps_passed=steps_passed,
            step_results=step_results,
            governance_verified=True,
            adapter_used=type(active_adapter).__name__,
            audit_id=audit_event.audit_id
        )

    def _execute_step(
        self,
        step: TestStep,
        fault_profile: Optional[FaultProfile],
        adapter: Optional[BaseDiagnosticBusAdapter] = None
    ) -> StepExecutionResult:
        """Executes an individual test step and evaluates response frames and timing."""
        active_adapter = adapter or self.adapter
        try:
            req_bytes = bytes.fromhex(step.request_hex.replace("0x", "").replace(" ", ""))
        except Exception as e:
            return StepExecutionResult(
                step_number=step.step_number,
                description=step.description,
                request_hex=step.request_hex,
                actual_response_hex="",
                expected_response_type=step.expected_response_type,
                expected_response_hex=step.expected_response_hex,
                expected_nrc=step.expected_nrc,
                elapsed_ms=0.0,
                timeout_ms=step.timeout_ms,
                timing_verdict="FAIL",
                step_verdict="FAIL",
                error_message=f"Hex syntax error: {str(e)}"
            )

        resp_bytes, elapsed_ms, trace_logs = active_adapter.send_and_receive(
            request_bytes=req_bytes,
            timeout_ms=step.timeout_ms,
            fault_profile=fault_profile
        )

        actual_resp_hex = resp_bytes.hex(" ").upper() if resp_bytes else ""
        timing_pass = elapsed_ms <= float(step.timeout_ms)
        timing_verdict = "PASS" if timing_pass else "TIMEOUT"

        # Evaluate Response Logic
        sid = req_bytes[0] if req_bytes else 0
        actual_nrc: Optional[str] = None
        error_msg: Optional[str] = None
        verdict = "FAIL"

        if not timing_pass:
            error_msg = f"Response timeout: Elapsed {elapsed_ms:.1f}ms exceeds maximum P2Server {step.timeout_ms}ms."

        elif step.expected_response_type == "POSITIVE":
            # Positive test: Expect SID + 0x40
            expected_pos_sid = sid + 0x40
            if step.suppress_pos_rsp:
                # If SPRMIB was set, response should be empty
                if len(resp_bytes) == 0:
                    verdict = "PASS"
                else:
                    error_msg = f"Expected suppressed positive response, but received: '{actual_resp_hex}'"
            elif len(resp_bytes) > 0 and resp_bytes[0] == expected_pos_sid:
                verdict = "PASS"
            elif len(resp_bytes) >= 3 and resp_bytes[0] == 0x7F:
                actual_nrc = f"0x{resp_bytes[2]:02X}"
                error_msg = f"Expected positive response (0x{expected_pos_sid:02X}), received NRC {actual_nrc}."
            else:
                error_msg = f"Response does not match positive format (expected start 0x{expected_pos_sid:02X})."

        elif step.expected_response_type == "NEGATIVE":
            # Negative test: Expect 0x7F <SID> <NRC>
            if len(resp_bytes) >= 3 and resp_bytes[0] == 0x7F and resp_bytes[1] == sid:
                actual_nrc = f"0x{resp_bytes[2]:02X}"
                if step.expected_nrc:
                    clean_expected = step.expected_nrc.upper().replace("0X", "")
                    clean_actual = actual_nrc.upper().replace("0X", "")
                    if clean_actual == clean_expected:
                        verdict = "PASS"
                    else:
                        error_msg = f"NRC mismatch: Expected {step.expected_nrc}, received {actual_nrc}."
                else:
                    verdict = "PASS"  # Generic negative pass
            elif len(resp_bytes) > 0 and resp_bytes[0] == (sid + 0x40):
                error_msg = f"Expected negative response, but ECU accepted request with positive response: '{actual_resp_hex}'"
            else:
                error_msg = f"Unexpected response format: '{actual_resp_hex}'"

        return StepExecutionResult(
            step_number=step.step_number,
            description=step.description,
            request_hex=step.request_hex,
            actual_response_hex=actual_resp_hex,
            expected_response_type=step.expected_response_type,
            expected_response_hex=step.expected_response_hex,
            expected_nrc=step.expected_nrc,
            actual_nrc=actual_nrc,
            elapsed_ms=round(elapsed_ms, 2),
            timeout_ms=step.timeout_ms,
            timing_verdict=timing_verdict,
            step_verdict=verdict if timing_pass else "FAIL",
            error_message=error_msg,
            trace_logs=trace_logs
        )


execution_engine = TestExecutionEngine()
