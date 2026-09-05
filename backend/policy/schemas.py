from pydantic import BaseModel, Field
from typing import List

class PolicyConfig(BaseModel):
    max_retries: int = 2
    max_autonomous_amount: float = 10000.0
    max_customer_contacts: int = 2
    policy_version: str = "v1"

class ExecutionState(BaseModel):
    is_already_successful: bool = False
    previously_executed_events: List[str] = Field(default_factory=list)
    customer_contacts_count: int = 0
    event_id: str

class PolicyDecision(BaseModel):
    allowed: bool
    action: str
    reason: str
    violations: List[str]
    requires_escalation: bool
    policy_version: str
