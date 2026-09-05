import abc
import uuid
from datetime import datetime, timezone, timedelta
from backend.recovery.schemas import PaymentContext
from .schemas import ExecutionResult

class ExecutionAdapter(abc.ABC):
    @abc.abstractmethod
    def execute(self, action: str, payment_context: PaymentContext, event_id: str) -> ExecutionResult:
        pass

class SimulatorExecutionAdapter(ExecutionAdapter):
    def execute(self, action: str, payment_context: PaymentContext, event_id: str) -> ExecutionResult:
        now = datetime.now(timezone.utc).isoformat()
        exec_id = f"exec_sim_{uuid.uuid4().hex[:8]}"
        
        if action in ["escalate", "stop"]:
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status=f"{action}ped" if action == "stop" else f"{action}d",  # stopped / escalated
                provider="simulator",
                attempted_at=now,
                amount=payment_context.amount,
                success=True,
                message=f"Action '{action}' processed without executing payment."
            )
            
        if action == "retry_later":
            scheduled_for = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status="scheduled",
                provider="simulator",
                provider_reference=f"sched_{uuid.uuid4().hex[:8]}",
                attempted_at=now,
                amount=payment_context.amount,
                success=True,
                message=f"Scheduled for {scheduled_for}",
                metadata={"scheduled_for": scheduled_for}
            )
            
        if action in ["retry_now", "payment_link"]:
            # Pure simulated execution succeeds
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status="executed",
                provider="simulator",
                provider_reference=f"sim_ref_{uuid.uuid4().hex[:8]}",
                attempted_at=now,
                amount=payment_context.amount,
                success=True,
                message="Simulated execution successful"
            )
            
        # Unsupported action
        return ExecutionResult(
            execution_id=exec_id,
            action=action,
            status="failed",
            provider="simulator",
            attempted_at=now,
            amount=payment_context.amount,
            success=False,
            message=f"Simulator cannot execute unsupported action: {action}"
        )
