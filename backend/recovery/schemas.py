from pydantic import BaseModel
from typing import List, Optional

class CandidateAction(BaseModel):
    action_type: str
    ev: float
    timing: str

class RecoveryAnalysisResult(BaseModel):
    opportunity_score: int
    candidates: List[CandidateAction]
    
class PaymentContext(BaseModel):
    model_config = {'extra': 'forbid'}
    amount: float
    failure_type: str
    retry_count: int
    customer_tenure_months: int
    previous_successes: int
    previous_failures: int
    customer_message: Optional[str] = None
    support_note: Optional[str] = None
