"""Mocked tests for the Gemini provider; these never make network calls."""
import json
from unittest.mock import MagicMock, patch

import pytest

from backend.agent.agent import RecoveryDecisionAgent
from backend.agent.provider import GeminiProvider, get_llm_provider
from backend.agent.schemas import AgentContext, CandidateInfo


@pytest.fixture
def agent_context():
    return AgentContext(
        amount=999.0,
        failure_type="insufficient_funds",
        retry_count=0,
        customer_tenure_months=18,
        previous_successes=15,
        previous_failures=1,
        recovery_opportunity_score=100,
        customer_message="I get paid tomorrow. Please don't cancel my subscription.",
        candidates=[
            CandidateInfo(action="retry_now", ev=94.9, timing="now"),
            CandidateInfo(action="retry_later", ev=494.5, timing="48h"),
            CandidateInfo(action="payment_link", ev=397.6, timing="now"),
            CandidateInfo(action="escalate", ev=99.8, timing="now"),
        ],
    )


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "LLM_MODEL": "gemini-test"})
@patch("google.genai.Client")
def test_initializes_official_google_client(mock_client):
    provider = GeminiProvider()

    mock_client.assert_called_once_with(api_key="test-key")
    assert provider.model == "gemini-test"


def test_requires_gemini_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable not set"):
        GeminiProvider()


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "LLM_MODEL": "gemini-test"})
@patch("google.genai.Client")
def test_uses_structured_output_and_validates_agent_decision(mock_client, agent_context):
    response = MagicMock()
    response.output_text = json.dumps(
        {
            "selected_action": "retry_later",
            "reason": "The customer explicitly says funds arrive tomorrow.",
            "relevant_signals": ["customer_message", "insufficient_funds"],
            "confidence": 0.92,
            "context_summary": "Customer asks to pay tomorrow.",
        }
    )
    mock_client.return_value.interactions.create.return_value = response
    provider = GeminiProvider()

    decision = provider.get_decision(agent_context, "system instructions")

    assert decision.selected_action == "retry_later"
    kwargs = mock_client.return_value.interactions.create.call_args.kwargs
    assert kwargs["model"] == "gemini-test"
    assert kwargs["response_format"]["mime_type"] == "application/json"
    assert kwargs["response_format"]["schema"] == decision.__class__.model_json_schema()
    assert "ground_truth_outcome" not in kwargs["input"]
    request_context = kwargs["input"].split("Decision-time context:\n", 1)[1]
    assert json.loads(request_context) == agent_context.model_dump()


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
@patch("google.genai.Client")
def test_rejects_malformed_structured_output(mock_client, agent_context):
    response = MagicMock()
    response.output_text = "not-json"
    mock_client.return_value.interactions.create.return_value = response

    with pytest.raises(Exception, match="Gemini API Error"):
        GeminiProvider().get_decision(agent_context, "prompt")


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
@patch("google.genai.Client")
def test_rejects_action_outside_candidate_list_and_agent_fails_safely(mock_client, agent_context):
    response = MagicMock()
    response.output_text = json.dumps(
        {
            "selected_action": "charge_again",
            "reason": "Invalid action",
            "relevant_signals": [],
            "confidence": 0.9,
            "context_summary": "Invalid output.",
        }
    )
    mock_client.return_value.interactions.create.return_value = response

    decision = RecoveryDecisionAgent(GeminiProvider()).decide(agent_context)

    assert decision.selected_action is None
    assert decision.status == "unavailable"
    assert "failed" in decision.reason.lower()


@patch.dict("os.environ", {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"})
@patch("google.genai.Client")
def test_factory_selects_gemini_provider(mock_client):
    assert isinstance(get_llm_provider(), GeminiProvider)
