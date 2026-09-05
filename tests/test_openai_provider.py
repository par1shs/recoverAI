import os
import pytest
from unittest.mock import patch, MagicMock

from backend.agent.schemas import AgentContext, AgentDecision, CandidateInfo
from backend.agent.provider import OpenAIProvider

@pytest.fixture
def agent_context():
    return AgentContext(
        amount=1000,
        failure_type="insufficient_funds",
        retry_count=0,
        customer_tenure_months=12,
        previous_successes=10,
        previous_failures=0,
        recovery_opportunity_score=80,
        candidates=[CandidateInfo(action="retry_later", ev=1000, timing="24h")]
    )

def test_missing_api_key_raises_error(agent_context):
    provider = OpenAIProvider()
    if "LLM_API_KEY" in os.environ:
        del os.environ["LLM_API_KEY"]
        
    with pytest.raises(ValueError, match="LLM_API_KEY environment variable not set"):
        provider.get_decision(agent_context, "prompt")

@patch.dict(os.environ, {"LLM_API_KEY": "test_key", "LLM_MODEL": "gpt-4o-mini"})
@patch("openai.OpenAI")
def test_valid_structured_output_parsing(mock_openai, agent_context):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    # Mock the parse response
    mock_response = MagicMock()
    mock_parsed_decision = AgentDecision(
        selected_action="retry_later",
        reason="Test reason",
        confidence=0.9,
        relevant_signals=[],
        context_summary="Summary"
    )
    mock_response.choices[0].message.parsed = mock_parsed_decision
    mock_client.beta.chat.completions.parse.return_value = mock_response
    
    provider = OpenAIProvider()
    decision = provider.get_decision(agent_context, "system prompt")
    
    assert decision.selected_action == "retry_later"
    assert decision.reason == "Test reason"
    
    # Verify client was called correctly
    mock_client.beta.chat.completions.parse.assert_called_once()
    kwargs = mock_client.beta.chat.completions.parse.call_args[1]
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["response_format"] == AgentDecision

@patch.dict(os.environ, {"LLM_API_KEY": "test_key"})
@patch("openai.OpenAI")
def test_provider_handles_parsing_failure(mock_openai, agent_context):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    # Mock parse failure (parsed is None)
    mock_response = MagicMock()
    mock_response.choices[0].message.parsed = None
    mock_client.beta.chat.completions.parse.return_value = mock_response
    
    provider = OpenAIProvider()
    with pytest.raises(Exception, match="Model failed to parse"):
        provider.get_decision(agent_context, "system prompt")

@patch.dict(os.environ, {"LLM_API_KEY": "test_key"})
@patch("openai.OpenAI")
def test_provider_handles_api_exception(mock_openai, agent_context):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    mock_client.beta.chat.completions.parse.side_effect = Exception("Network timeout")
    
    provider = OpenAIProvider()
    with pytest.raises(Exception, match="OpenAI API Error: Network timeout"):
        provider.get_decision(agent_context, "system prompt")
