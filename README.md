# RecoverAI — Bounded AI Revenue Recovery for Failed Subscription Payments

RecoverAI helps merchants recover revenue from failed subscription payments using a deterministic recovery analysis pipeline, an LLM agent, and a strict Policy Engine safety boundary.

> **Evaluation Caveat**: Results are measured on synthetic datasets. These results represent controlled simulation performance and are **not** claims of live-merchant performance.

## Quick Start

```powershell
# 1. Setup Backend
python -m venv venv
.\venv\Scripts\activate
pip install pydantic pytest fastapi uvicorn httpx razorpay openai aiosqlite

# 2. Run backend tests (no API keys required)
$env:PYTHONPATH="."
pytest tests/

# 3. Run Phase 1 evaluation (1,200 synthetic cases)
.\run_phase1.ps1

# 4. Start the API server (simulator mode — no credentials needed)
$env:EXECUTION_MODE="simulator"
$env:LLM_PROVIDER="fake"
uvicorn backend.app:app --reload
```
API server runs at `http://127.0.0.1:8000`.

### Dashboard Frontend

The repository includes a Vite + React dashboard to visualize the pipeline (AI recommendation → Policy Engine → Execution).

```powershell
# Open a new terminal
cd frontend
npm install
npm run dev
```
The dashboard runs at `http://localhost:5173`.


The server starts at `http://127.0.0.1:8000`. Interactive API docs at `/docs`.

## Architecture (Phase 5)

```text
FAILED PAYMENT
     ↓
API (FastAPI)
     ↓
CONTEXT BUILDER
     ↓
DETERMINISTIC RECOVERY ANALYSIS (Candidates + EV + Timing)
     ↓
LLM AGENT (Interprets context & selects candidate)
     ↓
POLICY ENGINE (Authorizes or Blocks)
     ↓                    ↓
  [ALLOW]              [BLOCK]
     ↓                    ↓
EXECUTION ADAPTER     NO EXECUTION
(Simulator / Razorpay)   → Escalate
     ↓
VERIFICATION LAYER
     ↓
AUDIT TRAIL / SQLite
     ↓
API RESPONSE
```

### Key Rules
- The **backend** deterministically computes candidate actions, Expected Value, and timing.
- The **LLM** selects from supplied candidates only. It cannot invent actions, modify amounts, or bypass policy.
- The **Policy Engine** is the only component that can authorize execution. Policy failure defaults to **deny**.
- **Execution ≠ Recovery**. Creating a payment link (HTTP 200) does not mean revenue was recovered.

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/recoveries/analyze` | Recommendation only (no execution) |
| `POST` | `/api/v1/recoveries/execute` | Full pipeline with execution + verification |
| `GET` | `/api/v1/recoveries` | List recent recovery records |
| `GET` | `/api/v1/recoveries/{payment_id}` | Detail for a specific payment |
| `GET` | `/api/v1/demos` | List demo scenarios |
| `POST` | `/api/v1/demos/{scenario}/execute` | Run a demo scenario |

### Example: Analyze a Failed Payment

```bash
curl -X POST http://localhost:8000/api/v1/recoveries/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pay_001",
    "customer_id": "cust_001",
    "amount": 999.0,
    "failure_type": "insufficient_funds",
    "retry_count": 0,
    "customer_tenure_months": 18,
    "previous_successes": 15,
    "previous_failures": 1,
    "customer_message": "I get paid tomorrow."
  }'
```

**Response** (truncated):
```json
{
  "recovery_opportunity_score": 100,
  "candidate_actions": [
    {"action": "retry_later", "ev": 494.5, "timing": "48h"},
    {"action": "payment_link", "ev": 397.6, "timing": "now"},
    {"action": "escalate", "ev": 99.8, "timing": "now"}
  ],
  "agent_decision": {"selected_action": "retry_later", "confidence": 0.8},
  "policy_decision": {"allowed": true, "reason": "Authorized"}
}
```

### Example: Execute (with Policy Block)

```bash
curl -X POST http://localhost:8000/api/v1/recoveries/execute \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pay_blocked",
    "amount": 499.0,
    "failure_type": "temporary_bank_failure",
    "retry_count": 3
  }'
```

**Response** (policy blocks because retry_count ≥ max_retries):
```json
{
  "policy_decision": {"allowed": false, "reason": "Maximum retry limit reached"},
  "execution_result": {"status": "blocked", "provider": "none"},
  "verification_result": {"verification_status": "not_recovered"}
}
```

## Demo Scenarios

| Scenario | Failure Type | Purpose |
|----------|-------------|---------|
| `insufficient_funds` | Customer short on funds | Shows retry_later recommendation |
| `retry_limit_reached` | Too many retries | **Safety demo**: Policy blocks execution |
| `expired_card` | Card expired | Shows payment_link recommendation |
| `permanent_failure` | Permanent decline | Shows stop/escalate, no retry candidates |

```bash
# Run Scenario B (safety demo)
curl -X POST http://localhost:8000/api/v1/demos/retry_limit_reached/execute
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `fake` | `fake` for testing, `openai` for real LLM |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `LLM_API_KEY` | — | OpenAI API key (only for `openai` provider) |
| `LLM_CONFIDENCE_THRESHOLD` | `0.70` | Below this, agent escalates |
| `EXECUTION_MODE` | `simulator` | `simulator` or `razorpay_test` |
| `RAZORPAY_MODE` | `test` | Must be `test` |
| `RAZORPAY_KEY_ID` | — | Razorpay Test key (only for `razorpay_test`) |
| `RAZORPAY_KEY_SECRET` | — | Razorpay Test secret |
| `DATABASE_PATH` | `recoverai.db` | SQLite database path |

> **Warning**: Never commit `.env` or hardcode credentials. The `.gitignore` prevents `.env` and `*.db` tracking.

## Execution Modes

### Simulator (default)
- No external credentials required.
- Provider clearly identified as `"simulator"`.
- Synthetic references use `sim_ref_*` / `sched_*` prefixes — never mistaken for real Razorpay IDs.
- Complete workflow runs locally for demo/testing.

### Razorpay Test Mode
- Set `EXECUTION_MODE=razorpay_test` with valid test credentials.
- `payment_link`: Real Razorpay Test Mode Payment Link API call. Creating a link is execution, **not** recovered revenue.
- `retry_now`: Fails safely — requires a real subscription/invoice identifier.
- `retry_later`: Scheduled (non-blocking), no API call.
- `escalate` / `stop`: No payment API call.
- If credentials are missing, fails clearly — does **not** silently fall back to simulator.

## Policy Test Matrix

| Condition | Proposed Action | Policy |
|-----------|----------------|--------|
| Retry count 0 | `retry_now` | ALLOW |
| Retry count ≥ 2 | `retry_now` | BLOCK |
| Permanent failure | `retry_later` | BLOCK |
| Payment already successful | `retry_now` | BLOCK |
| Amount ≤ ₹10,000 | `retry_now` | ALLOW |
| Amount > ₹10,000 | `retry_now` | BLOCK |
| Duplicate event | `retry_now` | BLOCK |
| Unsupported action | `unknown` | BLOCK |

## Testing

```powershell
$env:PYTHONPATH="."
pytest tests/     # All automated tests (no API keys / network required)
.\run_phase1.ps1  # Full 1,200-case synthetic evaluation
```

- Tests use `FakeLLMProvider` + `SimulatorExecutionAdapter`.
- No real OpenAI or Razorpay API calls during `pytest`.
- Phase 1 evaluation remains deterministic across dev/held-out/stress regimes.

## Limitations

- No production payment processing.
- No polished frontend dashboard (API only).
- Simulator execution is synthetic — not a claim of live recovered revenue.
- Razorpay `retry_now` requires real subscription/invoice identifiers not yet available in the data model.
- SQLite is used for lightweight persistence; not designed for production scale.
