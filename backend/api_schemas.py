"""RecoverAI — API Request/Response Schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class PaymentRequest(BaseModel):
    """Inbound API request for a failed payment."""
    payment_id: str
    customer_id: str = "unknown"
    subscription_id: str = ""
    amount: float
    failure_type: str
    retry_count: int = 0
    customer_tenure_months: int = 0
    previous_successes: int = 0
    previous_failures: int = 0
    customer_message: Optional[str] = None
    support_note: Optional[str] = None
    merchant_note: Optional[str] = None
    days_since_last_success: int = 0
    subscription_value: float = 0.0

class CandidateActionResponse(BaseModel):
    action: str
    ev: float
    timing: str

class AgentDecisionResponse(BaseModel):
    selected_action: Optional[str] = None
    reason: str = ""
    confidence: float = 0.0
    status: str = "success"

class PolicyDecisionResponse(BaseModel):
    allowed: bool
    action: str
    reason: str
    violations: List[str] = []
    requires_escalation: bool = False
    policy_version: str = "v1"

class ExecutionResultResponse(BaseModel):
    execution_id: str = ""
    action: str = ""
    status: str = ""
    provider: str = ""
    provider_reference: Optional[str] = None
    message: Optional[str] = None
    attempted_at: Optional[str] = None
    metadata: Dict[str, Any] = {}
    amount: float = 0.0
    success: bool = False

class VerificationResultResponse(BaseModel):
    payment_id: str = ""
    action: str = ""
    verification_status: str = ""
    recovered_amount: float = 0.0
    provider: str = ""
    verified_at: str = ""
    message: str = ""

class AnalyzeResponse(BaseModel):
    """Response for the /analyze endpoint — recommendation only, no execution."""
    payment_id: str
    customer_id: str
    amount: float
    failure_type: str
    recovery_opportunity_score: int
    candidate_actions: List[CandidateActionResponse]
    agent_decision: AgentDecisionResponse
    policy_decision: PolicyDecisionResponse

class ExecuteResponse(BaseModel):
    """Response for the /execute endpoint — includes execution + verification."""
    payment_id: str
    customer_id: str
    amount: float
    failure_type: str
    recovery_opportunity_score: int
    candidate_actions: List[CandidateActionResponse]
    agent_decision: AgentDecisionResponse
    policy_decision: PolicyDecisionResponse
    execution_result: ExecutionResultResponse
    verification_result: VerificationResultResponse

class RecoveryRecordSummary(BaseModel):
    """Summary record for list endpoint."""
    id: int
    payment_id: str
    customer_id: Optional[str] = None
    amount: Optional[float] = None
    failure_type: Optional[str] = None
    opportunity_score: Optional[int] = None
    selected_action: Optional[str] = None
    policy_allowed: Optional[bool] = None
    policy_reason: Optional[str] = None
    execution_status: Optional[str] = None
    execution_provider: Optional[str] = None
    verification_status: Optional[str] = None
    recovered_amount: Optional[float] = None
    created_at: str = ""

class RecoveryRecordDetail(BaseModel):
    """Full detail record for single-payment lookup."""
    id: int
    payment_id: str
    customer_id: Optional[str] = None
    amount: Optional[float] = None
    failure_type: Optional[str] = None
    opportunity_score: Optional[int] = None
    selected_action: Optional[str] = None
    agent_reason: Optional[str] = None
    agent_confidence: Optional[float] = None
    policy_allowed: Optional[bool] = None
    policy_reason: Optional[str] = None
    requires_escalation: Optional[bool] = None
    execution_status: Optional[str] = None
    execution_provider: Optional[str] = None
    execution_provider_reference: Optional[str] = None
    verification_status: Optional[str] = None
    recovered_amount: Optional[float] = None
    full_result: Optional[Dict[str, Any]] = None
    created_at: str = ""
