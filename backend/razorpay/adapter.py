import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

from backend.recovery.schemas import PaymentContext
from backend.execution.schemas import ExecutionResult
from backend.execution.adapter import ExecutionAdapter

logger = logging.getLogger(__name__)

class RazorpayExecutionAdapter(ExecutionAdapter):
    def __init__(self):
        self.key_id = os.environ.get("RAZORPAY_KEY_ID")
        self.key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
        self.mode = os.environ.get("RAZORPAY_MODE", "test")
        
    def execute(self, action: str, payment_context: PaymentContext, event_id: str) -> ExecutionResult:
        now = datetime.now(timezone.utc).isoformat()
        exec_id = f"exec_rzp_{uuid.uuid4().hex[:8]}"
        
        if action in ["escalate", "stop"]:
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status=f"{action}ped" if action == "stop" else f"{action}d",
                provider="razorpay_test",
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
                provider="razorpay_test",
                provider_reference=f"test_sched_{uuid.uuid4().hex[:8]}",
                attempted_at=now,
                amount=payment_context.amount,
                success=True,
                message=f"Scheduled for {scheduled_for}",
                metadata={"scheduled_for": scheduled_for}
            )
            
        if not self.key_id or not self.key_secret:
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status="failed",
                provider="razorpay_test",
                attempted_at=now,
                amount=payment_context.amount,
                success=False,
                message="Razorpay credentials not configured."
            )
            
        try:
            # Fake network call logic representing Razorpay integration
            # import razorpay
            # client = razorpay.Client(auth=(self.key_id, self.key_secret))
            
            if action == "payment_link":
                # Responds with a pending state for link generation
                provider_ref = f"plink_{uuid.uuid4().hex[:14]}"
                message = "Payment link generated in test mode."
            elif action == "retry_now":
                provider_ref = f"pay_{uuid.uuid4().hex[:14]}"
                message = "Synchronous charge succeeded in test mode."
            else:
                return ExecutionResult(
                    execution_id=exec_id,
                    action=action,
                    status="failed",
                    provider="razorpay_test",
                    attempted_at=now,
                    amount=payment_context.amount,
                    success=False,
                    message=f"Unsupported action for razorpay test mode: {action}"
                )
                
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status="executed",
                provider="razorpay_test",
                provider_reference=provider_ref,
                attempted_at=now,
                amount=payment_context.amount,
                success=True,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Razorpay API Error: {e}")
            return ExecutionResult(
                execution_id=exec_id,
                action=action,
                status="failed",
                provider="razorpay_test",
                attempted_at=now,
                amount=payment_context.amount,
                success=False,
                message=str(e)
            )
