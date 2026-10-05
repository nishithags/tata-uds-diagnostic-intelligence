"""
Unit tests for Dual-Tier Bus Architecture and Virtual CAN Adapter (AD-03 Option 3C).
Tata Technologies: Rule-Verified AI Assistant for UDS Diagnostic Test Generation and Validation.
"""

import pytest
from src.core.execution_engine import (
    SimulatedECUAdapter,
    TestExecutionEngine,
    VirtualCANBusAdapter,
)
from src.core.generator import TestCase, TestStep, test_generator
from src.core.governance import governance_manager


def test_virtual_can_adapter_initialization():
    adapter = VirtualCANBusAdapter(channel="vcan_test_0", tx_id=0x7E0, rx_id=0x7E8)
    assert adapter.channel == "vcan_test_0"
    assert adapter.tx_id == 0x7E0
    assert adapter.rx_id == 0x7E8
    assert adapter.ecu is not None


def test_virtual_can_send_and_receive():
    adapter = VirtualCANBusAdapter(channel="vcan_test_channel")
    # Send 0x10 0x01 (Default session request)
    resp_bytes, elapsed, logs = adapter.send_and_receive(bytes([0x10, 0x01]))
    assert resp_bytes.startswith(bytes([0x50, 0x01]))
    assert elapsed >= 0.0
    assert any("Virtual CAN Bus" in log for log in logs)


def test_virtual_can_state_and_preconditions():
    adapter = VirtualCANBusAdapter(channel="vcan_test_state")
    adapter.configure_preconditions("EXTENDED", 1)
    st = adapter.get_state()
    assert st.session == "EXTENDED"
    assert st.security_locked is False

    adapter.reset_target()
    st_reset = adapter.get_state()
    assert st_reset.session == "DEFAULT"
    assert st_reset.security_locked is True


def test_execution_engine_default_adapter():
    engine = TestExecutionEngine()
    # Default adapter must strictly be SimulatedECUAdapter (Option 3C requirement)
    assert isinstance(engine.adapter, SimulatedECUAdapter)
    assert not isinstance(engine.adapter, VirtualCANBusAdapter)


def test_execution_engine_adapter_override():
    engine = TestExecutionEngine()
    vcan_adapter = VirtualCANBusAdapter(channel="vcan_test_override")

    tc = test_generator.generate_positive_test(service_id=0x10, project_id="vcan_proj")
    governance_manager.submit_review(
        test_case=tc,
        reviewer_name="Validation Lead",
        reviewer_role="Lead",
        action="APPROVE",
        comments="Approved for test run"
    )

    result = engine.execute_test_case(tc, adapter_override=vcan_adapter)
    assert result.adapter_used == "VirtualCANBusAdapter"
    assert result.overall_verdict == "PASS"
