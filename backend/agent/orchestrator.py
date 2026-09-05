import os
import uuid
from typing import Dict, Any
from datetime import datetime, timezone

from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import analyze_recovery
from backend.policy.schemas import ExecutionState, PolicyConfig
from backend.policy.engine import evaluate_policy
from backend.execution.schemas import ExecutionResult
from backend.verification.verifier import verify_execution

from .schemas import AgentContext, CandidateInfo
from .agent import RecoveryDecisionAgent
from .provider import get_llm_provider

def process_failed_payment(
    record: Dict[str, Any], 
    execution_state: ExecutionState, 
    policy_config: PolicyConfig = PolicyConfig()
) -> Dict[str, Any]:
    
    # 1. Build deterministic recovery context
    # Note: ground_truth_outcome is deliberately excluded to prevent leakage.
    recovery_context = PaymentContext(
        amount=record["amount"],
        failure_type=record["failure_type"],
        retry_count=record["retry_count"],
        customer_tenure_months=record["customer_tenure_months"],
        previous_successes=record["previous_successes"],
        previous_failures=record["previous_failures"],
        customer_message=record.get("customer_message"),
        support_note=record.get("support_note")
    )
    
    # 2. Run deterministic recovery analysis (Opportunity Score, Candidates, EV, Timing)
    recovery_result = analyze_recovery(recovery_context)
    
    # Check if there are no candidates
    if not recovery_result.candidates:
        return {
            "recovery_analysis": recovery_result.model_dump(),
            "agent_decision": {
                "selected_action": "stop",
                "reason": "No candidates available",
                "status": "unavailable"
            },
            "policy_decision": {
                "allowed": False,
                "action": "stop",
                "reason": "No candidates generated",
                "violations": ["No candidates generated"],
                "requires_escalation": True,
                "policy_version": policy_config.policy_version
            }
        }
    
    # 3. Build Agent Context
    agent_context = AgentContext(
        amount=recovery_context.amount,
        failure_type=recovery_context.failure_type,
        retry_count=recovery_context.retry_count,
        customer_tenure_months=recovery_context.customer_tenure_months,
        previous_successes=recovery_context.previous_successes,
        previous_failures=recovery_context.previous_failures,
        days_since_last_success=record.get("days_since_last_success", 0),
        subscription_value=record.get("subscription_value", 0.0),
        recovery_opportunity_score=recovery_result.opportunity_score,
        customer_message=recovery_context.customer_message,
        support_note=recovery_context.support_note,
        merchant_note=record.get("merchant_note"),
        candidates=[
            CandidateInfo(action=c.action_type, ev=c.ev, timing=c.timing)
            for c in recovery_result.candidates
        ]
    )
    
    # 4. LLM Recommendation
    provider = get_llm_provider()
    agent = RecoveryDecisionAgent(provider=provider)
    agent_decision = agent.decide(agent_context)
    
    # Fallback / Confidence checking
    threshold = float(os.environ.get("LLM_CONFIDENCE_THRESHOLD", "0.70"))
    proposed_action = agent_decision.selected_action
    
    if agent_decision.status != "success" or not proposed_action:
        # Fallback to safe failure requiring escalation
        proposed_action = "escalate" # Use a dummy safe action for policy if it failed
        
    elif agent_decision.confidence < threshold:
        # Low confidence -> prefer escalation if it's a candidate, otherwise let policy handle it
        if "escalate" in {c.action for c in agent_context.candidates}:
            proposed_action = "escalate"
            
    # 5. Deterministic Policy Engine (Authorization Boundary)
    policy_decision = evaluate_policy(
        context=recovery_context,
        proposed_action=proposed_action,
        execution_state=execution_state,
        config=policy_config
    )
    
    # If the agent failed, explicitly set requires_escalation=True to override
    if agent_decision.status != "success":
        policy_decision.allowed = False
        policy_decision.requires_escalation = True
        policy_decision.reason = "Agent unavailable or failed"
    
    # 6. Controlled Execution Layer
    # Safety invariant: if policy is blocked, NEVER execute.
    if policy_decision.allowed:
        adapter_mode = os.environ.get("EXECUTION_MODE", "simulator").lower()
        if adapter_mode == "razorpay_test":
            from backend.razorpay.adapter import RazorpayExecutionAdapter
            adapter = RazorpayExecutionAdapter()
        else:
            from backend.execution.adapter import SimulatorExecutionAdapter
            adapter = SimulatorExecutionAdapter()
            
        execution_result_obj = adapter.execute(
            action=policy_decision.action,
            payment_context=recovery_context,
            event_id=execution_state.event_id
        )
    else:
        # Policy is blocked -> record non-execution
        execution_result_obj = ExecutionResult(
            execution_id=f"exec_blocked_{uuid.uuid4().hex[:8]}",
            action=policy_decision.action,
            status="blocked",
            provider="none",
            attempted_at=datetime.now(timezone.utc).isoformat(),
            amount=recovery_context.amount,
            success=False,
            message=policy_decision.reason
        )
        
    # 7. Verification Layer
    verification_result_obj = verify_execution(execution_result_obj, record["payment_id"])
    
    # Return structured separation for audit trail
    return {
        "recovery_analysis": recovery_result.model_dump(),
        "agent_decision": agent_decision.model_dump(),
        "policy_decision": policy_decision.model_dump(),
        "execution_result": execution_result_obj.model_dump(),
        "verification_result": verification_result_obj.model_dump()
    }
