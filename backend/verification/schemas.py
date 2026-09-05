from pydantic import BaseModel
from typing import Optional, Any, Dict

class RecoveryOutcome(BaseModel):
    payment_id: str
    action: str
    verification_status: str  # recovered, not_recovered, pending, failed
    recovered_amount: float
    provider: str
    provider_reference: Optional[str] = None
    verified_at: str
    message: str
    metadata: Dict[str, Any] = {}
