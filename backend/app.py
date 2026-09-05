"""RecoverAI — FastAPI Application Entry Point."""
import os
import uuid
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db, save_recovery_record, get_recovery_records, get_recovery_record_by_payment_id
from backend.api_schemas import (
    PaymentRequest, AnalyzeResponse, ExecuteResponse,
    CandidateActionResponse, AgentDecisionResponse, PolicyDecisionResponse,
    ExecutionResultResponse, VerificationResultResponse,
    RecoveryRecordSummary, RecoveryRecordDetail
)
from backend.demos import DEMO_SCENARIOS, get_scenario_names, get_scenario
from backend.agent.orchestrator import process_failed_payment
from backend.recovery.schemas import PaymentContext
from backend.recovery.engine import analyze_recovery
from backend.agent.schemas import AgentContext, CandidateInfo
from backend.agent.agent import RecoveryDecisionAgent
from backend.agent.provider import get_llm_provider
from backend.policy.schemas import ExecutionState, PolicyConfig
from backend.policy.engine import evaluate_policy

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    settings = get_settings()
    init_db(settings.DATABASE_PATH)
    yield

app = FastAPI(
    title="RecoverAI",
    description="Bounded AI Revenue Recovery for Failed Subscription Payments",
    version="0.5.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "recoverAI",
        "execution_mode": settings.EXECUTION_MODE,
        "llm_provider": settings.LLM_PROVIDER
    }


# ─── Analyze (recommendation only, NO execution) ─────────────────────────────
@app.post("/api/v1/recoveries/analyze", response_model=AnalyzeResponse)
def analyze_recovery_endpoint(req: PaymentRequest):
    """Run recovery analysis + LLM recommendation + policy decision.
    Does NOT execute the selected action."""
    
    # Build PaymentContext (ground_truth_outcome deliberately excluded)
    recovery_context = PaymentContext(
        amount=req.amount,
        failure_type=req.failure_type,
        retry_count=req.retry_count,
        customer_tenure_months=req.customer_tenure_months,
        previous_successes=req.previous_successes,
        previous_failures=req.previous_failures,
        customer_message=req.customer_message,
        support_note=req.support_note
    )
    
    # Deterministic recovery analysis
    recovery_result = analyze_recovery(recovery_context)
    
    if not recovery_result.candidates:
        return AnalyzeResponse(
            payment_id=req.payment_id,
            customer_id=req.customer_id,
            amount=req.amount,
            failure_type=req.failure_type,
            recovery_opportunity_score=recovery_result.opportunity_score,
            candidate_actions=[],
            agent_decision=AgentDecisionResponse(
                selected_action=None, reason="No candidates available", status="unavailable"
            ),
            policy_decision=PolicyDecisionResponse(
                allowed=False, action="stop", reason="No candidates generated",
                violations=["No candidates generated"], requires_escalation=True
            )
        )
    
    # Build agent context
    agent_context = AgentContext(
        amount=recovery_context.amount,
        failure_type=recovery_context.failure_type,
        retry_count=recovery_context.retry_count,
        customer_tenure_months=recovery_context.customer_tenure_months,
        previous_successes=recovery_context.previous_successes,
        previous_failures=recovery_context.previous_failures,
        days_since_last_success=req.days_since_last_success,
        subscription_value=req.subscription_value,
        recovery_opportunity_score=recovery_result.opportunity_score,
        customer_message=recovery_context.customer_message,
        support_note=recovery_context.support_note,
        merchant_note=req.merchant_note,
        candidates=[
            CandidateInfo(action=c.action_type, ev=c.ev, timing=c.timing)
            for c in recovery_result.candidates
        ]
    )
    
    # LLM recommendation
    provider = get_llm_provider()
    agent = RecoveryDecisionAgent(provider=provider)
    agent_decision = agent.decide(agent_context)
    
    # Confidence fallback
    threshold = float(os.environ.get("LLM_CONFIDENCE_THRESHOLD", "0.70"))
    proposed_action = agent_decision.selected_action
    
    if agent_decision.status != "success" or not proposed_action:
        proposed_action = "escalate"
    elif agent_decision.confidence < threshold:
        if "escalate" in {c.action for c in agent_context.candidates}:
            proposed_action = "escalate"
    
    # Policy evaluation
    event_id = f"analyze_{uuid.uuid4().hex[:8]}"
    execution_state = ExecutionState(event_id=event_id)
    policy_decision = evaluate_policy(
        context=recovery_context,
        proposed_action=proposed_action,
        execution_state=execution_state
    )
    
    if agent_decision.status != "success":
        policy_decision.allowed = False
        policy_decision.requires_escalation = True
        policy_decision.reason = "Agent unavailable or failed"
    
    return AnalyzeResponse(
        payment_id=req.payment_id,
        customer_id=req.customer_id,
        amount=req.amount,
        failure_type=req.failure_type,
        recovery_opportunity_score=recovery_result.opportunity_score,
        candidate_actions=[
            CandidateActionResponse(action=c.action_type, ev=c.ev, timing=c.timing)
            for c in recovery_result.candidates
        ],
        agent_decision=AgentDecisionResponse(
            selected_action=agent_decision.selected_action,
            reason=agent_decision.reason,
            confidence=agent_decision.confidence,
            status=agent_decision.status
        ),
        policy_decision=PolicyDecisionResponse(
            allowed=policy_decision.allowed,
            action=policy_decision.action,
            reason=policy_decision.reason,
            violations=policy_decision.violations,
            requires_escalation=policy_decision.requires_escalation,
            policy_version=policy_decision.policy_version
        )
    )


# ─── Execute (full pipeline including execution + verification) ───────────────
@app.post("/api/v1/recoveries/execute", response_model=ExecuteResponse)
def execute_recovery_endpoint(req: PaymentRequest):
    """Run the full recovery pipeline: analysis → LLM → policy → execution → verification.
    Persists the result for audit."""
    
    settings = get_settings()
    
    # Validate Razorpay mode if selected
    if settings.EXECUTION_MODE == "razorpay_test" and not settings.validate_razorpay():
        raise HTTPException(
            status_code=503,
            detail="Razorpay Test Mode selected but credentials are not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET or use EXECUTION_MODE=simulator."
        )
    
    # Build record dict for the existing orchestrator
    record = {
        "payment_id": req.payment_id,
        "customer_id": req.customer_id,
        "subscription_id": req.subscription_id,
        "amount": req.amount,
        "failure_type": req.failure_type,
        "retry_count": req.retry_count,
        "customer_tenure_months": req.customer_tenure_months,
        "previous_successes": req.previous_successes,
        "previous_failures": req.previous_failures,
        "customer_message": req.customer_message,
        "support_note": req.support_note,
        "merchant_note": req.merchant_note,
        "days_since_last_success": req.days_since_last_success,
        "subscription_value": req.subscription_value,
    }
    
    event_id = f"exec_{uuid.uuid4().hex[:8]}"
    execution_state = ExecutionState(event_id=event_id)
    
    # Call existing orchestrator (reuses all existing logic)
    result = process_failed_payment(record, execution_state)
    
    # Inject context for frontend display without altering DB schema
    result["context"] = record
    
    # Persist for audit
    save_recovery_record(
        payment_id=req.payment_id,
        customer_id=req.customer_id,
        amount=req.amount,
        failure_type=req.failure_type,
        result=result,
        db_path=settings.DATABASE_PATH
    )
    
    # Build response
    recovery = result.get("recovery_analysis", {})
    agent = result.get("agent_decision", {})
    policy = result.get("policy_decision", {})
    execution = result.get("execution_result", {})
    verification = result.get("verification_result", {})
    
    return ExecuteResponse(
        payment_id=req.payment_id,
        customer_id=req.customer_id,
        amount=req.amount,
        failure_type=req.failure_type,
        recovery_opportunity_score=recovery.get("opportunity_score", 0),
        candidate_actions=[
            CandidateActionResponse(action=c["action_type"], ev=c["ev"], timing=c["timing"])
            for c in recovery.get("candidates", [])
        ],
        agent_decision=AgentDecisionResponse(
            selected_action=agent.get("selected_action"),
            reason=agent.get("reason", ""),
            confidence=agent.get("confidence", 0.0),
            status=agent.get("status", "success")
        ),
        policy_decision=PolicyDecisionResponse(
            allowed=policy.get("allowed", False),
            action=policy.get("action", ""),
            reason=policy.get("reason", ""),
            violations=policy.get("violations", []),
            requires_escalation=policy.get("requires_escalation", False),
            policy_version=policy.get("policy_version", "v1")
        ),
        execution_result=ExecutionResultResponse(**execution) if execution else ExecutionResultResponse(),
        verification_result=VerificationResultResponse(**verification) if verification else VerificationResultResponse()
    )


# ─── Recovery Records ────────────────────────────────────────────────────────
@app.get("/api/v1/recoveries", response_model=List[RecoveryRecordSummary])
def list_recoveries(limit: int = 50):
    """List recent recovery records."""
    settings = get_settings()
    rows = get_recovery_records(limit=limit, db_path=settings.DATABASE_PATH)
    results = []
    for r in rows:
        results.append(RecoveryRecordSummary(
            id=r["id"],
            payment_id=r["payment_id"],
            customer_id=r.get("customer_id"),
            amount=r.get("amount"),
            failure_type=r.get("failure_type"),
            opportunity_score=r.get("opportunity_score"),
            selected_action=r.get("selected_action"),
            policy_allowed=bool(r.get("policy_allowed")) if r.get("policy_allowed") is not None else None,
            policy_reason=r.get("policy_reason"),
            execution_status=r.get("execution_status"),
            execution_provider=r.get("execution_provider"),
            verification_status=r.get("verification_status"),
            recovered_amount=r.get("recovered_amount"),
            created_at=r.get("created_at", "")
        ))
    return results

@app.get("/api/v1/recoveries/{payment_id}", response_model=RecoveryRecordDetail)
def get_recovery(payment_id: str):
    """Get the detailed recovery record for a specific payment."""
    settings = get_settings()
    record = get_recovery_record_by_payment_id(payment_id, db_path=settings.DATABASE_PATH)
    if not record:
        raise HTTPException(status_code=404, detail=f"No recovery record found for payment_id={payment_id}")
    
    return RecoveryRecordDetail(
        id=record["id"],
        payment_id=record["payment_id"],
        customer_id=record.get("customer_id"),
        amount=record.get("amount"),
        failure_type=record.get("failure_type"),
        opportunity_score=record.get("opportunity_score"),
        selected_action=record.get("selected_action"),
        agent_reason=record.get("agent_reason"),
        agent_confidence=record.get("agent_confidence"),
        policy_allowed=bool(record.get("policy_allowed")) if record.get("policy_allowed") is not None else None,
        policy_reason=record.get("policy_reason"),
        requires_escalation=bool(record.get("requires_escalation")) if record.get("requires_escalation") is not None else None,
        execution_status=record.get("execution_status"),
        execution_provider=record.get("execution_provider"),
        execution_provider_reference=record.get("execution_provider_reference"),
        verification_status=record.get("verification_status"),
        recovered_amount=record.get("recovered_amount"),
        full_result=record.get("full_result"),
        created_at=record.get("created_at", "")
    )


# ─── Demo Scenarios ──────────────────────────────────────────────────────────
@app.get("/api/v1/demos")
def list_demos():
    """List available demo scenarios."""
    return {
        name: {"name": s["name"], "description": s["description"]}
        for name, s in DEMO_SCENARIOS.items()
    }

@app.post("/api/v1/demos/{scenario_name}/execute", response_model=ExecuteResponse)
def run_demo_scenario(scenario_name: str):
    """Execute a predefined demo scenario through the full pipeline."""
    scenario = get_scenario(scenario_name)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Unknown demo scenario: {scenario_name}")
    
    req = PaymentRequest(**scenario["request"])
    return execute_recovery_endpoint(req)
