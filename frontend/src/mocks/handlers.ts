import { http, HttpResponse, delay } from "msw";
import { store } from "@/mocks/store";
import type { DocumentType, ReviewAction } from "@/types/domain";

/**
 * Mock implementation of the API surface listed in the PRD:
 *   POST/GET/PATCH /applications
 *   POST/GET /applications/{id}/documents
 *   POST /applications/{id}/agent/run
 *   GET /applications/{id}/agent/events
 *   GET /reviews/{id}; POST /reviews/{id}/decision
 *   POST /applications/{id}/credit-score | fraud-score | policy-evaluate
 *   POST/GET /applications/{id}/offer; POST /applications/{id}/offer/accept
 *   POST /applications/{id}/agreement
 *   POST /applications/{id}/disbursal (mock only)
 *
 * This stands in for the real backend so the frontend can be built and
 * demoed independently. Swap `src/api/client.ts`'s base URL / remove this
 * worker once the real service exists -- component code does not change.
 */

const LATENCY_MS = 220;

export const handlers = [
  http.get("/api/applications", async () => {
    await delay(LATENCY_MS);
    return HttpResponse.json(store.listApplications());
  }),

  http.post("/api/applications", async ({ request }) => {
    await delay(LATENCY_MS);
    const body = (await request.json()) as any;
    const app = store.createApplication(body);
    return HttpResponse.json(app, { status: 201 });
  }),

  http.get("/api/applications/:id", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.getApplication(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.patch("/api/applications/:id", async ({ params, request }) => {
    await delay(LATENCY_MS);
    const body = (await request.json()) as any;
    const app = store.updateApplication(params.id as string, body);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.post("/api/applications/:id/submit", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.submitApplication(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.get("/api/applications/:id/documents", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.getApplication(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app.documents);
  }),

  http.post("/api/applications/:id/documents", async ({ params, request }) => {
    await delay(LATENCY_MS);
    const body = (await request.json()) as { type: DocumentType; fileName: string };
    const doc = store.addDocument(params.id as string, body.type, body.fileName);
    if (!doc) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(doc, { status: 201 });
  }),

  http.post("/api/applications/:id/agent/run", async ({ params }) => {
    await delay(LATENCY_MS * 2);
    const app = store.runAgent(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.get("/api/applications/:id/agent/events", async ({ params }) => {
    await delay(LATENCY_MS);
    return HttpResponse.json(store.listAgentEvents(params.id as string));
  }),

  http.get("/api/applications/:id/audit-events", async ({ params }) => {
    await delay(LATENCY_MS);
    return HttpResponse.json(store.listAuditEvents(params.id as string));
  }),

  http.get("/api/reviews", async () => {
    await delay(LATENCY_MS);
    return HttpResponse.json(store.listReviewCases());
  }),

  http.get("/api/reviews/:id", async ({ params }) => {
    await delay(LATENCY_MS);
    const review = store.getReviewCase(params.id as string);
    if (!review) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(review);
  }),

  http.post("/api/reviews/:id/decision", async ({ params, request }) => {
    await delay(LATENCY_MS);
    const body = (await request.json()) as {
      userId: string;
      userName: string;
      action: ReviewAction;
      reasonCode: string;
      comment: string;
      modifiedOfferAmount?: number;
    };
    const review = store.decideReview(params.id as string, body);
    if (!review) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(review);
  }),

  http.post("/api/applications/:id/offer/accept", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.acceptOffer(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.post("/api/applications/:id/agreement", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.signAgreement(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),

  http.post("/api/applications/:id/disbursal", async ({ params }) => {
    await delay(LATENCY_MS);
    const app = store.disburse(params.id as string);
    if (!app) return HttpResponse.json({ message: "Not found" }, { status: 404 });
    return HttpResponse.json(app);
  }),
];
