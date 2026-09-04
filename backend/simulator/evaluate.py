import json
import random
from typing import List, Dict, Any
from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import analyze_recovery

def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r") as f:
        return json.load(f)

def simulate_outcome(action: str, record: Dict[str, Any]) -> bool:
    failure_type = record["failure_type"]
    base_probs = {
        "retry_now": {"temporary_bank_failure": 0.8, "insufficient_funds": 0.1, "default": 0.0},
        "retry_later": {"temporary_bank_failure": 0.6, "insufficient_funds": 0.5, "default": 0.2},
        "payment_link": {"default": 0.4},
        "escalate": {"default": 0.2},
        "stop": {"default": 0.0}
    }
    
    prob_map = base_probs.get(action, {})
    prob = prob_map.get(failure_type, prob_map.get("default", 0.0))
    
    return random.random() < prob

def naive_baseline(record: Dict[str, Any]) -> str:
    if record["failure_type"] == "permanent_decline":
        return "stop"
    return "retry_now"

def rule_based_baseline(record: Dict[str, Any]) -> str:
    ft = record["failure_type"]
    if ft == "permanent_decline":
        return "stop"
    elif ft == "expired_card":
        return "payment_link"
    elif ft == "insufficient_funds":
        return "retry_later"
    elif ft == "temporary_bank_failure":
        return "retry_now"
    return "escalate"

def evaluate_strategy(strategy_func, dataset: List[Dict[str, Any]]) -> Dict[str, float]:
    total_revenue_at_risk = 0.0
    recovered_revenue = 0.0
    successful_recoveries = 0
    total_cases = len(dataset)
    costs = {
        "retry_now": 5.0,
        "retry_later": 5.0,
        "payment_link": 2.0,
        "escalate": 100.0,
        "stop": 0.0
    }
    total_cost = 0.0
    
    for record in dataset:
        action = strategy_func(record)
        total_revenue_at_risk += record["amount"]
        total_cost += costs.get(action, 0.0)
        
        if simulate_outcome(action, record):
            recovered_revenue += record["amount"]
            successful_recoveries += 1
            
    return {
        "revenue_at_risk": total_revenue_at_risk,
        "recovered_revenue": recovered_revenue,
        "net_recovered": recovered_revenue - total_cost,
        "recovery_rate": successful_recoveries / total_cases if total_cases > 0 else 0,
        "successful_recoveries": successful_recoveries,
        "total_cost": total_cost
    }

def run_evaluation():
    random.seed(42)  # For reproducible evaluation
    dataset = load_dataset("data/test.json")
    print(f"Evaluating on {len(dataset)} records...")
    
    print("\n--- Baseline 1: Naive ---")
    metrics_naive = evaluate_strategy(naive_baseline, dataset)
    print(json.dumps(metrics_naive, indent=2))
    
    print("\n--- Baseline 2: Rule-Based ---")
    random.seed(42)
    metrics_rules = evaluate_strategy(rule_based_baseline, dataset)
    print(json.dumps(metrics_rules, indent=2))
    
    print("\n--- RecoverAI (Top-EV MVP) ---")
    def recover_ai_strategy(record: Dict[str, Any]) -> str:
        context = PaymentContext(
            amount=record["amount"],
            failure_type=record["failure_type"],
            retry_count=record["retry_count"],
            customer_tenure_months=record["customer_tenure_months"],
            previous_successes=record["previous_successes"],
            previous_failures=record["previous_failures"]
        )
        res = analyze_recovery(context)
        # Choose candidate with highest EV
        return res.candidates[0].action_type
        
    random.seed(42)
    metrics_ai = evaluate_strategy(recover_ai_strategy, dataset)
    print(json.dumps(metrics_ai, indent=2))

if __name__ == "__main__":
    run_evaluation()
