import os
import pytest
from unittest.mock import patch, MagicMock

from backend.agent.orchestrator import process_failed_payment
from backend.policy.schemas import ExecutionState

def get_base_record(failure_type="temporary_bank_failure", amount=1000.0, retry_count=0):
    # Using temporary_bank_failure with retry_count=0 often generates 'retry_now' candidate
    return {
        "payment_id": "pay_123",
        "customer_id": "cust_123",
        "subscription_id": "sub_123",
        "amount": amount,
        "failure_type": failure_type,
        "retry_count": retry_count,
        "customer_tenure_months": 12,
        "previous_successes": 10,
        "previous_failures": 0,
    }

@pytest.fixture(autouse=True)
def execution_env():
    os.environ["EXECUTION_MODE"] = "simulator"
    yield
    if "EXECUTION_MODE" in os.environ:
        del os.environ["EXECUTION_MODE"]

@patch("backend.agent.orchestrator.get_llm_provider")
def test_1_authorized_action_reaches_execution(mock_provider):
    # Testing that a valid allowed action is executed
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="", confidence=0.9
    ))
    
    res = process_failed_payment(get_base_record(), ExecutionState(event_id="e1"))
    
    assert res["policy_decision"]["allowed"] is True
    # retry_later translates to "scheduled" status in execution
    assert res["execution_result"]["status"] == "scheduled"
    assert res["execution_result"]["provider"] == "simulator"

@patch("backend.agent.orchestrator.get_llm_provider")
@patch("backend.execution.adapter.SimulatorExecutionAdapter.execute")
def test_2_blocked_action_never_reaches_execution_adapter(mock_execute, mock_provider):
    # This specifically tests the CRITICAL INVARIANT using a spy/mock.
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="", confidence=0.9
    ))
    
    # Exceeding retry count to force policy block
    res = process_failed_payment(get_base_record(retry_count=4), ExecutionState(event_id="e2"))
    
    assert res["policy_decision"]["allowed"] is False
    assert res["execution_result"]["status"] == "blocked"
    # CRITICAL INVARIANT CHECK
    mock_execute.assert_not_called()

@patch("backend.agent.orchestrator.get_llm_provider")
@patch("backend.execution.adapter.SimulatorExecutionAdapter.execute")
def test_3_permanent_failure_prevents_retry_execution(mock_execute, mock_provider):
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="", confidence=0.9
    ))
    
    res = process_failed_payment(get_base_record(failure_type="permanent_decline"), ExecutionState(event_id="e3"))
    
    assert res["policy_decision"]["allowed"] is False
    assert res["execution_result"]["status"] == "blocked"
    mock_execute.assert_not_called()

@patch("backend.agent.orchestrator.get_llm_provider")
@patch("backend.execution.adapter.SimulatorExecutionAdapter.execute")
def test_4_amount_above_autonomous_limit_blocked(mock_execute, mock_provider):
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="", confidence=0.9
    ))
    
    # 15000 is above the default 10000 autonomous limit
    res = process_failed_payment(get_base_record(amount=15000.0), ExecutionState(event_id="e4"))
    
    assert res["policy_decision"]["allowed"] is False
    assert res["execution_result"]["status"] == "blocked"
    mock_execute.assert_not_called()

@patch("backend.agent.orchestrator.get_llm_provider")
@patch("backend.execution.adapter.SimulatorExecutionAdapter.execute")
def test_5_duplicate_action_prevents_execution(mock_execute, mock_provider):
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="", confidence=0.9
    ))
    
    state = ExecutionState(event_id="e5_dup", previously_executed_events=["e5_dup"])
    res = process_failed_payment(get_base_record(), state)
    
    assert res["policy_decision"]["allowed"] is False
    assert res["execution_result"]["status"] == "blocked"
    mock_execute.assert_not_called()

@patch("backend.agent.orchestrator.get_llm_provider")
@patch("backend.execution.adapter.SimulatorExecutionAdapter.execute")
def test_6_llm_bypassing_policy_impossible(mock_execute, mock_provider):
    # LLM recommends an unsupported action outside of candidates
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="charge_again", reason="I insist", confidence=0.99
    ))
    
    res = process_failed_payment(get_base_record(), ExecutionState(event_id="e6"))
    
    # The agent fallback sets status='unavailable' for invalid actions, which orchestrator blocks
    assert res["policy_decision"]["allowed"] is False
    assert res["execution_result"]["status"] == "blocked"
    mock_execute.assert_not_called()

def test_7_simulator_retry_now_succeeds():
    from backend.execution.adapter import SimulatorExecutionAdapter
    from backend.recovery.schemas import PaymentContext
    adapter = SimulatorExecutionAdapter()
    ctx = PaymentContext(amount=100, failure_type="test", retry_count=0, customer_tenure_months=1, previous_successes=0, previous_failures=0)
    
    res = adapter.execute("retry_now", ctx, "e7")
    assert res.status == "executed"
    assert res.success is True

def test_8_simulator_retry_later_scheduled():
    from backend.execution.adapter import SimulatorExecutionAdapter
    from backend.recovery.schemas import PaymentContext
    adapter = SimulatorExecutionAdapter()
    ctx = PaymentContext(amount=100, failure_type="test", retry_count=0, customer_tenure_months=1, previous_successes=0, previous_failures=0)
    
    res = adapter.execute("retry_later", ctx, "e8")
    assert res.status == "scheduled"
    assert res.success is True
    assert "scheduled_for" in res.metadata

def test_9_simulator_payment_link_succeeds():
    from backend.execution.adapter import SimulatorExecutionAdapter
    from backend.recovery.schemas import PaymentContext
    adapter = SimulatorExecutionAdapter()
    ctx = PaymentContext(amount=100, failure_type="test", retry_count=0, customer_tenure_months=1, previous_successes=0, previous_failures=0)
    
    res = adapter.execute("payment_link", ctx, "e9")
    assert res.status == "executed"
    assert res.success is True

def test_10_simulator_escalate_and_stop_do_not_execute_payment():
    from backend.execution.adapter import SimulatorExecutionAdapter
    from backend.recovery.schemas import PaymentContext
    adapter = SimulatorExecutionAdapter()
    ctx = PaymentContext(amount=100, failure_type="test", retry_count=0, customer_tenure_months=1, previous_successes=0, previous_failures=0)
    
    res_esc = adapter.execute("escalate", ctx, "e10")
    assert res_esc.status == "escalated"
    assert res_esc.success is True
    
    res_stop = adapter.execute("stop", ctx, "e10")
    assert res_stop.status == "stopped"
    assert res_stop.success is True

def test_11_razorpay_adapter_no_credentials():
    from backend.razorpay.adapter import RazorpayExecutionAdapter
    from backend.recovery.schemas import PaymentContext
    
    # Unset env vars
    keys = ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"]
    old_vals = {k: os.environ.get(k) for k in keys}
    for k in keys:
        if k in os.environ: del os.environ[k]
        
    adapter = RazorpayExecutionAdapter()
    ctx = PaymentContext(amount=100, failure_type="test", retry_count=0, customer_tenure_months=1, previous_successes=0, previous_failures=0)
    
    res = adapter.execute("payment_link", ctx, "e11")
    assert res.status == "failed"
    assert res.success is False
    assert "credentials not configured" in res.message.lower()
    
    # Restore
    for k, v in old_vals.items():
        if v is not None: os.environ[k] = v

@patch("backend.agent.orchestrator.get_llm_provider")
def test_12_verification_outcomes(mock_provider):
    # Test how execution results map to verification status in orchestrator flow
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    
    # We will mock the execution adapter to return specific states to test verifier
    
    # 1. retry_now -> executed -> recovered
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_exec:
        from backend.execution.schemas import ExecutionResult
        mock_exec.return_value = ExecutionResult(
            execution_id="1", action="retry_now", status="executed", provider="sim", amount=100, success=True
        )
        mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
            selected_action="retry_now", reason="", confidence=0.9
        ))
        res1 = process_failed_payment(get_base_record(), ExecutionState(event_id="v1"))
        assert res1["verification_result"]["verification_status"] == "recovered"
    
    # 2. payment_link -> executed -> pending
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_exec:
        from backend.execution.schemas import ExecutionResult
        mock_exec.return_value = ExecutionResult(
            execution_id="2", action="payment_link", status="executed", provider="sim", amount=100, success=True
        )
        mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
            selected_action="payment_link", reason="", confidence=0.9
        ))
        res2 = process_failed_payment(get_base_record(), ExecutionState(event_id="v2"))
        assert res2["verification_result"]["verification_status"] == "pending"
        
    # 3. retry_later -> scheduled -> pending
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_exec:
        from backend.execution.schemas import ExecutionResult
        mock_exec.return_value = ExecutionResult(
            execution_id="3", action="retry_later", status="scheduled", provider="sim", amount=100, success=True
        )
        mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
            selected_action="retry_later", reason="", confidence=0.9
        ))
        res3 = process_failed_payment(get_base_record(), ExecutionState(event_id="v3"))
        assert res3["verification_result"]["verification_status"] == "pending"

    # 4. failure -> failed
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_exec:
        from backend.execution.schemas import ExecutionResult
        mock_exec.return_value = ExecutionResult(
            execution_id="4", action="retry_now", status="failed", provider="sim", amount=100, success=False
        )
        mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
            selected_action="retry_now", reason="", confidence=0.9
        ))
        res4 = process_failed_payment(get_base_record(), ExecutionState(event_id="v4"))
        assert res4["verification_result"]["verification_status"] == "failed"

@patch("backend.agent.orchestrator.get_llm_provider")
def test_13_end_to_end_audit_record(mock_provider):
    from backend.agent.schemas import AgentDecision
    from backend.agent.provider import FakeLLMProvider
    mock_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="audit testing", confidence=0.99
    ))
    
    res = process_failed_payment(get_base_record(), ExecutionState(event_id="e13"))
    
    assert "recovery_analysis" in res
    assert "agent_decision" in res
    assert "policy_decision" in res
    assert "execution_result" in res
    assert "verification_result" in res
    
    # Audit chain holds true
    assert res["policy_decision"]["action"] == res["agent_decision"]["selected_action"]
    assert res["execution_result"]["action"] == res["policy_decision"]["action"]
    assert res["verification_result"]["action"] == res["execution_result"]["action"]
