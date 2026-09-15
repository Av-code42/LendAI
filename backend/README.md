# LendAI Backend

Python/FastAPI backend implementing the PRD's state machine, policy
engine, ML scoring, deterministic decision router, and agent tool layer
-- against the real synthetic dataset bundle (customers, applications,
transactions, documents, fraud features, and historical routing/policy/
model-output ground truth, 10,000 rows each).

> All data, names, and policy thresholds are synthetic/illustrative
> (PRD "Data disclaimer"). Not real bank policy or real customer data.

## Stack

Python 3.11 · FastAPI · SQLAlchemy 2.0 + Alembic · PostgreSQL 16 ·
scikit-learn + XGBoost · pytest

## Quickstart (Docker)

```bash
docker compose up --build
```

This runs migrations, loads the bundled dataset, trains the ML models,
and starts the API on `http://localhost:8000`. First boot takes a minute
or two (training).

## Quickstart (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Postgres must be running locally; database `lendai` must exist.
cp .env.example .env   # adjust DATABASE_URL if needed

alembic upgrade head
python scripts/load_data.py --reset   # loads the 9 bundle files
python -m app.ml.train                # trains + saves credit/fraud models
python scripts/export_lite_models.py  # distills + validates the pure-Python scorer

uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`.

Run tests (spins up its own `lendai_test` database, isolated via
per-test SAVEPOINT rollback):

```bash
createdb lendai_test   # once
pytest tests/ -v
```

## Deploying to Vercel

The API deploys to Vercel as a Python serverless function
(`api/index.py` re-exports the FastAPI `app`; `vercel.json` routes every
path to it). Vercel serverless has no persistent local disk/Postgres, so
this needs an external managed Postgres reachable over the network --
[Neon](https://neon.tech) is the natural choice (free tier, and Vercel
has a native "Storage -> Neon" integration that provisions one and wires
the connection string in for you).

**One-time setup, before or right after the first deploy:**

1. Create a Postgres database (Neon via Vercel's Storage tab, or
   standalone at neon.tech/supabase/etc.). Use the **pooled** connection
   string if your provider offers one (Neon: the "Pooled connection"
   string) -- serverless functions open a fresh connection per
   invocation, and a pooler on the DB side absorbs that far better than
   a raw Postgres connection.
2. Run migrations and load the dataset against that database from a
   normal shell (your machine, or this session if it has network access
   to your DB host) -- these are one-time/one-off operations, not part of
   the deployed function:
   ```bash
   DATABASE_URL="<your connection string>" alembic upgrade head
   DATABASE_URL="<your connection string>" python scripts/load_data.py --reset
   ```
   Model training does **not** need to be re-run against the new
   database -- `artifacts/models/*.joblib` (and their distilled
   `*_lite.json` siblings, see below) are already committed and are
   loaded as static files by the deployed function; only per-application
   *feature lookups* at scoring time hit the database.
3. In the Vercel project (Root Directory: `backend`), set the
   `DATABASE_URL` environment variable to the same connection string.
4. Set `CORS_ALLOW_ORIGINS` to your frontend's real origin(s) (a JSON
   array, e.g. `["https://your-frontend.vercel.app"]`) once you're ready
   to lock it down -- it defaults to `["*"]`, fine for an initial
   preview deploy.

**Why the deployed function's dependencies are so much smaller than
local/Docker:** the first real deploy attempt hit Vercel's function size
limit head-on -- the full `requirements.txt` (with xgboost, scikit-learn,
scipy, pandas, numpy) came to just over **1 GB**, well past the 500 MB
cap. Removing xgboost alone (only used by the offline training script)
wasn't enough of a margin to trust -- scikit-learn + scipy + pandas +
numpy alone still measured ~**410 MB** installed.

So scoring doesn't use scikit-learn at request time at all anymore.
`app/ml/lite.py` is a from-scratch, pure-Python reimplementation of a
scikit-learn `Pipeline(StandardScaler + OneHotEncoder, LogisticRegression)`
predict -- linear regression is exactly a dot product plus a sigmoid, and
`scripts/export_lite_models.py` distills the trained joblib pipeline's
fitted coefficients into a small JSON spec (`artifacts/models/
{credit,fraud}_model_lite.json`) that `app/ml/lite.py` scores with only
the standard library. Before trusting it, that export script validates
the lite scorer against the real sklearn pipeline **on every application
in the database** and refuses to write the spec if they don't match to
high precision -- the actual run validated all 10,001 applications for
both models, max difference **4.44e-16** (credit) and **1.05e-14**
(fraud), i.e. floating-point noise, not approximation. `app/ml/scoring.py`
prefers the lite spec whenever one exists and only imports
joblib/scikit-learn (lazily) as a fallback.

The result: `api/requirements.txt` needs only FastAPI, SQLAlchemy,
psycopg2, and Pydantic -- **~47 MB installed**, measured directly (vs.
the ~410-1000+ MB above). `../requirements.txt` (local dev, Docker,
tests) is unaffected and keeps the full training stack.

**If a future retrain picks a tree-based model (Random Forest/XGBoost)
as the winner for either target**, `export_lite_models.py` will detect
that and skip the lite export for that model, and `scoring.py` falls
back to the full joblib+scikit-learn path -- which needs those
dependencies added back to `api/requirements.txt` before deploying, or
the deployed function will fail at prediction time for that model.

## Architecture

```
app/
  db/            SQLAlchemy models + session (13 tables)
  policy/        Deterministic policy engine (PL_2026_V1)
  ml/            Feature engineering, training, scoring
  routing/       Evidence checks + the deterministic decision router
  core/          State machine, config, audit log, document pipeline stub
  agent/         Tool contracts, permission/schema/timeout dispatcher,
                 and a deterministic orchestrator (see below)
  api/           FastAPI routers (applications, reviews)
  schemas/       Pydantic request/response models
scripts/
  load_data.py          Loads the 9 bundle files into Postgres
  validate_policy.py    Policy engine vs. policy_results.csv (10,000 rows)
  validate_router.py    Full router vs. decision_routing.csv (10,000 rows)
  smoke_test_agent.py   End-to-end orchestrator smoke test
```

### Core rule, enforced structurally

LLM/agent -> structured tool call -> schema validation -> permission
validation -> tool execution -> deterministic router -> human or
authorized workflow. Concretely:

- **The agent never decides anything.** `app/agent/orchestrator.py` calls
  the same 7 tools (`config/tool_schemas.json`) an LLM would, in the same
  order, but every tool call is validated and logged by
  `app/agent/dispatcher.py` before it runs. Approve/decline/review is
  always the output of `app/routing/router.py`, a pure function over
  policy/model/evidence signals -- the agent only supplies those signals.
- **Prohibited actions are unreachable, not just blocked.** There is no
  "override policy" or "approve" tool in the whitelist at all -- calling
  anything not in `tool_schemas.json` is rejected by the dispatcher before
  execution (PRD golden case 8), logged as `BLOCKED_ACTION`, with no state
  change.
- **The state machine is backend-owned.** `app/core/state_machine.py` is
  the only place a status transition is allowed to happen; an illegal
  jump raises before touching the database, whether requested by the API,
  the orchestrator, or a human decision.
- **Guardrails are real, not decorative.** Max agent steps *per run*
  (`AgentStepLimitExceeded`, fail-safe-escalates to `HUMAN_REVIEW`) and a
  wall-clock tool timeout (`ToolTimeoutError`, via a real thread-pool
  `.result(timeout=...)`, not just a config flag) are both covered by
  adversarial tests in `tests/test_golden_cases.py`.

### The orchestrator is deterministic, not an LLM -- on purpose, for now

`app/agent/orchestrator.py` is a fixed script that calls tools in a fixed
order. It stands in for a real LLM-driven agent (e.g. Claude choosing
which tool to call next against the same `tool_schemas.json` contract)
without changing anything about the guardrails above, since those live in
the dispatcher/state machine/router, not in whoever is calling the tools.
Swapping in a real LLM loop is the natural next milestone.

### The document pipeline is a placeholder

`app/core/document_pipeline.py` deterministically derives a plausible OCR
confidence from a hash of the inputs -- there's no real OCR/security-scan
integration. It's isolated to one function specifically so a real
provider is a one-file change later.

### The mock backend seam for the frontend

The frontend (built in an earlier session) currently runs against its own
in-browser MSW mock implementing the same REST shape. This backend's API
is close but not byte-identical (notably: snake_case fields here vs.
camelCase in the frontend's TypeScript types, and `application_id` as the
natural id here vs. a separate generated `applicationNumber` there) --
wiring them together is a follow-up integration pass, not a rewrite of
either side.

## Validation against the dataset's ground truth

Two scripts cross-check our from-scratch implementations against the
bundle's historical outcomes, run over all 10,000 rows:

| Check | Script | Result |
|---|---|---|
| Policy engine reproduces `policy_results.csv` | `scripts/validate_policy.py` | **10,000 / 10,000 exact match** |
| Full router (policy + historical risk bands + evidence) reproduces `decision_routing.csv` | `scripts/validate_router.py` | **9,931 / 10,000 (99.3%)** |

The router's 69 misses are concentrated entirely in the historical
`LOW_DOCUMENT_CONFIDENCE` bucket. Investigating it: flagged vs.
non-flagged applications with OCR confidence in the same sub-0.8 range
have nearly identical mean OCR confidence and income-mismatch ratio (see
git history of `app/routing/evidence.py` for the analysis) -- i.e. the
original generator appears to have applied some randomness on top of the
threshold, which isn't recoverable from the released columns. Our own
evidence check instead implements the PRD's stated rule directly (an OCR
confidence floor, `settings.ocr_confidence_floor = 0.7`) rather than
curve-fitting to that noise.

## ML models

Trained on the historical dataset's `actual_default_label` (credit) and
`actual_fraud_label`/`fraud_label` (fraud) as ground truth. Logistic
Regression, Random Forest, and XGBoost are all trained and compared
(`app/ml/train.py`); the best by PR-AUC on a held-out 30% split is saved
as the serving artifact for each target. Full comparison in
`artifacts/models/training_report.json` after running `python -m
app.ml.train`.

**Fraud model is near-perfectly separable** (PR-AUC ~0.99-1.0 across all
three algorithms) -- this reflects a clean/rule-like fraud pattern in
this synthetic dataset, not a bug (see the training report). One real
consequence worth flagging: a model this confident is also *overconfident*
on inputs outside its training distribution -- e.g. a genuinely new live
applicant defaults to `relationship_months=0`/no prior applications, and
the model can swing to a near-1.0 fraud probability on that alone. The
PRD scopes this MVP to *existing* salaried customers, so
`POST /applications` accepts `relationship_months` and callers should
supply the applicant's real banking tenure rather than leaving it at the
default. Recalibration (Platt/isotonic scaling) would be the right fix
before any real use.

**Credit (default) model is much harder** -- PR-AUC ~0.12 vs. a 3.8% base
rate (roughly 3x lift, but far from clean separation), which is a far
more realistic-looking difficulty level for a credit-default problem and
suggests the fraud pattern's cleanliness is a property of the dataset
rather than of our pipeline.

## API surface

Matches the PRD's listed surface:

```
POST/GET/PATCH /applications
POST/GET       /applications/{id}/documents
POST           /applications/{id}/agent/run
GET            /applications/{id}/agent/events
GET            /applications/{id}/audit-events        (extra, for the reconstructable trail)
GET/POST       /reviews, /reviews/{id}/decision
POST           /applications/{id}/credit-score | fraud-score | policy-evaluate
POST/GET       /applications/{id}/offer
POST           /applications/{id}/offer/accept
POST           /applications/{id}/agreement
POST           /applications/{id}/disbursal            (mock only)
```

## What's NOT built yet

Real OCR/document verification, real device/geolocation fraud signals
(current fraud features approximate device reuse/velocity at the
customer level, not device/IP level -- see
`app/ml/fraud_feature_builder.py`), auth/RBAC, an actual LLM in the agent
loop, and frontend↔backend wiring.
