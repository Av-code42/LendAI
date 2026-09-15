/**
 * Domain types for LendAI, mirrored from the PRD data model:
 * customers, applications, transactions, documents, fraud_features,
 * model_outputs, policy_results, human_review_cases, offers, agreements,
 * agent_events, audit_events.
 *
 * The frontend never computes decisions itself -- it only renders what
 * the (mocked, later real) backend returns. This keeps the UI honest to
 * the PRD's core rule: LLM/ML/policy layers decide, humans review,
 * the frontend just presents evidence and captures actions.
 */

export type ApplicationStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "DATA_COLLECTION"
  | "VERIFICATION"
  | "RISK_ASSESSMENT"
  | "POLICY_EVALUATION"
  | "AUTO_APPROVED"
  | "HUMAN_REVIEW"
  | "DECLINED"
  | "OFFER"
  | "AGREEMENT"
  | "MOCK_DISBURSAL"
  | "WAITING_FOR_DOCUMENT";

export const APPLICATION_STATUS_ORDER: ApplicationStatus[] = [
  "DRAFT",
  "SUBMITTED",
  "DATA_COLLECTION",
  "VERIFICATION",
  "RISK_ASSESSMENT",
  "POLICY_EVALUATION",
  "HUMAN_REVIEW",
  "OFFER",
  "AGREEMENT",
  "MOCK_DISBURSAL",
];

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface Customer {
  id: string;
  fullName: string;
  email: string;
  phone: string;
  dateOfBirth: string; // ISO date
  employmentType: "SALARIED";
  employerName: string;
  employmentTenureMonths: number;
  monthlyIncome: number;
  bureauScore: number;
  accountAgeMonths: number;
  createdAt: string;
}

export interface LoanApplication {
  id: string;
  applicationNumber: string;
  customerId: string;
  customer: Pick<Customer, "id" | "fullName" | "email" | "phone">;
  status: ApplicationStatus;
  requestedAmount: number;
  tenureMonths: number;
  purpose: string;
  submittedAt: string | null;
  updatedAt: string;
  createdAt: string;
  policyVersion: string;
  latestCreditScore?: ModelOutput;
  latestFraudScore?: ModelOutput;
  policyResult?: PolicyResult;
  agentRecommendation?: AgentRecommendation;
  documents: DocumentRecord[];
  offer?: Offer;
  agreement?: Agreement;
}

export interface ModelOutput {
  id: string;
  applicationId: string;
  modelType: "CREDIT" | "FRAUD";
  modelName: "LOGISTIC_REGRESSION" | "RANDOM_FOREST" | "XGBOOST";
  modelVersion: string;
  score: number; // 0-1 probability of adverse outcome (default / fraud)
  riskLevel: RiskLevel;
  featureContributions?: { feature: string; contribution: number }[];
  scoredAt: string;
}

export interface PolicyRuleResult {
  ruleCode: string;
  label: string;
  pass: boolean;
  actualValue: string | number;
  threshold: string | number;
  reasonCode?: string;
}

export interface PolicyResult {
  id: string;
  applicationId: string;
  policyVersion: string;
  overallPass: boolean;
  rules: PolicyRuleResult[];
  evaluatedAt: string;
}

export type DocumentType =
  | "PAN_CARD"
  | "AADHAAR"
  | "SALARY_SLIP"
  | "BANK_STATEMENT"
  | "SELFIE";

export type DocumentStatus =
  | "UPLOADED"
  | "SCANNING"
  | "OCR_PROCESSING"
  | "CLASSIFIED"
  | "EXTRACTED"
  | "VALIDATED"
  | "REJECTED"
  | "NEEDS_REUPLOAD";

export interface DocumentRecord {
  id: string;
  applicationId: string;
  type: DocumentType;
  status: DocumentStatus;
  fileName: string;
  ocrConfidence?: number; // 0-1
  extractedFields?: Record<string, string>;
  mismatchFlags?: string[];
  uploadedAt: string;
}

export type AgentRecommendationAction =
  | "AUTO_APPROVE"
  | "HUMAN_REVIEW"
  | "DECLINE"
  | "REQUEST_DOCUMENT";

export interface AgentRecommendation {
  action: AgentRecommendationAction;
  reasonCodes: string[];
  summary: string;
}

export interface AgentEvent {
  id: string;
  applicationId: string;
  step: number;
  type:
    | "TOOL_CALL"
    | "TOOL_RESULT"
    | "EVIDENCE_ANALYSIS"
    | "REVIEW_CASE_CREATED"
    | "RECOMMENDATION"
    | "BLOCKED_ACTION";
  toolName?: string;
  detail: string;
  createdAt: string;
}

export type ReviewAction =
  | "APPROVE"
  | "REJECT"
  | "REQUEST_INFORMATION"
  | "MODIFY_OFFER"
  | "ESCALATE";

export interface HumanReviewCase {
  id: string;
  applicationId: string;
  application: LoanApplication;
  status: "OPEN" | "CLOSED";
  triggerReasons: string[];
  createdAt: string;
  decision?: ReviewDecision;
}

export interface ReviewDecision {
  userId: string;
  userName: string;
  action: ReviewAction;
  reasonCode: string;
  comment: string;
  modifiedOfferAmount?: number;
  decidedAt: string;
}

export interface Offer {
  id: string;
  applicationId: string;
  approvedAmount: number;
  interestRateApr: number;
  tenureMonths: number;
  monthlyInstallment: number;
  processingFee: number;
  status: "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED";
  expiresAt: string;
  createdAt: string;
}

export interface Agreement {
  id: string;
  applicationId: string;
  status: "PENDING_SIGNATURE" | "SIGNED";
  signedAt?: string;
  documentUrl?: string;
}

export interface AuditEvent {
  id: string;
  applicationId: string;
  actor: string;
  action: string;
  detail: string;
  createdAt: string;
}
