import json
import random
from typing import List, Dict, Any
from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import analyze_recovery

def load_dataset(filepath: str) -> Dict[str, Any]:
    with open(filepath, "r") as f:
        return json.load(f)

def simulate_outcome(action: str, record: Dict[str, Any]) -> bool:
    """
    Pseudo-probabilistic outcome simulator for synthetic evaluation.
    These probabilities are part of the synthetic environment, NOT learned from data,
    and NOT an ML prediction model. This measures behavior strictly inside this controlled environment.
    """
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

def evaluate_strategy(strategy_func, dataset_dict: Dict[str, Any]) -> Dict[str, float]:
    dataset = dataset_dict["records"]
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
    escalations = 0
    stopped_cases = 0
    unnecessary_interventions = 0
    
    for record in dataset:
        action = strategy_func(record)
        total_revenue_at_risk += record["amount"]
        total_cost += costs.get(action, 0.0)
        
        if action == "escalate":
            escalations += 1
        elif action == "stop":
            stopped_cases += 1
            
        success = simulate_outcome(action, record)
        if success:
            recovered_revenue += record["amount"]
            successful_recoveries += 1
        else:
            if action not in ["escalate", "stop"]:
                unnecessary_interventions += 1
            
    return {
        "number_of_cases": total_cases,
        "revenue_at_risk": round(total_revenue_at_risk, 2),
        "recovered_revenue": round(recovered_revenue, 2),
        "net_recovered_revenue": round(recovered_revenue - total_cost, 2),
        "recovery_rate": round(successful_recoveries / total_cases if total_cases > 0 else 0, 2),
        "successful_recoveries": successful_recoveries,
        "total_cost": round(total_cost, 2),
        "unnecessary_interventions": unnecessary_interventions,
        "escalations": escalations,
        "stopped_cases": stopped_cases
    }

def run_evaluation():
    datasets = {
        "Development": load_dataset("data/dev.json"),
        "Held-out Test": load_dataset("data/test.json"),
        "Stress Test": load_dataset("data/stress.json")
    }
    
    def recover_ai_strategy(record: Dict[str, Any]) -> str:
        # Note: ground_truth_outcome is NEVER passed into the engine
        context = PaymentContext(
            amount=record["amount"],
            failure_type=record["failure_type"],
            retry_count=record["retry_count"],
            customer_tenure_months=record["customer_tenure_months"],
            previous_successes=record["previous_successes"],
            previous_failures=record["previous_failures"],
            customer_message=record.get("customer_message"),
            support_note=record.get("support_note")
        )
        res = analyze_recovery(context)
        return res.candidates[0].action_type
        
    for name, data in datasets.items():
        print(f"\n==================================================")
        print(f"REGIME: {name.upper()}")
        print(f"==================================================")
        metadata = data.get("metadata", {})
        print(f"Metadata: Seed={metadata.get('seed')}, Records={metadata.get('num_records')}\n")
        
        random.seed(metadata.get("seed", 42))
        print("--- Baseline 1: Naive ---")
        metrics_naive = evaluate_strategy(naive_baseline, data)
        print(json.dumps(metrics_naive, indent=2))
        
        random.seed(metadata.get("seed", 42))
        print("\n--- Baseline 2: Rule-Based ---")
        metrics_rules = evaluate_strategy(rule_based_baseline, data)
        print(json.dumps(metrics_rules, indent=2))
        
        random.seed(metadata.get("seed", 42))
        print("\n--- RecoverAI Top-EV MVP (LLM stand-in) ---")
        metrics_ai = evaluate_strategy(recover_ai_strategy, data)
        print(json.dumps(metrics_ai, indent=2))

if __name__ == "__main__":
    run_evaluation()
