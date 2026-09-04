from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import (
    calculate_opportunity_score,
    generate_candidates,
    calculate_ev,
    determine_timing,
    analyze_recovery
)
import pytest

def test_opportunity_score_bounds():
    # Test upper bound (100)
    ctx_high = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=100,
        previous_successes=100,
        previous_failures=0
    )
    score_high = calculate_opportunity_score(ctx_high)
    assert score_high == 100

    # Test lower bound (0)
    ctx_low = PaymentContext(
        amount=1000.0,
        failure_type="permanent_decline",
        retry_count=10,
        customer_tenure_months=0,
        previous_successes=0,
        previous_failures=100
    )
    score_low = calculate_opportunity_score(ctx_low)
    assert score_low == 0

def test_permanent_decline_candidates():
    ctx = PaymentContext(
        amount=5000.0,
        failure_type="permanent_decline",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0
    )
    candidates = generate_candidates(ctx)
    action_types = [c.action_type for c in candidates]
    assert "stop" in action_types
    assert "escalate" in action_types
    assert "retry_now" not in action_types
    assert "retry_later" not in action_types

def test_valid_retryable_candidates():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0
    )
    candidates = generate_candidates(ctx)
    action_types = [c.action_type for c in candidates]
    assert "retry_now" in action_types
    assert "retry_later" in action_types
    assert "payment_link" in action_types

def test_ev_calculation_deterministic():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=1,
        previous_successes=0,
        previous_failures=0
    )
    ev1 = calculate_ev("retry_now", ctx)
    ev2 = calculate_ev("retry_now", ctx)
    assert ev1 == ev2
    assert ev1 == (0.8 * 1000.0) - 5.0

def test_candidate_ordering():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="insufficient_funds",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0
    )
    candidates = generate_candidates(ctx)
    # Order should be descending by EV
    for i in range(len(candidates) - 1):
        assert candidates[i].ev >= candidates[i+1].ev

def test_timing_heuristic():
    assert determine_timing("retry_later", "insufficient_funds") == "48h"
    assert determine_timing("retry_later", "temporary_bank_failure") == "2h"
    assert determine_timing("retry_now", "insufficient_funds") == "now"

def test_ground_truth_leakage_prevented():
    # Attempting to pass ground_truth_outcome to PaymentContext should raise ValidationError
    with pytest.raises(ValueError):
        PaymentContext(
            amount=1000.0,
            failure_type="temporary_bank_failure",
            retry_count=0,
            customer_tenure_months=12,
            previous_successes=10,
            previous_failures=0,
            ground_truth_outcome="recovered" # This field doesn't exist in schema
        )

def test_missing_and_noisy_context_safety():
    # Missing optional fields should work
    ctx_missing = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0
    )
    res_missing = analyze_recovery(ctx_missing)
    assert len(res_missing.candidates) > 0

    # Noisy/unknown fields should work as long as they are strings
    ctx_noisy = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0,
        customer_message="SOME BIZARRE GARBAGE!@#$%",
        support_note="UNKNOWN_CODE_999"
    )
    res_noisy = analyze_recovery(ctx_noisy)
    assert len(res_noisy.candidates) > 0

def test_retry_count_limits_handled():
    # While policy engine handles the strict block, score should be impacted severely
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=10, # Way above normal limit
        customer_tenure_months=1,
        previous_successes=0,
        previous_failures=0
    )
    score = calculate_opportunity_score(ctx)
    # Base 50 + 2 + 0 - 100 + 20 = -28, capped to 0
    assert score == 0

def test_unknown_failure_type_safe_fallback():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="unknown_weird_error_500",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0
    )
    candidates = generate_candidates(ctx)
    action_types = [c.action_type for c in candidates]
    # Default fallback generates: ["retry_later", "payment_link", "escalate", "stop"]
    # It safely provides escalation and stop, and doesn't invent new ones.
    assert "stop" in action_types
    assert "escalate" in action_types
    assert "retry_now" not in action_types
