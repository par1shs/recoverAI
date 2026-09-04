# RecoverAI — Bounded AI Revenue Recovery for Failed Subscription Payments

RecoverAI helps merchants recover revenue from failed subscription payments using a deterministic recovery analysis pipeline enhanced by an LLM for context-aware candidate selection, all constrained by a strict policy engine.

> **Note**: Results are measured on synthetic datasets modeled around the targeted payment lifecycle. Held-out and stress-test regimes are used to evaluate generalization and robustness. These results are controlled simulations, not claims of live-merchant performance.

## Architecture (Phase 1)

```text
FAILED PAYMENT -> CONTEXT BUILDER -> DETERMINISTIC RECOVERY ANALYSIS (Opportunity Score, Candidate Actions + EV + TIMING)
```
*(The LLM Agent and Policy Engine components will be added in subsequent phases).*

## Project Structure

- `backend/api/` - FastAPI application (upcoming)
- `backend/agent/` - LLM Agent (upcoming)
- `backend/recovery/` - Recovery Engine (Opportunity Score, EV, Candidates, Timing)
- `backend/policy/` - Policy Engine (upcoming)
- `backend/razorpay/` - Razorpay Test Mode Integration (upcoming)
- `backend/audit/` - Audit Trail (upcoming)
- `backend/simulator/` - Synthetic data generator and evaluator
- `tests/` - Unit tests
- `data/` - Synthetic dataset splits

## Quick Start (Phase 1)

Set up the Python environment and run the complete Phase 1 pipeline:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install pydantic pytest

# 1. Run Tests
$env:PYTHONPATH="."
pytest tests/

# 2. Generate Synthetic Dataset (200 dev, 100 test, 100 stress)
python backend/simulator/generator.py

# 3. Evaluate Baselines vs RecoverAI Engine
python backend/simulator/evaluate.py
```

### What `evaluate.py` does:
1. **Generates Candidates**: Processes 100+ failed payments.
2. **Calculates Scores**: Assigns deterministic Recovery Opportunity Scores.
3. **Calculates EV & Timing**: Attaches expected values and context-aware timing to each candidate.
4. **Produces Metrics**: Evaluates Naive Baseline, Rule-Based Baseline, and RecoverAI (MVP Top-EV) against a simulated outcome environment.
