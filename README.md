# RecoverAI — Bounded AI Revenue Recovery for Failed Subscription Payments

RecoverAI helps merchants recover revenue from failed subscription payments using a deterministic recovery analysis pipeline. 

> **Evaluation Caveat**: Results are measured on synthetic datasets modeled around the targeted failed-subscription-payment lifecycle. Separate development, held-out, and stress-test regimes are used to evaluate behavior and robustness. These results represent controlled simulation performance and are not claims of live-merchant performance.

## Current Phase 1 Status
### What Phase 1 currently does:
- Deterministic recovery analysis (Opportunity Score, EV, Timing heuristics).
- Robust synthetic data generation and comprehensive evaluation across multiple regimes.
- **RecoverAI Top-EV MVP (LLM stand-in)**: The current strategy deterministically selects the highest-EV candidate. 

### What it does NOT do yet:
- **No LLM Agent**: The LLM agent will be introduced in a later phase to interpret unstructured customer context and select among the deterministic candidate actions.
- **No autonomous execution** or Policy Engine.
- **No Razorpay integration**.
- **No production payment actions**.

## Architecture (Phase 1)

```text
FAILED PAYMENT -> CONTEXT BUILDER -> DETERMINISTIC RECOVERY ANALYSIS (Opportunity Score, Candidate Actions + EV + TIMING)
```

## Quick Start (Phase 1)

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

