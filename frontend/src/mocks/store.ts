import * as seed from "@/mocks/seed/data";
import { nextId } from "@/mocks/seed/data";
import { POLICY_VERSION } from "@/lib/policy";
import type {
  Agreement,
  AgentEvent,
  ApplicationStatus,
  AuditEvent,
  DocumentRecord,
  DocumentType,
  HumanReviewCase,
  LoanApplication,
  ModelOutput,
  Offer,
  PolicyResult,
  ReviewDecision,
} from "@/types/domain";

/**
 * In-memory mock "backend". This is a stand-in for the real API described
 * in the PRD -- it deliberately keeps decision logic (policy thresholds,
 * routing) server-side (i.e. here, not in React components) so the UI
 * layer only ever renders results, matching the PRD's core rule that the
 * frontend/agent never makes the authoritative decision.
 *
 * State resets on page reload. This is intentional for an MVP frontend
 * milestone -- swapping this module for real HTTP calls is the seam where
 * the real backend plugs in later.
 */

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function appendAudit(applicationId: string, actor: string, action: string, detail: string) {
  seed.auditEvents.push({
    id: nextId("aud"),
    applicationId,
    actor,
    action,
    detail,
    createdAt: new Date().toISOString(),
  });
}

function appendAgentEvent(
  applicationId: string,
  partial: Omit<AgentEvent, "id" | "applicationId" | "step" | "createdAt">
) {
  const step = seed.agentEvents.filter((e) => e.applicationId === applicationId).length + 1;
  seed.agentEvents.push({
    id: nextId("evt"),
    applicationId,
    step,
    createdAt: new Date().toISOString(),
    ...partial,
  });
}

function touch(app: LoanApplication) {
  app.updatedAt = new Date().toISOString();
}

export const store = {
  listApplications(): LoanApplication[] {
    return clone(seed.applications).sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  },

  getApplication(id: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === id);
    return app ? clone(app) : undefined;
  },

  createApplication(input: {
    requestedAmount: number;
    tenureMonths: number;
    purpose: string;
    fullName: string;
    email: string;
    phone: string;
    monthlyIncome: number;
  }): LoanApplication {
    const customerId = nextId("cust");
    const applicationId = nextId("app");
    const now = new Date().toISOString();
    const app: LoanApplication = {
      id: applicationId,
      applicationNumber: `LN-2026-${(seed.applications.length + 1000).toString().padStart(5, "0")}`,
      customerId,
      customer: {
        id: customerId,
        fullName: input.fullName,
        email: input.email,
        phone: input.phone,
      },
      status: "DRAFT",
      requestedAmount: input.requestedAmount,
      tenureMonths: input.tenureMonths,
      purpose: input.purpose,
      submittedAt: null,
      updatedAt: now,
      createdAt: now,
      policyVersion: POLICY_VERSION,
      documents: [],
    };
    seed.applications.unshift(app);
    appendAudit(applicationId, input.fullName, "APPLICATION_CREATED", "Draft application created.");
    return clone(app);
  },

  updateApplication(id: string, patch: Partial<LoanApplication>): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === id);
    if (!app) return undefined;
    Object.assign(app, patch);
    touch(app);
    return clone(app);
  },

  submitApplication(id: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === id);
    if (!app) return undefined;
    app.status = "SUBMITTED";
    app.submittedAt = new Date().toISOString();
    touch(app);
    appendAudit(id, app.customer.fullName, "APPLICATION_SUBMITTED", "Customer submitted application for processing.");
    appendAgentEvent(id, {
      type: "TOOL_CALL",
      toolName: "fetch_customer_profile",
      detail: "Fetched verified customer profile from core banking.",
    });
    return clone(app);
  },

  addDocument(
    applicationId: string,
    type: DocumentType,
    fileName: string
  ): DocumentRecord | undefined {
    const app = seed.applications.find((a) => a.id === applicationId);
    if (!app) return undefined;
    const doc: DocumentRecord = {
      id: nextId("doc"),
      applicationId,
      type,
      status: "UPLOADED",
      fileName,
      uploadedAt: new Date().toISOString(),
    };
    app.documents.push(doc);
    if (app.status === "SUBMITTED") {
      app.status = "DATA_COLLECTION";
    }
    touch(app);
    appendAudit(applicationId, app.customer.fullName, "DOCUMENT_UPLOADED", `Uploaded ${type} (${fileName}).`);
    appendAgentEvent(applicationId, {
      type: "TOOL_CALL",
      toolName: "document_pipeline",
      detail: `Queued ${type} for security scan, OCR, classification and extraction.`,
    });

    // Simulate async pipeline completing shortly after upload.
    setTimeout(() => {
      const confidence = 0.85 + Math.random() * 0.14;
      doc.status = confidence < 0.7 ? "NEEDS_REUPLOAD" : "VALIDATED";
      doc.ocrConfidence = Number(confidence.toFixed(2));
      appendAgentEvent(applicationId, {
        type: "EVIDENCE_ANALYSIS",
        detail: `OCR confidence ${(confidence * 100).toFixed(0)}% for ${type}. ${
          doc.status === "VALIDATED" ? "Validated." : "Below threshold -- flagged for re-upload."
        }`,
      });
    }, 1200);

    return clone(doc);
  },

  runAgent(applicationId: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === applicationId);
    if (!app) return undefined;

    if (app.documents.length === 0 || app.documents.some((d) => d.status === "NEEDS_REUPLOAD")) {
      app.status = "WAITING_FOR_DOCUMENT";
      touch(app);
      appendAgentEvent(applicationId, {
        type: "RECOMMENDATION",
        detail: "Evidence incomplete or low-confidence -- requesting document(s) before proceeding.",
      });
      return clone(app);
    }

    app.status = "VERIFICATION";
    touch(app);

    // Deterministic pseudo-scoring from the mocked customer profile, purely
    // for a believable demo -- real scoring happens in the ML service.
    const seedNum = applicationId.split("_")[1] ?? "1";
    const pseudoRandom = (Array.from(seedNum).reduce((a, c) => a + c.charCodeAt(0), 0) % 100) / 100;

    const credit: ModelOutput = {
      id: nextId("mo"),
      applicationId,
      modelType: "CREDIT",
      modelName: "XGBOOST",
      modelVersion: "credit-v1.3.0",
      score: Number((pseudoRandom * 0.4).toFixed(2)),
      riskLevel: pseudoRandom > 0.6 ? "HIGH" : pseudoRandom > 0.3 ? "MEDIUM" : "LOW",
      scoredAt: new Date().toISOString(),
    };
    const fraud: ModelOutput = {
      id: nextId("mo"),
      applicationId,
      modelType: "FRAUD",
      modelName: "XGBOOST",
      modelVersion: "fraud-v1.1.0",
      score: Number(((1 - pseudoRandom) * 0.3).toFixed(2)),
      riskLevel: pseudoRandom < 0.2 ? "HIGH" : pseudoRandom < 0.4 ? "MEDIUM" : "LOW",
      scoredAt: new Date().toISOString(),
    };
    seed.modelOutputs.push(credit, fraud);
    app.latestCreditScore = credit;
    app.latestFraudScore = fraud;
    app.status = "RISK_ASSESSMENT";
    appendAgentEvent(applicationId, { type: "TOOL_CALL", toolName: "credit_score", detail: `Invoked credit model ${credit.modelName}.` });
    appendAgentEvent(applicationId, { type: "TOOL_CALL", toolName: "fraud_score", detail: `Invoked fraud model ${fraud.modelName}.` });

    const policyResult = evaluatePolicyInternal(app);
    seed.policyResults.push(policyResult);
    app.policyResult = policyResult;
    app.status = "POLICY_EVALUATION";
    appendAgentEvent(applicationId, { type: "TOOL_CALL", toolName: "policy_evaluate", detail: `Evaluated policy ${POLICY_VERSION}.` });

    // Deterministic decision router mirroring the PRD's routing order.
    let finalStatus: ApplicationStatus;
    let recommendationAction: LoanApplication["agentRecommendation"];
    const reasonCodes: string[] = [];

    if (fraud.riskLevel === "HIGH") {
      finalStatus = "HUMAN_REVIEW";
      reasonCodes.push("HIGH_FRAUD_RISK");
    } else if (!policyResult.overallPass) {
      finalStatus = "DECLINED";
      reasonCodes.push(...policyResult.rules.filter((r) => !r.pass).map((r) => r.reasonCode!));
    } else if (credit.riskLevel === "HIGH") {
      finalStatus = "HUMAN_REVIEW";
      reasonCodes.push("HIGH_CREDIT_RISK");
    } else if (fraud.riskLevel === "MEDIUM") {
      finalStatus = "HUMAN_REVIEW";
      reasonCodes.push("MEDIUM_FRAUD_RISK");
    } else {
      finalStatus = "AUTO_APPROVED";
      reasonCodes.push("ALL_POLICY_RULES_PASS", "LOW_FRAUD_RISK", "LOW_CREDIT_RISK");
    }

    recommendationAction = {
      action:
        finalStatus === "AUTO_APPROVED"
          ? "AUTO_APPROVE"
          : finalStatus === "DECLINED"
          ? "DECLINE"
          : "HUMAN_REVIEW",
      reasonCodes,
      summary: buildRecommendationSummary(finalStatus, reasonCodes),
    };
    app.agentRecommendation = recommendationAction;
    appendAgentEvent(applicationId, { type: "RECOMMENDATION", detail: recommendationAction.summary });

    app.status = finalStatus;
    touch(app);

    if (finalStatus === "HUMAN_REVIEW") {
      seed.humanReviewCases.push({
        id: nextId("rev"),
        applicationId,
        application: clone(app),
        status: "OPEN",
        triggerReasons: reasonCodes,
        createdAt: new Date().toISOString(),
      });
      appendAgentEvent(applicationId, { type: "REVIEW_CASE_CREATED", detail: `Created human review case: ${reasonCodes.join(", ")}.` });
    }

    if (finalStatus === "AUTO_APPROVED") {
      const offer = createOfferInternal(app);
      seed.offers.push(offer);
      app.offer = offer;
      app.status = "OFFER";
    }

    appendAudit(applicationId, "agent", "AGENT_RUN_COMPLETE", `Routed to ${app.status}.`);
    return clone(app);
  },

  listAgentEvents(applicationId: string): AgentEvent[] {
    return clone(seed.agentEvents.filter((e) => e.applicationId === applicationId)).sort(
      (a, b) => a.step - b.step
    );
  },

  listAuditEvents(applicationId: string): AuditEvent[] {
    return clone(seed.auditEvents.filter((e) => e.applicationId === applicationId)).sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
    );
  },

  listReviewCases(): HumanReviewCase[] {
    return clone(seed.humanReviewCases).sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  },

  getReviewCase(id: string): HumanReviewCase | undefined {
    const found = seed.humanReviewCases.find((r) => r.id === id);
    if (!found) return undefined;
    const app = seed.applications.find((a) => a.id === found.applicationId);
    if (app) found.application = app;
    return clone(found);
  },

  decideReview(
    id: string,
    decision: Omit<ReviewDecision, "decidedAt">
  ): HumanReviewCase | undefined {
    const reviewCase = seed.humanReviewCases.find((r) => r.id === id);
    if (!reviewCase) return undefined;
    const app = seed.applications.find((a) => a.id === reviewCase.applicationId);
    if (!app) return undefined;

    reviewCase.decision = { ...decision, decidedAt: new Date().toISOString() };
    reviewCase.status = "CLOSED";

    switch (decision.action) {
      case "APPROVE": {
        app.status = "OFFER";
        const offer = createOfferInternal(app);
        seed.offers.push(offer);
        app.offer = offer;
        break;
      }
      case "REJECT":
        app.status = "DECLINED";
        break;
      case "REQUEST_INFORMATION":
        app.status = "WAITING_FOR_DOCUMENT";
        break;
      case "MODIFY_OFFER": {
        app.status = "OFFER";
        const offer = createOfferInternal(app, decision.modifiedOfferAmount);
        seed.offers.push(offer);
        app.offer = offer;
        break;
      }
      case "ESCALATE":
        // Stays in HUMAN_REVIEW conceptually but this case is closed;
        // in a full backend this would open a new, higher-tier case.
        app.status = "HUMAN_REVIEW";
        reviewCase.status = "OPEN";
        break;
    }
    touch(app);
    appendAudit(
      app.id,
      decision.userName,
      `REVIEW_${decision.action}`,
      `${decision.comment} (reason: ${decision.reasonCode})`
    );
    appendAgentEvent(app.id, {
      type: "RECOMMENDATION",
      detail: `Underwriter ${decision.userName} recorded decision ${decision.action}.`,
    });
    return clone(reviewCase);
  },

  acceptOffer(applicationId: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === applicationId);
    if (!app || !app.offer) return undefined;
    app.offer.status = "ACCEPTED";
    app.status = "AGREEMENT";
    app.agreement = { id: nextId("agr"), applicationId, status: "PENDING_SIGNATURE" };
    seed.agreements.push(app.agreement);
    touch(app);
    appendAudit(applicationId, app.customer.fullName, "OFFER_ACCEPTED", "Customer accepted the offer.");
    return clone(app);
  },

  signAgreement(applicationId: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === applicationId);
    if (!app || !app.agreement) return undefined;
    app.agreement.status = "SIGNED";
    app.agreement.signedAt = new Date().toISOString();
    app.agreement.documentUrl = "#";
    touch(app);
    appendAudit(applicationId, app.customer.fullName, "AGREEMENT_SIGNED", "Customer completed e-signature.");
    return clone(app);
  },

  disburse(applicationId: string): LoanApplication | undefined {
    const app = seed.applications.find((a) => a.id === applicationId);
    if (!app || !app.agreement || app.agreement.status !== "SIGNED") return undefined;
    app.status = "MOCK_DISBURSAL";
    touch(app);
    appendAudit(applicationId, "system", "MOCK_DISBURSAL", "Funds mock-disbursed to linked account.");
    return clone(app);
  },
};

function evaluatePolicyInternal(app: LoanApplication): PolicyResult {
  // NOTE: mock-only reconstruction of PL_2026_V1 for demo purposes. The
  // seed customer fields the real app would have collected during
  // DATA_COLLECTION aren't all present on LoanApplication here, so this
  // uses believable derived values consistent with the request.
  const amountMultiple = app.requestedAmount / (app.requestedAmount / 6); // placeholder unless customer income known
  const rules: PolicyResult["rules"] = [
    { ruleCode: "AGE_RANGE", label: "Age between 21-60", pass: true, actualValue: 32, threshold: "21-60" },
    { ruleCode: "MIN_INCOME", label: "Monthly income >= 50,000", pass: true, actualValue: 75000, threshold: 50000 },
    { ruleCode: "BUREAU_SCORE", label: "Bureau score >= 700", pass: true, actualValue: 735, threshold: 700 },
    { ruleCode: "FOIR", label: "FOIR <= 50%", pass: true, actualValue: "38%", threshold: "50%" },
    { ruleCode: "EMPLOYMENT_TENURE", label: "Employment tenure >= 6 months", pass: true, actualValue: 24, threshold: 6 },
    {
      ruleCode: "MAX_AMOUNT",
      label: "Requested amount <= 8x monthly income",
      pass: app.requestedAmount <= 8 * 75000,
      actualValue: app.requestedAmount,
      threshold: 8 * 75000,
    },
  ];
  const overallPass = rules.every((r) => r.pass);
  rules.forEach((r) => {
    if (!r.pass) r.reasonCode = `POLICY_${r.ruleCode}_FAIL`;
  });
  return {
    id: nextId("pol"),
    applicationId: app.id,
    policyVersion: POLICY_VERSION,
    overallPass,
    rules,
    evaluatedAt: new Date().toISOString(),
  };
}

function buildRecommendationSummary(status: ApplicationStatus, reasonCodes: string[]): string {
  switch (status) {
    case "AUTO_APPROVED":
      return "All policy rules pass and credit/fraud risk are both low. Recommending auto-approval.";
    case "DECLINED":
      return `Policy evaluation failed (${reasonCodes.join(", ")}). Routing to decline.`;
    case "HUMAN_REVIEW":
      return `Routing to mandatory human review (${reasonCodes.join(", ")}).`;
    default:
      return "Evidence incomplete.";
  }
}

function createOfferInternal(app: LoanApplication, overrideAmount?: number): Offer {
  const principal = overrideAmount ?? app.requestedAmount;
  const rate = 13.5;
  const monthlyRate = rate / 12 / 100;
  const n = app.tenureMonths;
  const emi = (principal * monthlyRate * Math.pow(1 + monthlyRate, n)) / (Math.pow(1 + monthlyRate, n) - 1);
  return {
    id: nextId("off"),
    applicationId: app.id,
    approvedAmount: principal,
    interestRateApr: rate,
    tenureMonths: n,
    monthlyInstallment: Math.round(emi),
    processingFee: Math.round(principal * 0.01),
    status: "PENDING",
    expiresAt: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    createdAt: new Date().toISOString(),
  };
}
