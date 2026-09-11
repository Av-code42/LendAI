# LendAI

Agentic digital lending & underwriting MVP — an end-to-end personal-loan
workflow where an AI agent orchestrates evidence collection and tools,
while deterministic ML/policy/routing layers govern every consequential
decision. See `frontend/PRD.md`-equivalent context in the project bundle
for the full product spec.

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
  Tailwind), currently backed by an in-browser mock API layer standing in
  for the real backend. See `frontend/README.md` for setup.
- Backend, ML services, and infra are not yet built — this repo currently
  covers the frontend milestone only, built against the API surface the
  real backend will implement next (see `frontend/src/mocks/handlers.ts`
  for the exact contract).

## Recommended build order

1. Load data into PostgreSQL.
2. Implement the application state machine.
3. Implement the policy engine from the JSON policy.
4. Train/evaluate credit and fraud ML models.
5. Expose model scoring behind internal APIs.
6. Implement agent tool contracts and action validation.
7. Implement deterministic decision routing.
8. **Build the customer & human-review UI. ← current milestone**
9. Add audit/event logging.
10. Add mock offer/agreement/disbursal.
11. Run golden and adversarial test cases.
