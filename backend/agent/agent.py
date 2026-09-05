import logging
from .schemas import AgentContext, AgentDecision
from .prompts import SYSTEM_PROMPT
from .provider import LLMProvider

logger = logging.getLogger(__name__)

class RecoveryDecisionAgent:
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        
    def decide(self, context: AgentContext) -> AgentDecision:
        if not context.candidates:
            return AgentDecision(
                selected_action=None,
                reason="No candidates supplied by deterministic engine",
                relevant_signals=[],
                confidence=0.0,
                context_summary="",
                status="unavailable"
            )
            
        candidate_actions = {c.action for c in context.candidates}
        
        try:
            decision = self.provider.get_decision(context, SYSTEM_PROMPT)
            
            # Candidate restriction mechanism
            if decision.selected_action not in candidate_actions:
                logger.warning(f"LLM proposed invalid action '{decision.selected_action}'. Allowed: {candidate_actions}")
                return AgentDecision(
                    selected_action=None,
                    reason=f"LLM proposed an invalid action: {decision.selected_action}",
                    relevant_signals=[],
                    confidence=0.0,
                    context_summary="Fallback due to candidate restriction violation",
                    status="unavailable" # Safe fallback
                )
                
            return decision
            
        except Exception as e:
            logger.error(f"LLM decision failed safely: {e}")
            return AgentDecision(
                selected_action=None,
                reason=f"LLM unavailable or failed: {str(e)}",
                relevant_signals=[],
                confidence=0.0,
                context_summary="Fallback due to provider failure",
                status="unavailable"
            )
