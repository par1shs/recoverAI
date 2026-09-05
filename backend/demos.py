"""RecoverAI — Demo Scenarios for Hackathon Demonstration."""
from typing import Dict, Any, List

DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "insufficient_funds": {
        "name": "Scenario A — Insufficient Funds",
        "description": "Customer cannot pay today but asks to keep their subscription.",
        "request": {
            "payment_id": "pay_demo_insuf_001",
            "customer_id": "cust_demo_001",
            "subscription_id": "sub_demo_001",
            "amount": 999.0,
            "failure_type": "insufficient_funds",
            "retry_count": 0,
            "customer_tenure_months": 18,
            "previous_successes": 15,
            "previous_failures": 1,
            "customer_message": "I get paid tomorrow. Please don't cancel my subscription.",
            "days_since_last_success": 30,
            "subscription_value": 999.0
        }
    },
    "retry_limit_reached": {
        "name": "Scenario B — Retry Limit Reached (Safety Demo)",
        "description": "LLM may want to retry, but Policy Engine MUST block it.",
        "request": {
            "payment_id": "pay_demo_retry_limit_001",
            "customer_id": "cust_demo_002",
            "subscription_id": "sub_demo_002",
            "amount": 499.0,
            "failure_type": "temporary_bank_failure",
            "retry_count": 3,
            "customer_tenure_months": 6,
            "previous_successes": 5,
            "previous_failures": 3,
            "days_since_last_success": 7,
            "subscription_value": 499.0
        }
    },
    "expired_card": {
        "name": "Scenario C — Expired Card",
        "description": "Card is expired; payment-link/update action is more appropriate than retry.",
        "request": {
            "payment_id": "pay_demo_expired_001",
            "customer_id": "cust_demo_003",
            "subscription_id": "sub_demo_003",
            "amount": 1499.0,
            "failure_type": "expired_card",
            "retry_count": 0,
            "customer_tenure_months": 24,
            "previous_successes": 23,
            "previous_failures": 0,
            "support_note": "Loyal customer, card recently expired. Sent email.",
            "days_since_last_success": 31,
            "subscription_value": 1499.0
        }
    },
    "permanent_failure": {
        "name": "Scenario D — Permanent Failure",
        "description": "Permanent decline — retry actions unavailable, case is stopped/escalated.",
        "request": {
            "payment_id": "pay_demo_perm_001",
            "customer_id": "cust_demo_004",
            "subscription_id": "sub_demo_004",
            "amount": 2999.0,
            "failure_type": "permanent_decline",
            "retry_count": 0,
            "customer_tenure_months": 3,
            "previous_successes": 2,
            "previous_failures": 1,
            "days_since_last_success": 60,
            "subscription_value": 2999.0
        }
    }
}

def get_scenario_names() -> List[str]:
    return list(DEMO_SCENARIOS.keys())

def get_scenario(name: str) -> Dict[str, Any]:
    return DEMO_SCENARIOS.get(name, {})
