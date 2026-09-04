from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import (
    calculate_opportunity_score,
    generate_candidates,
    calculate_ev,
    analyze_recovery
)

def test_opportunity_score():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=24,
        previous_successes=20,
        previous_failures=0
    )
    score = calculate_opportunity_score(ctx)
    # Base 50 + 20 (tenure) + 20 (success) - 0 (retries) + 20 (temp failure) = 110, capped at 100
    assert score == 100

def test_permanent_decline_score():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="permanent_decline",
        retry_count=2,
        customer_tenure_months=1,
        previous_successes=0,
        previous_failures=0
    )
    score = calculate_opportunity_score(ctx)
    # Base 50 + 2 (tenure) + 0 (success) - 20 (retries) - 50 (perm) = -18, capped at 0
    assert score == 0

def test_generate_candidates_permanent():
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

def test_ev_calculation():
    ctx = PaymentContext(
        amount=1000.0,
        failure_type="temporary_bank_failure",
        retry_count=0,
        customer_tenure_months=1,
        previous_successes=0,
        previous_failures=0
    )
    # prob = 0.8, amount = 1000, cost = 5
    ev = calculate_ev("retry_now", ctx)
    assert ev == (0.8 * 1000.0) - 5.0
