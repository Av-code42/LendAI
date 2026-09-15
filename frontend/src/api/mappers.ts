/**
 * Translates the real backend's snake_case JSON shapes (see
 * ../../../backend/app/schemas/api.py) into this frontend's existing
 * camelCase domain types (src/types/domain.ts). This is the seam
 * anticipated when the frontend was first built against a mock API --
 * every screen/component keeps working unchanged; only this file and
 * api/queries.ts know the backend's actual wire format.
 *
 * A few real shape differences from what the mock originally assumed,
 * absorbed here rather than in components:
 * - Backend document status is always "UPLOADED" (no rich pipeline
 *   states) -- "needs re-upload" is instead synthesized from
 *   ocr_confidence being below the backend's own floor (0.7), which is
 *   the actual signal the backend's evidence check uses.
 * - Historical (bulk-imported) customers have no PII (full_name/email/
 *   phone are null) by design -- see the PRD's PII-minimisation
 *   guardrail -- so those get friendly placeholders instead of blanks.
 * - agentRecommendation isn't a field on the backend's Application at
 *   all (only reconstructable from the agent event log) -- left
 *   undefined; every component that reads it already handles that.
 */

import type {
  AgentEvent,
  Agreement,
  AuditEvent,
  DocumentRecord,
  DocumentType,
  HumanReviewCase,
  LoanApplication,
  ModelOutput,
  Offer,
  PolicyResult,
} from "@/types/domain";

const OCR_CONFIDENCE_FLOOR = 0.7;
const INCOME_MISMATCH_FLAG_THRESHOLD = 0.15;

export function mapModelOutput(mo: any): ModelOutput {
  return {
    id: String(mo.id),
    applicationId: mo.application_id,
    modelType: mo.model_type,
    modelName: mo.model_name,
    modelVersion: mo.model_version,
    score: mo.score,
    riskLevel: mo.risk_level,
    scoredAt: mo.scored_at,
  };
}

export function mapPolicyResult(pr: any): PolicyResult {
  return {
    id: String(pr.id),
    applicationId: pr.application_id,
    policyVersion: pr.policy_version,
    overallPass: pr.overall_pass,
    rules: (pr.rules ?? []).map((r: any) => ({
      ruleCode: r.rule_code,
      label: r.label,
      pass: r.pass,
      actualValue: r.actual_value,
      threshold: r.threshold,
      reasonCode: r.reason_code ?? undefined,
    })),
    evaluatedAt: pr.evaluated_at,
  };
}

export function mapDocument(d: any): DocumentRecord {
  const mismatchFlags: string[] = [];
  if (d.name_match === false) mismatchFlags.push("NAME_MISMATCH");
  if (d.income_mismatch_ratio != null && d.income_mismatch_ratio > INCOME_MISMATCH_FLAG_THRESHOLD) {
    mismatchFlags.push("INCOME_MISMATCH");
  }
  const lowConfidence = d.ocr_confidence != null && d.ocr_confidence < OCR_CONFIDENCE_FLOOR;

  return {
    id: String(d.id),
    applicationId: d.application_id,
    type: d.document_type as DocumentType,
    status: lowConfidence ? "NEEDS_REUPLOAD" : "VALIDATED",
    fileName: d.file_name ?? `${d.document_type}.pdf`,
    ocrConfidence: d.ocr_confidence ?? undefined,
    mismatchFlags: mismatchFlags.length ? mismatchFlags : undefined,
    uploadedAt: d.uploaded_at,
  };
}

export function mapOffer(o: any): Offer {
  return {
    id: String(o.id),
    applicationId: o.application_id,
    approvedAmount: o.approved_amount,
    interestRateApr: o.interest_rate_apr,
    tenureMonths: o.tenure_months,
    monthlyInstallment: o.monthly_installment,
    processingFee: o.processing_fee,
    status: o.status,
    expiresAt: o.expires_at,
    createdAt: o.created_at,
  };
}

export function mapAgreement(a: any): Agreement {
  return {
    id: String(a.id),
    applicationId: a.application_id,
    status: a.status,
    signedAt: a.signed_at ?? undefined,
    documentUrl: a.document_url ?? undefined,
  };
}

export function mapApplication(a: any): LoanApplication {
  return {
    id: a.application_id,
    applicationNumber: a.application_id,
    customerId: a.customer_id,
    customer: {
      id: a.customer.customer_id,
      fullName: a.customer.full_name ?? "Existing customer",
      email: a.customer.email ?? "—",
      phone: a.customer.phone ?? "—",
    },
    status: a.status,
    requestedAmount: a.requested_amount,
    tenureMonths: a.tenure_months,
    purpose: a.purpose,
    submittedAt: a.submitted_at,
    updatedAt: a.updated_at,
    createdAt: a.created_at,
    policyVersion: a.policy_version,
    latestCreditScore: a.latest_credit_score ? mapModelOutput(a.latest_credit_score) : undefined,
    latestFraudScore: a.latest_fraud_score ? mapModelOutput(a.latest_fraud_score) : undefined,
    policyResult: a.policy_result ? mapPolicyResult(a.policy_result) : undefined,
    agentRecommendation: undefined,
    documents: (a.documents ?? []).map(mapDocument),
    offer: a.offer ? mapOffer(a.offer) : undefined,
    agreement: a.agreement ? mapAgreement(a.agreement) : undefined,
  };
}

export function mapAgentEvent(e: any): AgentEvent {
  return {
    id: String(e.id),
    applicationId: e.application_id,
    step: e.step,
    type: e.type,
    toolName: e.tool_name ?? undefined,
    detail: e.detail,
    createdAt: e.created_at,
  };
}

export function mapAuditEvent(e: any): AuditEvent {
  return {
    id: String(e.id),
    applicationId: e.application_id,
    actor: e.actor,
    action: e.action,
    detail: e.detail,
    createdAt: e.created_at,
  };
}

export function mapHumanReviewCase(r: any): HumanReviewCase {
  return {
    id: r.review_id,
    applicationId: r.application_id,
    application: mapApplication(r.application),
    status: r.status,
    triggerReasons: r.review_reason ? String(r.review_reason).split("|") : [],
    createdAt: r.created_at,
    decision: r.decided_at
      ? {
          userId: r.decided_by_user_id ?? "",
          userName: r.decided_by_user_name ?? "",
          action: r.decision_action,
          reasonCode: r.decision_reason_code ?? "",
          comment: r.decision_comment ?? "",
          modifiedOfferAmount: r.modified_offer_amount ?? undefined,
          decidedAt: r.decided_at,
        }
      : undefined,
  };
}
