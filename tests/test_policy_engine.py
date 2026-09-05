import pytest
from backend.recovery.schemas import PaymentContext
from backend.policy.schemas import PolicyConfig, ExecutionState
from backend.policy.engine import evaluate_policy

def get_base_context(amount=1000.0, retry_count=0, failure_type="insufficient_funds") -> PaymentContext:
    return PaymentContext(
        amount=amount,
        failure_type=failure_type,
        retry_count=retry_count,
        customer_tenure_months=12,
        previous_successes=5,
        previous_failures=0
    )

def get_base_state(event_id="evt_123") -> ExecutionState:
    return ExecutionState(event_id=event_id)

def test_1_allow_retry():
    ctx = get_base_context(retry_count=0)
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is True
    assert decision.requires_escalation is False

def test_2_block_max_retries():
    ctx = get_base_context(retry_count=2)
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Maximum retry limit reached" in decision.violations

def test_3_block_max_retries_later():
    ctx = get_base_context(retry_count=2)
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_later", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Maximum retry limit reached" in decision.violations

def test_4_block_permanent_failure():
    ctx = get_base_context(failure_type="permanent_decline")
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Failure type is non-retryable" in decision.violations

def test_5_block_successful_payment():
    ctx = get_base_context()
    state = get_base_state()
    state.is_already_successful = True
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Payment already successful" in decision.violations

def test_6_allow_under_amount_limit():
    ctx = get_base_context(amount=9999.0)
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is True

def test_7_block_over_amount_limit():
    ctx = get_base_context(amount=10001.0)
    state = get_base_state()
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Amount exceeds autonomous execution limit" in decision.violations

def test_8_block_duplicate_event():
    ctx = get_base_context()
    state = get_base_state(event_id="evt_123")
    state.previously_executed_events = ["evt_123"]
    decision = evaluate_policy(ctx, "retry_now", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Duplicate recovery event/action" in decision.violations

def test_9_block_unsupported_action():
    ctx = get_base_context()
    state = get_base_state()
    decision = evaluate_policy(ctx, "charge_customer_again", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Unsupported recovery action" in decision.violations

def test_10_block_max_customer_contacts():
    ctx = get_base_context()
    state = get_base_state()
    state.customer_contacts_count = 2
    decision = evaluate_policy(ctx, "payment_link", state)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Maximum customer contacts reached" in decision.violations

def test_11_fail_closed_on_invalid_input():
    # Pass None as context which will cause an AttributeError inside evaluate_policy
    state = get_base_state()
    decision = evaluate_policy(None, "retry_now", state) # type: ignore
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Internal policy evaluation error" == decision.reason

def test_12_config_override():
    ctx = get_base_context(retry_count=1)
    state = get_base_state()
    config = PolicyConfig(max_retries=1)
    decision = evaluate_policy(ctx, "retry_now", state, config=config)
    assert decision.allowed is False
    assert decision.requires_escalation is True
    assert "Maximum retry limit reached" in decision.violations

def test_safety_llm_recommendation_does_not_equal_authorization():
    """
    Test proving 'LLM recommendation does not equal authorization'.
    Simulates a future LLM output that recommends 'retry_now' despite limits.
    """
    proposed_action = "retry_now"
    ctx = get_base_context(retry_count=2)
    state = get_base_state()
    
    # Policy enforces the block
    decision = evaluate_policy(ctx, proposed_action, state)
    
    assert decision.action == "retry_now"
    assert decision.allowed is False
    assert decision.requires_escalation is True

def test_deterministic_evaluation():
    ctx = get_base_context(amount=5000.0)
    state = get_base_state()
    config = PolicyConfig()
    
    decision1 = evaluate_policy(ctx, "retry_now", state, config)
    decision2 = evaluate_policy(ctx, "retry_now", state, config)
    
    assert decision1.allowed == decision2.allowed
    assert decision1.violations == decision2.violations
    assert decision1.reason == decision2.reason
