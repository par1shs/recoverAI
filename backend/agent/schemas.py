from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class AgentDecision(BaseModel):
    # Gemini structured output must not introduce fields outside this contract.
    model_config = ConfigDict(extra="forbid")
    selected_action: Optional[str] = None
    reason: str
    relevant_signals: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    context_summary: str = ""
    status: str = "success"  # 'success' or 'unavailable'

class CandidateInfo(BaseModel):
    action: str
    ev: float
    timing: str

class AgentContext(BaseModel):
    # Structured Context
    amount: float
    failure_type: str
    retry_count: int
    customer_tenure_months: int
    previous_successes: int
    previous_failures: int
    days_since_last_success: int = 0
    subscription_value: float = 0.0
    recovery_opportunity_score: int
    
    # Unstructured Context
    customer_message: Optional[str] = None
    support_note: Optional[str] = None
    merchant_note: Optional[str] = None
    
    # Candidates
    candidates: List[CandidateInfo]
