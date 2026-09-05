import os
import pytest
from unittest.mock import patch

from backend.recovery.schemas import PaymentContext
from backend.policy.schemas import ExecutionState, PolicyConfig
from backend.agent.schemas import AgentContext, AgentDecision, CandidateInfo
from backend.agent.agent import RecoveryDecisionAgent
from backend.agent.provider import FakeLLMProvider
from backend.agent.orchestrator import process_failed_payment

def get_base_record(failure_type="insufficient_funds", customer_message=None):
    return {
        "payment_id": "pay_123",
        "customer_id": "cust_123",
        "subscription_id": "sub_123",
        "amount": 1000.0,
        "failure_type": failure_type,
        "retry_count": 0,
        "customer_tenure_months": 12,
        "previous_successes": 10,
        "previous_failures": 0,
        "days_since_last_success": 30,
        "subscription_value": 1000.0,
        "customer_message": customer_message,
        "support_note": None,
        "ground_truth_outcome": "recovered_after_delay" # This must NOT leak!
    }

def test_1_valid_candidate_selection():
    # LLM mock returns retry_later when supplied
    fake_provider = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later",
        reason="Good reason",
        confidence=0.9
    ))
    agent = RecoveryDecisionAgent(provider=fake_provider)
    
    ctx = AgentContext(
        amount=1000, failure_type="insufficient_funds", retry_count=0,
        customer_tenure_months=12, previous_successes=10, previous_failures=0,
        recovery_opportunity_score=80,
        candidates=[
            CandidateInfo(action="retry_now", ev=1000, timing="now"),
            CandidateInfo(action="retry_later", ev=1100, timing="24h")
        ]
    )
    
    decision = agent.decide(ctx)
    assert decision.selected_action == "retry_later"
    assert decision.status == "success"

def test_2_candidate_restriction():
    # LLM mock returns an action that wasn't supplied
    fake_provider = FakeLLMProvider(return_invalid_action=True)
    agent = RecoveryDecisionAgent(provider=fake_provider)
    
    ctx = AgentContext(
        amount=1000, failure_type="insufficient_funds", retry_count=0,
        customer_tenure_months=12, previous_successes=10, previous_failures=0,
        recovery_opportunity_score=80,
        candidates=[
            CandidateInfo(action="retry_now", ev=1000, timing="now"),
        ]
    )
    
    decision = agent.decide(ctx)
    assert decision.selected_action is None # Restricted
    assert decision.status == "unavailable" # Safe fallback
    assert "invalid action" in decision.reason.lower()

def test_3_malformed_response():
    fake_provider = FakeLLMProvider(return_malformed=True)
    agent = RecoveryDecisionAgent(provider=fake_provider)
    
    ctx = AgentContext(
        amount=1000, failure_type="insufficient_funds", retry_count=0,
        customer_tenure_months=12, previous_successes=10, previous_failures=0,
        recovery_opportunity_score=80,
        candidates=[CandidateInfo(action="retry_now", ev=1000, timing="now")]
    )
    
    decision = agent.decide(ctx)
    assert decision.selected_action is None
    assert decision.status == "unavailable"
    assert "failed" in decision.reason.lower()

def test_4_llm_unavailable():
    fake_provider = FakeLLMProvider(should_fail=True)
    agent = RecoveryDecisionAgent(provider=fake_provider)
    
    ctx = AgentContext(
        amount=1000, failure_type="insufficient_funds", retry_count=0,
        customer_tenure_months=12, previous_successes=10, previous_failures=0,
        recovery_opportunity_score=80,
        candidates=[CandidateInfo(action="retry_now", ev=1000, timing="now")]
    )
    
    decision = agent.decide(ctx)
    assert decision.selected_action is None
    assert decision.status == "unavailable"

def test_5_ground_truth_leakage():
    record = get_base_record()
    state = ExecutionState(event_id="evt_123")
    
    # We patch the agent deciding so we can inspect the context passed to it
    with patch("backend.agent.orchestrator.RecoveryDecisionAgent.decide") as mock_decide:
        mock_decide.return_value = AgentDecision(
            selected_action="retry_now",
            reason="Mocked",
            confidence=0.9
        )
        process_failed_payment(record, state)
        
        args, kwargs = mock_decide.call_args
        agent_ctx = args[0]
        
        # Verify ground_truth_outcome is NOT in the agent context
        assert not hasattr(agent_ctx, "ground_truth_outcome")
        # Ensure it doesn't accidentally end up in unstructured context
        assert agent_ctx.customer_message == record["customer_message"]
        assert agent_ctx.support_note == record["support_note"]
        # Double check pydantic model dump doesn't have it
        assert "ground_truth_outcome" not in agent_ctx.model_dump()

@patch("backend.agent.orchestrator.get_llm_provider")
def test_6_contextual_decision(mock_get_provider):
    msg = "I get my salary tomorrow. Please retry tomorrow."
    record = get_base_record(customer_message=msg)
    state = ExecutionState(event_id="evt_123")
    
    mock_get_provider.return_value = FakeLLMProvider(predefined_responses={
        msg: AgentDecision(selected_action="retry_later", reason="Salary tomorrow", confidence=0.9)
    })
    
    result = process_failed_payment(record, state)
    
    assert result["agent_decision"]["selected_action"] == "retry_later"
    assert result["policy_decision"]["allowed"] is True
    assert result["policy_decision"]["action"] == "retry_later"

@patch("backend.agent.orchestrator.get_llm_provider")
def test_7_policy_has_final_authority(mock_get_provider):
    # LLM recommends retry_now, but retry_count is at max limit
    record = get_base_record(failure_type="temporary_bank_failure")
    record["retry_count"] = 2
    state = ExecutionState(event_id="evt_123")
    
    # LLM recommends retry_now anyway
    mock_get_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_now", reason="Ignoring limits", confidence=0.9
    ))
    
    with patch("backend.execution.adapter.SimulatorExecutionAdapter.execute") as mock_execute:
        result = process_failed_payment(record, state)
    
    # LLM actually recommended retry_now
    assert result["agent_decision"]["selected_action"] == "retry_now"
    
    # But policy engine BLOCKS it
    assert result["policy_decision"]["allowed"] is False
    assert result["policy_decision"]["requires_escalation"] is True
    assert result["execution_result"]["status"] == "blocked"
    mock_execute.assert_not_called()

@patch("backend.agent.orchestrator.analyze_recovery")
def test_8_no_candidates(mock_analyze):
    # If deterministic recovery analysis returns no candidates
    from backend.recovery.schemas import RecoveryAnalysisResult
    mock_analyze.return_value = RecoveryAnalysisResult(opportunity_score=0, candidates=[])
    
    record = get_base_record()
    state = ExecutionState(event_id="evt_123")
    
    result = process_failed_payment(record, state)
    
    assert result["agent_decision"]["status"] == "unavailable"
    assert result["policy_decision"]["allowed"] is False
    assert result["policy_decision"]["requires_escalation"] is True

@patch("backend.agent.orchestrator.get_llm_provider")
def test_9_empty_context(mock_get_provider):
    # No customer message or support note
    record = get_base_record(customer_message=None)
    record["support_note"] = None
    state = ExecutionState(event_id="evt_123")
    
    mock_get_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="Default structural choice", confidence=0.8
    ))
    
    result = process_failed_payment(record, state)
    assert result["agent_decision"]["selected_action"] == "retry_later"

def test_10_deterministic_orchestration_boundary():
    record = get_base_record()
    state = ExecutionState(event_id="evt_123")
    
    with patch("backend.agent.orchestrator.get_llm_provider") as mock_get_provider:
        # Provide a mock that might try to mess things up internally, though our schema prevents it.
        # Mostly we just assert the EV before and after are identical by calling process_failed_payment twice
        # or checking the outputs.
        mock_get_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
            selected_action="retry_later", reason="Safe", confidence=0.9
        ))
        
        result1 = process_failed_payment(record, state)
        
        # EV calculations from recovery analysis should be unmodified
        cands1 = result1["recovery_analysis"]["candidates"]
        assert len(cands1) > 0
        
        # Re-run to ensure determinism and immutability
        result2 = process_failed_payment(record, state)
        cands2 = result2["recovery_analysis"]["candidates"]
        
        assert [c["ev"] for c in cands1] == [c["ev"] for c in cands2]

@patch("backend.agent.orchestrator.get_llm_provider")
def test_fallback_due_to_low_confidence(mock_get_provider):
    record = get_base_record()
    state = ExecutionState(event_id="evt_123")
    
    # Confidence is 0.1, lower than 0.70 threshold
    mock_get_provider.return_value = FakeLLMProvider(default_response=AgentDecision(
        selected_action="retry_later", reason="Not sure", confidence=0.1
    ))
    
    # We need a candidate list that includes 'escalate' to see the fallback
    result = process_failed_payment(record, state)
    
    # It should fall back to escalate
    assert result["agent_decision"]["selected_action"] == "retry_later"
    assert result["policy_decision"]["action"] == "escalate"
