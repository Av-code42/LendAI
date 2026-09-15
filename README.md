# LendAI

Agentic digital lending & underwriting MVP — an end-to-end personal-loan
workflow where an AI agent orchestrates evidence collection and tools,
while deterministic ML/policy/routing layers govern every consequential
decision.

**Core rule:** LLM → structured action → schema validation → permission
validation → tool/model/policy → deterministic router → human or
authorized workflow. The LLM is never the authoritative credit/fraud
decision-maker and never writes to the database directly.

> All data, names, scores and policy thresholds anywhere in this repo are
> synthetic and illustrative — for development and portfolio demonstration
> only, not real bank policy or real customer data.

## Repository layout

- `frontend/` — the customer-facing loan application flow and the
  underwriter human-review console (React + TypeScript + Vite +
  Tailwind), currently backed by an in-browser mock API layer. See
  `frontend/README.md`.
- `backend/` — Python/FastAPI backend: Postgres schema + data loader for
  the real 10,000-row dataset bundle, the state machine, the policy
  engine (validated 10,000/10,000 against ground truth), trained credit
  and fraud ML models (Logistic Regression / Random Forest / XGBoost
  compared), the deterministic decision router (validated 99.3% against
  ground truth), the agent tool/permission layer, and the full REST API.
  See `backend/README.md` for setup, architecture, and known limitations.
- Frontend↔backend wiring, real OCR, real device/fraud signal capture,
  auth/RBAC, and an actual LLM in the agent loop are not yet built.

## Recommended build order

1. ~~Load data into PostgreSQL.~~ ✅
2. ~~Implement the application state machine.~~ ✅
3. ~~Implement the policy engine from the JSON policy.~~ ✅
4. ~~Train/evaluate credit and fraud ML models.~~ ✅
5. ~~Expose model scoring behind internal APIs.~~ ✅
6. ~~Implement agent tool contracts and action validation.~~ ✅
7. ~~Implement deterministic decision routing.~~ ✅
8. ~~Build the customer & human-review UI.~~ ✅
9. ~~Add audit/event logging.~~ ✅
10. ~~Add mock offer/agreement/disbursal.~~ ✅
11. ~~Run golden and adversarial test cases.~~ ✅ (`backend/tests/`)

**Next up:** wire the frontend to the real backend (currently the
frontend runs its own mock API layer independently); swap the
deterministic agent orchestrator for a real LLM-driven one against the
same tool contract and guardrails.
