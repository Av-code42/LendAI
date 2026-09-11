# LendAI Frontend

Customer loan-application flow and underwriter human-review console for
the LendAI MVP, built against the API surface defined in the PRD. The
real backend doesn't exist yet, so this app runs against a **mock API
layer** ([MSW](https://mswjs.io)) that implements the same REST contract
in-browser (`src/mocks/handlers.ts`) — swapping in the real backend later
should not require changing any component code, only removing the mock
worker bootstrap in `src/main.tsx`.

## Stack

- React 18 + TypeScript + Vite
- Tailwind CSS (design tokens in `tailwind.config.js`)
- React Router for routing between the customer and underwriter surfaces
- TanStack Query for data fetching/caching/mutations
- React Hook Form + Zod for form validation
- MSW for the mock API layer, seeded with data shaped to match
  `dataset_summary.json` and the PRD's 8 golden test cases

## Getting started

```bash
npm install
npm run dev
```

Then open the printed local URL. It redirects to `/customer` — use the
Customer/Underwriter switcher in the top nav to jump to the review
console at `/review`.

```bash
npm run build     # type-check + production build
npm run preview   # serve the production build locally
npm run lint      # type-check only
```

## What's implemented

**Customer flow** (`src/features/customer`):
- Application dashboard (list + status)
- New application form
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

## Mock data & API

`src/mocks/seed/data.ts` seeds ~14 applications, including all 8 PRD
golden cases (clean auto-approve, high/medium fraud, policy failure, high
credit risk, missing document, low OCR confidence, blocked agent action)
so every application state is reachable without manually driving an
application through the whole pipeline. `src/mocks/store.ts` is an
in-memory mock "backend" — it owns the decision/routing logic so the UI
layer never computes an approve/decline decision itself, consistent with
the PRD's core rule. State resets on page reload by design.

`src/api/client.ts` + `src/api/queries.ts` are the seam where a real
backend plugs in — no other file talks to `fetch` directly.

## Not yet built

Backend, database, real ML/fraud models, real document OCR pipeline, and
auth/RBAC. The role switcher in the top nav is a demo convenience, not
real authentication.
