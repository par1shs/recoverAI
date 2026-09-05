from datetime import datetime, timezone
from backend.execution.schemas import ExecutionResult
from .schemas import RecoveryOutcome

def verify_execution(execution_result: ExecutionResult, payment_id: str) -> RecoveryOutcome:
    now = datetime.now(timezone.utc).isoformat()
    
    if execution_result.status in ["escalated", "stopped", "blocked"]:
        return RecoveryOutcome(
            payment_id=payment_id,
            action=execution_result.action,
            verification_status="not_recovered",
            recovered_amount=0.0,
            provider=execution_result.provider,
            provider_reference=execution_result.provider_reference,
            verified_at=now,
            message=f"Action was {execution_result.status}"
        )
        
    if not execution_result.success or execution_result.status == "failed":
        return RecoveryOutcome(
            payment_id=payment_id,
            action=execution_result.action,
            verification_status="failed",
            recovered_amount=0.0,
            provider=execution_result.provider,
            provider_reference=execution_result.provider_reference,
            verified_at=now,
            message=execution_result.message or "Execution failed"
        )
        
    if execution_result.status == "scheduled":
        return RecoveryOutcome(
            payment_id=payment_id,
            action=execution_result.action,
            verification_status="pending",
            recovered_amount=0.0,
            provider=execution_result.provider,
            provider_reference=execution_result.provider_reference,
            verified_at=now,
            message=execution_result.message or "Execution scheduled for later"
        )
        
    if execution_result.status == "executed":
        if execution_result.action == "payment_link":
            # A generated payment link is pending until the user pays it
            return RecoveryOutcome(
                payment_id=payment_id,
                action=execution_result.action,
                verification_status="pending",
                recovered_amount=0.0,
                provider=execution_result.provider,
                provider_reference=execution_result.provider_reference,
                verified_at=now,
                message="Payment link generated, waiting for customer payment."
            )
        elif execution_result.action == "retry_now":
            # For test mode prototype, a successful synchronous retry means recovered
            return RecoveryOutcome(
                payment_id=payment_id,
                action=execution_result.action,
                verification_status="recovered",
                recovered_amount=execution_result.amount,
                provider=execution_result.provider,
                provider_reference=execution_result.provider_reference,
                verified_at=now,
                message="Synchronous retry succeeded."
            )
            
    # Unknown state
    return RecoveryOutcome(
        payment_id=payment_id,
        action=execution_result.action,
        verification_status="failed",
        recovered_amount=0.0,
        provider=execution_result.provider,
        provider_reference=execution_result.provider_reference,
        verified_at=now,
        message=f"Unknown execution status: {execution_result.status}"
    )
