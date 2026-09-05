# RecoverAI — Bounded AI Revenue Recovery for Failed Subscription Payments

RecoverAI helps merchants recover revenue from failed subscription payments using a deterministic recovery analysis pipeline and a strict Policy Engine safety boundary.

> **Evaluation Caveat**: Results are measured on synthetic datasets modeled around the targeted failed-subscription-payment lifecycle. Separate development, held-out, and stress-test regimes are used to evaluate behavior and robustness. These results represent controlled simulation performance and are not claims of live-merchant performance.

## Current Phase 3 Status
### What is currently implemented:
- **Deterministic Recovery Layer**: Calculates opportunity score, candidate actions, Expected Value (EV), and timing heuristics.
- **Robust synthetic data generation**: Evaluates across development, held-out, and stress regimes.
- **LLM Recovery Agent**: Interprets customer messages, support notes, and structured customer context to intelligently select among existing candidates. *The LLM recommends; the Policy Engine authorizes.* It cannot create new recovery actions, modify financial calculations, bypass policy rules, or directly execute payments. Includes safe deterministic fallback behavior when the LLM is unavailable.
- **Deterministic Policy Engine**: A strict authorization layer. The LLM may recommend an action, but it cannot authorize or execute it. Policy rules enforce limits and idempotency. **Policy failure defaults to deny.**

### What it does NOT do yet:
- **No autonomous execution**.
- **No Razorpay integration**.
- **No production payment actions**.
- **No frontend dashboard**.

## Policy Test Matrix
| Condition | Proposed Action | Policy |
| :--- | :--- | :--- |
| Retry count 0 | `retry_now` | ALLOW |
| Retry count 2 | `retry_now` | BLOCK |
| Permanent failure | `retry_later` | BLOCK |
| Payment already successful | `retry_now` | BLOCK |
| Amount ₹9,999 | `retry_now` | ALLOW |
| Amount ₹10,001 | `retry_now` | BLOCK |
| Duplicate event | `retry_now` | BLOCK |
| Unsupported action | `unknown` | BLOCK |

## Architecture (Phase 3)

```text
FAILED PAYMENT
     ↓
CONTEXT BUILDER
     ↓
DETERMINISTIC RECOVERY ANALYSIS (Opportunity Score, Candidate Actions + EV + TIMING)
     ↓
LLM AGENT (Interprets context & selects candidate)
     ↓
POLICY ENGINE (Authorizes or Blocks)
     ↓
EXECUTION (Future)
```

## Testing & LLM Configuration

The project uses a provider abstraction (`LLMProvider`) to ensure the agent logic and tests can run reliably without incurring API costs.

### Running Automated Tests
By default, the `.env.example` sets `LLM_PROVIDER=fake`. This enables the `FakeLLMProvider` which returns mocked deterministic responses.
**You do not need an OpenAI API key to run tests.**

```powershell
# Run tests and evaluation pipeline offline and for free:
pytest tests/
.\run_phase1.ps1
```

### Configuring the Real OpenAI Provider
For live demo cases, you can enable the real OpenAI API integration. This will call the OpenAI API (e.g. `gpt-4o-mini`) using Structured Outputs to enforce candidate selection.

To enable the real provider:
1. Ensure the `openai` python package is installed (`pip install openai`).
2. Copy `.env.example` to `.env` and configure:
```text
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-proj-your-real-key-here
LLM_CONFIDENCE_THRESHOLD=0.70
```
> **Warning**: Never commit your `.env` file or hardcode your API key. The `.gitignore` prevents `.env` tracking.

Set up the Python environment and run the complete Phase 1 pipeline:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install pydantic pytest

# 1. Run Tests
# 2. Run the Evaluation Pipeline (Generates 400 cases per regime & evaluates)
.\run_phase1.ps1
```

### What `evaluate.py` does:
1. **Generates Candidates**: Processes failed payments.
2. **Calculates Scores**: Assigns deterministic Recovery Opportunity Scores.
3. **Calculates EV & Timing**: Attaches expected values and context-aware timing to each candidate.
4. **Produces Metrics**: Evaluates Naive Baseline, Rule-Based Baseline, and RecoverAI (MVP Top-EV) against a simulated outcome environment.

