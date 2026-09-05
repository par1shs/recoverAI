import abc
import os
import json
from typing import Dict, Any, Optional
from .schemas import AgentContext, AgentDecision

class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def get_decision(self, context: AgentContext, system_prompt: str) -> AgentDecision:
        pass

class FakeLLMProvider(LLMProvider):
    """Fake provider for testing."""
    def __init__(self, predefined_responses: Optional[Dict[str, AgentDecision]] = None, default_response: Optional[AgentDecision] = None, should_fail: bool = False, return_invalid_action: bool = False, return_malformed: bool = False):
        self.predefined_responses = predefined_responses or {}
        self.default_response = default_response
        self.should_fail = should_fail
        self.return_invalid_action = return_invalid_action
        self.return_malformed = return_malformed

    def get_decision(self, context: AgentContext, system_prompt: str) -> AgentDecision:
        if self.should_fail:
            raise Exception("Provider API Error")
            
        if self.return_malformed:
            raise ValueError("Malformed JSON output")
            
        # Match by a key, e.g. customer_message or failure_type for tests
        key = context.customer_message if context.customer_message else context.failure_type
        
        if self.return_invalid_action:
            return AgentDecision(
                selected_action="charge_again",
                reason="Invalid action for testing",
                relevant_signals=[],
                confidence=0.9,
                context_summary="Testing candidate restriction"
            )

        if key and key in self.predefined_responses:
            return self.predefined_responses[key]
            
        if self.default_response:
            return self.default_response
            
        # Fallback to choosing the first candidate
        if context.candidates:
            return AgentDecision(
                selected_action=context.candidates[0].action,
                reason="Defaulting to first candidate",
                relevant_signals=[],
                confidence=0.8,
                context_summary="Fallback fake selection"
            )
        
        return AgentDecision(
            selected_action=None,
            reason="No candidates available",
            relevant_signals=[],
            confidence=0.0,
            context_summary=""
        )

class OpenAIProvider(LLMProvider):
    """Implementation for OpenAI using Structured Outputs."""
    def get_decision(self, context: AgentContext, system_prompt: str) -> AgentDecision:
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable not set")
            
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            prompt = f"Context:\n{context.model_dump_json(indent=2)}"
            
            # Using Structured Outputs (client.beta.chat.completions.parse)
            response = client.beta.chat.completions.parse(
                model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format=AgentDecision
            )
            
            decision = response.choices[0].message.parsed
            if not decision:
                raise ValueError("Model failed to parse structured output")
                
            return decision
            
        except Exception as e:
            raise Exception(f"OpenAI API Error: {str(e)}")

def get_llm_provider() -> LLMProvider:
    provider_name = os.environ.get("LLM_PROVIDER", "fake").lower()
    if provider_name == "openai":
        return OpenAIProvider()
    return FakeLLMProvider()
