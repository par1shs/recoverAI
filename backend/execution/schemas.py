from pydantic import BaseModel
from typing import Optional, Any, Dict

class ExecutionResult(BaseModel):
    execution_id: str
    action: str
    status: str  # executed, scheduled, skipped, failed, blocked, escalated, stopped
    provider: str
    provider_reference: Optional[str] = None
    message: Optional[str] = None
    attempted_at: Optional[str] = None
    metadata: Dict[str, Any] = {}
    amount: float
    success: bool
