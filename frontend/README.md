# LendAI Frontend

Customer loan-application flow and underwriter human-review console for
the LendAI MVP, talking to the real backend (`../backend`) — a Python/
FastAPI service backed by Postgres, running against the actual 10,000-row
synthetic dataset. This app no longer runs a mock API layer.

## Stack

- React 18 + TypeScript + Vite
- Tailwind CSS (design tokens in `tailwind.config.js`)
- React Router for routing between the customer and underwriter surfaces
- TanStack Query for data fetching/caching/mutations
- React Hook Form + Zod for form validation

## Getting started

```bash
npm install
npm run dev
```

By default this points at the deployed backend
(`https://lendaibackend-three.vercel.app`). To point at a locally-running
backend instead, create `.env.local`:

```bash
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
```

(see `../backend/README.md` to run that locally). Then open the printed
local URL — it redirects to `/customer`; use the Customer/Underwriter
switcher in the top nav to jump to the review console at `/review`.

```bash
npm run build     # type-check + production build
npm run preview   # serve the production build locally
npm run lint      # type-check only
```

## What's implemented

**Customer flow** (`src/features/customer`):
- Application dashboard (list + status)
- New application form — collects the applicant fields the real policy/
  credit engine actually needs (age, bureau score, employment tenure,
  banking relationship tenure, active loans, existing EMI), not just the
  loan amount/purpose
- Application detail page: state-machine stepper, document upload,
  running evidence collection ("agent run"), credit/fraud scores, policy
  rule breakdown, offer acceptance, e-agreement signature, mock disbursal,
  and the full agent activity timeline

**Underwriter console** (`src/features/underwriter`):
- Review queue (open vs. decided cases)
- Review detail: evidence, scores, failed policy rules, document
  confidence, agent recommendation, and the decision form (APPROVE /
  REJECT / REQUEST_INFORMATION / MODIFY_OFFER / ESCALATE) with mandatory
  reason code + comment

## The backend integration seam

`src/api/client.ts` is the only file that calls `fetch` directly (base
URL from `VITE_API_BASE_URL`, see above). `src/api/mappers.ts` translates
the backend's actual snake_case JSON (see
`../backend/app/schemas/api.py`) into this frontend's existing camelCase
domain types (`src/types/domain.ts`) — every screen/component is written
against those types and doesn't know or care that the wire format
differs. A few real shape differences the mappers absorb rather than
components handling directly:
- Backend document status is always `"UPLOADED"` (no rich pipeline
  states) — "needs re-upload" is synthesized from `ocr_confidence` being
  below the backend's own floor, the actual signal it uses internally.
- Historical (bulk-imported) customers have no PII by design (the PRD's
  PII-minimisation guardrail) — null `full_name`/`email`/`phone` get
  friendly placeholders instead of blanks.
- `agentRecommendation` isn't a field on the backend's Application at all
  (only reconstructable from the agent event log) — left undefined;
  every component reading it already handles that gracefully.

Document types were also corrected to match the real dataset/backend
(`PAN` / `SALARY_SLIP` / `BANK_STATEMENT`) — the original mock had
guessed at `PAN_CARD` / `AADHAAR` / `SELFIE` before the real backend
existed.

## A bug the real backend integration surfaced

`TextInput`/`Select` (`src/components/ui/Field.tsx`) weren't wrapped in
`React.forwardRef`, so React silently dropped the `ref` react-hook-form's
`register()` needs to read a field's value at submit time — every
registered field would read as empty/`NaN` on submit regardless of what
was visibly typed. This had been latent since the form was first built
(the mock-era testing never drove a real submit through Playwright); it's
fixed now and both components are `forwardRef`-wrapped.

## Not yet built

Real device/geolocation fraud signals (the backend approximates them at
the customer level for live applications — see
`../backend/app/ml/fraud_feature_builder.py`), real OCR/document
verification, and auth/RBAC. The role switcher in the top nav is a demo
convenience, not real authentication.
