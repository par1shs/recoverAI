from typing import List
from .schemas import PaymentContext, CandidateAction, RecoveryAnalysisResult

def calculate_opportunity_score(context: PaymentContext) -> int:
    score = 50
    
    # Tenure
    score += min(20, context.customer_tenure_months * 2)
    
    # Success history
    score += min(20, context.previous_successes * 2)
    
    # Retry penalty
    score -= (context.retry_count * 10)
    
    # Failure type heuristics
    if context.failure_type == "permanent_decline":
        score -= 50
    elif context.failure_type == "expired_card":
        score -= 10
    elif context.failure_type == "insufficient_funds":
        score += 10
    elif context.failure_type == "temporary_bank_failure":
        score += 20
        
    return max(0, min(100, score))

def determine_timing(action_type: str, failure_type: str) -> str:
    if action_type == "retry_later":
        if failure_type == "insufficient_funds":
            return "48h"
        elif failure_type == "temporary_bank_failure":
            return "2h"
        return "24h"
    return "now"

def calculate_ev(action_type: str, context: PaymentContext) -> float:
    base_probs = {
        "retry_now": {"temporary_bank_failure": 0.8, "insufficient_funds": 0.1, "default": 0.0},
        "retry_later": {"temporary_bank_failure": 0.6, "insufficient_funds": 0.5, "default": 0.2},
        "payment_link": {"default": 0.4},
        "escalate": {"default": 0.2},
        "stop": {"default": 0.0}
    }
    
    # Get probability
    prob_map = base_probs.get(action_type, {})
    prob = prob_map.get(context.failure_type, prob_map.get("default", 0.0))
    
    expected_recovered = context.amount * prob
    
    costs = {
        "retry_now": 5.0,
        "retry_later": 5.0,
        "payment_link": 2.0,
        "escalate": 100.0,
        "stop": 0.0
    }
    action_cost = costs.get(action_type, 0.0)
    
    return round(expected_recovered - action_cost, 2)

def generate_candidates(context: PaymentContext) -> List[CandidateAction]:
    candidates = []
    
    if context.failure_type == "permanent_decline":
        possible_actions = ["stop", "escalate"]
    elif context.failure_type == "expired_card":
        possible_actions = ["payment_link", "escalate"]
    elif context.failure_type == "insufficient_funds":
        possible_actions = ["retry_later", "payment_link", "escalate"]
    elif context.failure_type == "temporary_bank_failure":
        possible_actions = ["retry_now", "retry_later", "payment_link"]
    else:
        possible_actions = ["retry_later", "payment_link", "escalate", "stop"]
        
    for act in possible_actions:
        candidates.append(CandidateAction(
            action_type=act,
            ev=calculate_ev(act, context),
            timing=determine_timing(act, context.failure_type)
        ))
        
    # Sort candidates by EV descending
    candidates.sort(key=lambda x: x.ev, reverse=True)
    return candidates

def analyze_recovery(context: PaymentContext) -> RecoveryAnalysisResult:
    return RecoveryAnalysisResult(
        opportunity_score=calculate_opportunity_score(context),
        candidates=generate_candidates(context)
    )
