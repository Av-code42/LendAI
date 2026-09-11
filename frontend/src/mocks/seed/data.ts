import type {
  Agreement,
  AgentEvent,
  AgentRecommendation,
  AuditEvent,
  Customer,
  DocumentRecord,
  HumanReviewCase,
  LoanApplication,
  ModelOutput,
  Offer,
  PolicyResult,
} from "@/types/domain";
import { POLICY_VERSION } from "@/lib/policy";

/**
 * Synthetic seed data only -- shaped to match dataset_summary.json
 * (10,000 customers/applications, ~2.07% fraud rate, ~3.82% default rate,
 * 6203 auto-approve / 163 human review / 3634 decline) at demo scale, plus
 * the PRD's 8 golden test cases so every UI state is reachable.
 *
 * All names, incomes and scores are fabricated for development/demo use.
 * See PRD "Data disclaimer" -- not real bank policy or real customers.
 */

let idCounter = 1000;
export function nextId(prefix: string): string {
  idCounter += 1;
  return `${prefix}_${idCounter.toString(36)}`;
}

const now = new Date("2026-09-10T09:00:00+05:30");
const daysAgo = (n: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

interface Seeded {
  status: LoanApplication["status"];
  customer: Omit<Customer, "id" | "createdAt">;
  requestedAmount: number;
  tenureMonths: number;
  purpose: string;
  credit?: { score: number; risk: "LOW" | "MEDIUM" | "HIGH"; model: ModelOutput["modelName"] };
  fraud?: { score: number; risk: "LOW" | "MEDIUM" | "HIGH"; model: ModelOutput["modelName"] };
  policy?: { overallPass: boolean; failing?: string[] };
  documents?: Partial<DocumentRecord>[];
  agentRecommendation?: AgentRecommendation;
  reviewTrigger?: string[];
  reviewDecision?: HumanReviewCase["decision"];
  offer?: boolean;
  agreementSigned?: boolean;
  disbursed?: boolean;
  blockedAgentAction?: boolean;
  submittedDaysAgo: number;
  note: string;
}

const seeds: Seeded[] = [
  {
    // Golden case 1: clean low-risk -> auto approve
    status: "AUTO_APPROVED",
    customer: {
      fullName: "Ananya Sharma",
      email: "ananya.sharma@example.com",
      phone: "+91 98200 11223",
      dateOfBirth: "1992-04-12",
      employmentType: "SALARIED",
      employerName: "Nimbus Retail Pvt Ltd",
      employmentTenureMonths: 48,
      monthlyIncome: 95000,
      bureauScore: 782,
      accountAgeMonths: 60,
    },
    requestedAmount: 400000,
    tenureMonths: 36,
    purpose: "Home renovation",
    credit: { score: 0.04, risk: "LOW", model: "XGBOOST" },
    fraud: { score: 0.02, risk: "LOW", model: "XGBOOST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.98 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.97 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.95 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.96 },
    ],
    agentRecommendation: {
      action: "AUTO_APPROVE",
      reasonCodes: ["ALL_POLICY_RULES_PASS", "LOW_FRAUD_RISK", "LOW_CREDIT_RISK"],
      summary:
        "All policy rules pass, credit and fraud risk are both low, and all documents validated with high OCR confidence. Recommending auto-approval.",
    },
    offer: true,
    agreementSigned: true,
    disbursed: true,
    submittedDaysAgo: 6,
    note: "Golden case 1 — clean low-risk application, fully disbursed.",
  },
  {
    // Golden case 2: high fraud -> human review
    status: "HUMAN_REVIEW",
    customer: {
      fullName: "Rohit Verma",
      email: "rohit.verma@example.com",
      phone: "+91 90112 33445",
      dateOfBirth: "1989-11-02",
      employmentType: "SALARIED",
      employerName: "Kestrel Logistics",
      employmentTenureMonths: 22,
      monthlyIncome: 68000,
      bureauScore: 741,
      accountAgeMonths: 14,
    },
    requestedAmount: 500000,
    tenureMonths: 48,
    purpose: "Medical expenses",
    credit: { score: 0.11, risk: "LOW", model: "XGBOOST" },
    fraud: { score: 0.87, risk: "HIGH", model: "XGBOOST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.94 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.93 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.9, mismatchFlags: ["EMPLOYER_NAME_MISMATCH"] },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.91 },
    ],
    agentRecommendation: {
      action: "HUMAN_REVIEW",
      reasonCodes: ["HIGH_FRAUD_RISK", "DEVICE_REUSE", "INCOME_MISMATCH"],
      summary:
        "Fraud model flagged HIGH risk driven by device reuse across 3 recent applications and an income mismatch versus the submitted salary slip. Mandatory human review per policy.",
    },
    reviewTrigger: ["HIGH_FRAUD_RISK"],
    submittedDaysAgo: 2,
    note: "Golden case 2 — high fraud risk, mandatory human review.",
  },
  {
    // Golden case 3: medium fraud -> human review
    status: "HUMAN_REVIEW",
    customer: {
      fullName: "Priya Nair",
      email: "priya.nair@example.com",
      phone: "+91 97654 22110",
      dateOfBirth: "1995-06-20",
      employmentType: "SALARIED",
      employerName: "Solstice Media",
      employmentTenureMonths: 30,
      monthlyIncome: 72000,
      bureauScore: 715,
      accountAgeMonths: 26,
    },
    requestedAmount: 300000,
    tenureMonths: 24,
    purpose: "Wedding expenses",
    credit: { score: 0.16, risk: "MEDIUM", model: "RANDOM_FOREST" },
    fraud: { score: 0.52, risk: "MEDIUM", model: "RANDOM_FOREST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.95 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.92 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.89 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.9 },
    ],
    agentRecommendation: {
      action: "HUMAN_REVIEW",
      reasonCodes: ["MEDIUM_FRAUD_RISK", "APPLICATION_VELOCITY"],
      summary:
        "Fraud model flagged MEDIUM risk due to elevated application velocity from this device in the last 30 days. Policy requires human review for medium fraud risk.",
    },
    reviewTrigger: ["MEDIUM_FRAUD_RISK"],
    submittedDaysAgo: 1,
    note: "Golden case 3 — medium fraud risk, mandatory human review.",
  },
  {
    // Golden case 4: policy failure -> decline
    status: "DECLINED",
    customer: {
      fullName: "Karan Mehta",
      email: "karan.mehta@example.com",
      phone: "+91 99887 66554",
      dateOfBirth: "1998-01-15",
      employmentType: "SALARIED",
      employerName: "Bramble Foods",
      employmentTenureMonths: 4,
      monthlyIncome: 42000,
      bureauScore: 668,
      accountAgeMonths: 8,
    },
    requestedAmount: 450000,
    tenureMonths: 36,
    purpose: "Debt consolidation",
    credit: { score: 0.29, risk: "MEDIUM", model: "RANDOM_FOREST" },
    fraud: { score: 0.08, risk: "LOW", model: "RANDOM_FOREST" },
    policy: {
      overallPass: false,
      failing: ["MIN_INCOME", "BUREAU_SCORE", "EMPLOYMENT_TENURE", "MAX_AMOUNT"],
    },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.94 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.9 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.88 },
    ],
    agentRecommendation: {
      action: "DECLINE",
      reasonCodes: ["POLICY_MIN_INCOME_FAIL", "POLICY_BUREAU_SCORE_FAIL", "POLICY_TENURE_FAIL", "POLICY_MAX_AMOUNT_FAIL"],
      summary:
        "Four policy rules failed under PL_2026_V1: minimum income, bureau score, employment tenure, and maximum amount multiple. Policy failure routes directly to decline.",
    },
    submittedDaysAgo: 4,
    note: "Golden case 4 — multiple policy rule failures, declined.",
  },
  {
    // Golden case 5: high credit risk -> human review
    status: "HUMAN_REVIEW",
    customer: {
      fullName: "Simran Kaur",
      email: "simran.kaur@example.com",
      phone: "+91 98123 45678",
      dateOfBirth: "1990-09-08",
      employmentType: "SALARIED",
      employerName: "Ferro Industries",
      employmentTenureMonths: 60,
      monthlyIncome: 110000,
      bureauScore: 704,
      accountAgeMonths: 72,
    },
    requestedAmount: 700000,
    tenureMonths: 48,
    purpose: "Business investment",
    credit: { score: 0.74, risk: "HIGH", model: "XGBOOST" },
    fraud: { score: 0.05, risk: "LOW", model: "XGBOOST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.97 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.93 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.94 },
    ],
    agentRecommendation: {
      action: "HUMAN_REVIEW",
      reasonCodes: ["HIGH_CREDIT_RISK", "HIGH_FOIR"],
      summary:
        "Credit model flagged HIGH default risk driven by existing obligations pushing FOIR close to the policy ceiling. Passes policy rules but requires underwriter judgement.",
    },
    reviewTrigger: ["HIGH_CREDIT_RISK"],
    submittedDaysAgo: 3,
    note: "Golden case 5 — high credit risk despite passing policy, human review.",
  },
  {
    // Golden case 6: missing document -> request document
    status: "WAITING_FOR_DOCUMENT",
    customer: {
      fullName: "Arjun Reddy",
      email: "arjun.reddy@example.com",
      phone: "+91 90045 11009",
      dateOfBirth: "1994-03-25",
      employmentType: "SALARIED",
      employerName: "Vantage Software",
      employmentTenureMonths: 36,
      monthlyIncome: 88000,
      bureauScore: 760,
      accountAgeMonths: 40,
    },
    requestedAmount: 350000,
    tenureMonths: 24,
    purpose: "Consumer durables",
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.97 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.95 },
      { type: "SALARY_SLIP", status: "NEEDS_REUPLOAD" },
    ],
    agentRecommendation: {
      action: "REQUEST_DOCUMENT",
      reasonCodes: ["MISSING_BANK_STATEMENT", "SALARY_SLIP_UNREADABLE"],
      summary:
        "Bank statement was never uploaded and the salary slip could not be parsed. Evidence collection cannot proceed to verification without both documents.",
    },
    submittedDaysAgo: 1,
    note: "Golden case 6 — missing/unreadable documents, workflow paused.",
  },
  {
    // Golden case 7: low OCR confidence -> review/document request
    status: "WAITING_FOR_DOCUMENT",
    customer: {
      fullName: "Neha Joshi",
      email: "neha.joshi@example.com",
      phone: "+91 91234 56780",
      dateOfBirth: "1993-07-30",
      employmentType: "SALARIED",
      employerName: "Coral Analytics",
      employmentTenureMonths: 28,
      monthlyIncome: 76000,
      bureauScore: 731,
      accountAgeMonths: 33,
    },
    requestedAmount: 250000,
    tenureMonths: 24,
    purpose: "Travel",
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.94 },
      { type: "SALARY_SLIP", status: "NEEDS_REUPLOAD", ocrConfidence: 0.41 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.92 },
    ],
    agentRecommendation: {
      action: "REQUEST_DOCUMENT",
      reasonCodes: ["LOW_OCR_CONFIDENCE"],
      summary:
        "Salary slip OCR confidence (41%) is below the 70% minimum threshold. A low-confidence extraction cannot silently pass verification -- requesting a clearer re-upload.",
    },
    submittedDaysAgo: 1,
    note: "Golden case 7 — low OCR confidence document, cannot silently pass.",
  },
  {
    // Golden case 8: prohibited agent action -> blocked
    status: "RISK_ASSESSMENT",
    customer: {
      fullName: "Vikram Singh",
      email: "vikram.singh@example.com",
      phone: "+91 99001 22334",
      dateOfBirth: "1991-12-05",
      employmentType: "SALARIED",
      employerName: "Orbit Manufacturing",
      employmentTenureMonths: 50,
      monthlyIncome: 84000,
      bureauScore: 715,
      accountAgeMonths: 55,
    },
    requestedAmount: 600000,
    tenureMonths: 36,
    purpose: "Home renovation",
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.95 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.93 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.91 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.9 },
    ],
    blockedAgentAction: true,
    submittedDaysAgo: 1,
    note: "Golden case 8 — agent attempted a prohibited action (policy override) and was blocked before any state change.",
  },

  // Additional applications populating earlier pipeline stages, so the
  // customer-facing flow has real examples of every screen.
  {
    status: "DRAFT",
    customer: {
      fullName: "Avinash Pal",
      email: "avinashpal41@gmail.com",
      phone: "+91 98765 43210",
      dateOfBirth: "1994-02-18",
      employmentType: "SALARIED",
      employerName: "Northbridge Tech",
      employmentTenureMonths: 40,
      monthlyIncome: 105000,
      bureauScore: 758,
      accountAgeMonths: 50,
    },
    requestedAmount: 500000,
    tenureMonths: 36,
    purpose: "Home renovation",
    submittedDaysAgo: 0,
    note: "Draft application not yet submitted.",
  },
  {
    status: "SUBMITTED",
    customer: {
      fullName: "Meera Iyer",
      email: "meera.iyer@example.com",
      phone: "+91 90876 54321",
      dateOfBirth: "1996-05-02",
      employmentType: "SALARIED",
      employerName: "Cedarwood Consulting",
      employmentTenureMonths: 18,
      monthlyIncome: 62000,
      bureauScore: 722,
      accountAgeMonths: 20,
    },
    requestedAmount: 200000,
    tenureMonths: 18,
    purpose: "Education",
    submittedDaysAgo: 0,
    note: "Just submitted, awaiting agent run.",
  },
  {
    status: "DATA_COLLECTION",
    customer: {
      fullName: "Farhan Ali",
      email: "farhan.ali@example.com",
      phone: "+91 91765 43210",
      dateOfBirth: "1990-10-11",
      employmentType: "SALARIED",
      employerName: "Skyline Freight",
      employmentTenureMonths: 33,
      monthlyIncome: 71000,
      bureauScore: 745,
      accountAgeMonths: 38,
    },
    requestedAmount: 280000,
    tenureMonths: 24,
    purpose: "Medical expenses",
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "AADHAAR", status: "OCR_PROCESSING" },
    ],
    submittedDaysAgo: 0,
    note: "Documents partially uploaded, still processing.",
  },
  {
    status: "VERIFICATION",
    customer: {
      fullName: "Divya Menon",
      email: "divya.menon@example.com",
      phone: "+91 92345 67891",
      dateOfBirth: "1993-08-19",
      employmentType: "SALARIED",
      employerName: "Palmgrove Retail",
      employmentTenureMonths: 27,
      monthlyIncome: 69000,
      bureauScore: 728,
      accountAgeMonths: 30,
    },
    requestedAmount: 320000,
    tenureMonths: 30,
    purpose: "Consumer durables",
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.95 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.94 },
      { type: "SALARY_SLIP", status: "EXTRACTED", ocrConfidence: 0.88 },
      { type: "BANK_STATEMENT", status: "CLASSIFIED", ocrConfidence: 0.85 },
    ],
    submittedDaysAgo: 1,
    note: "All docs uploaded, verification pipeline running.",
  },
  {
    status: "OFFER",
    customer: {
      fullName: "Sanjay Gupta",
      email: "sanjay.gupta@example.com",
      phone: "+91 93456 78912",
      dateOfBirth: "1988-01-27",
      employmentType: "SALARIED",
      employerName: "Ironclad Systems",
      employmentTenureMonths: 66,
      monthlyIncome: 130000,
      bureauScore: 796,
      accountAgeMonths: 80,
    },
    requestedAmount: 900000,
    tenureMonths: 48,
    purpose: "Business investment",
    credit: { score: 0.03, risk: "LOW", model: "XGBOOST" },
    fraud: { score: 0.01, risk: "LOW", model: "XGBOOST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.98 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.97 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.95 },
    ],
    agentRecommendation: {
      action: "AUTO_APPROVE",
      reasonCodes: ["ALL_POLICY_RULES_PASS", "LOW_FRAUD_RISK", "LOW_CREDIT_RISK"],
      summary: "Clean auto-approval; offer generated and awaiting acceptance.",
    },
    offer: true,
    submittedDaysAgo: 3,
    note: "Approved, offer awaiting customer acceptance.",
  },
  {
    status: "AGREEMENT",
    customer: {
      fullName: "Ritu Bhatt",
      email: "ritu.bhatt@example.com",
      phone: "+91 94567 89123",
      dateOfBirth: "1991-06-14",
      employmentType: "SALARIED",
      employerName: "Meridian Health",
      employmentTenureMonths: 44,
      monthlyIncome: 98000,
      bureauScore: 770,
      accountAgeMonths: 52,
    },
    requestedAmount: 450000,
    tenureMonths: 36,
    purpose: "Home renovation",
    credit: { score: 0.05, risk: "LOW", model: "XGBOOST" },
    fraud: { score: 0.02, risk: "LOW", model: "XGBOOST" },
    policy: { overallPass: true },
    documents: [
      { type: "PAN_CARD", status: "VALIDATED", ocrConfidence: 0.97 },
      { type: "AADHAAR", status: "VALIDATED", ocrConfidence: 0.96 },
      { type: "SALARY_SLIP", status: "VALIDATED", ocrConfidence: 0.94 },
      { type: "BANK_STATEMENT", status: "VALIDATED", ocrConfidence: 0.93 },
    ],
    agentRecommendation: {
      action: "AUTO_APPROVE",
      reasonCodes: ["ALL_POLICY_RULES_PASS", "LOW_FRAUD_RISK", "LOW_CREDIT_RISK"],
      summary: "Clean auto-approval; offer accepted, agreement pending signature.",
    },
    offer: true,
    submittedDaysAgo: 5,
    note: "Offer accepted, e-agreement awaiting signature.",
  },
];

export const customers: Customer[] = [];
export const applications: LoanApplication[] = [];
export const modelOutputs: ModelOutput[] = [];
export const policyResults: PolicyResult[] = [];
export const humanReviewCases: HumanReviewCase[] = [];
export const offers: Offer[] = [];
export const agreements: Agreement[] = [];
export const agentEvents: AgentEvent[] = [];
export const auditEvents: AuditEvent[] = [];

function buildDocument(applicationId: string, partial: Partial<DocumentRecord>): DocumentRecord {
  return {
    id: nextId("doc"),
    applicationId,
    type: partial.type ?? "PAN_CARD",
    status: partial.status ?? "UPLOADED",
    fileName: partial.fileName ?? `${(partial.type ?? "document").toLowerCase()}.pdf`,
    ocrConfidence: partial.ocrConfidence,
    extractedFields: partial.extractedFields,
    mismatchFlags: partial.mismatchFlags,
    uploadedAt: daysAgo(1),
  };
}

seeds.forEach((seed, index) => {
  const customerId = nextId("cust");
  const applicationId = nextId("app");
  const customer: Customer = {
    id: customerId,
    ...seed.customer,
    createdAt: daysAgo(seed.customer.accountAgeMonths * 30),
  };
  customers.push(customer);

  const documents = (seed.documents ?? []).map((d) => buildDocument(applicationId, d));

  let credit: ModelOutput | undefined;
  if (seed.credit) {
    credit = {
      id: nextId("mo"),
      applicationId,
      modelType: "CREDIT",
      modelName: seed.credit.model,
      modelVersion: "credit-v1.3.0",
      score: seed.credit.score,
      riskLevel: seed.credit.risk,
      scoredAt: daysAgo(seed.submittedDaysAgo),
    };
    modelOutputs.push(credit);
  }

  let fraud: ModelOutput | undefined;
  if (seed.fraud) {
    fraud = {
      id: nextId("mo"),
      applicationId,
      modelType: "FRAUD",
      modelName: seed.fraud.model,
      modelVersion: "fraud-v1.1.0",
      score: seed.fraud.score,
      riskLevel: seed.fraud.risk,
      scoredAt: daysAgo(seed.submittedDaysAgo),
    };
    modelOutputs.push(fraud);
  }

  let policyResult: PolicyResult | undefined;
  if (seed.policy) {
    const failing = new Set(seed.policy.failing ?? []);
    const rule = (code: string, actual: string | number, threshold: string | number) => ({
      ruleCode: code,
      label: code,
      pass: !failing.has(code),
      actualValue: actual,
      threshold,
      reasonCode: failing.has(code) ? `POLICY_${code}_FAIL` : undefined,
    });
    const age = Math.floor(
      (now.getTime() - new Date(seed.customer.dateOfBirth).getTime()) / (365.25 * 24 * 3600 * 1000)
    );
    const foir = Math.round(((seed.requestedAmount / seed.tenureMonths) / seed.customer.monthlyIncome) * 100 + 12);
    policyResult = {
      id: nextId("pol"),
      applicationId,
      policyVersion: POLICY_VERSION,
      overallPass: seed.policy.overallPass,
      rules: [
        rule("AGE_RANGE", age, "21-60"),
        rule("MIN_INCOME", seed.customer.monthlyIncome, 50000),
        rule("BUREAU_SCORE", seed.customer.bureauScore, 700),
        rule("FOIR", `${foir}%`, "50%"),
        rule("EMPLOYMENT_TENURE", seed.customer.employmentTenureMonths, 6),
        rule(
          "MAX_AMOUNT",
          seed.requestedAmount,
          seed.customer.monthlyIncome * 8
        ),
      ],
      evaluatedAt: daysAgo(seed.submittedDaysAgo),
    };
    policyResults.push(policyResult);
  }

  let offer: Offer | undefined;
  if (seed.offer) {
    const rate = 13.5;
    const principal = seed.requestedAmount;
    const monthlyRate = rate / 12 / 100;
    const emi =
      (principal * monthlyRate * Math.pow(1 + monthlyRate, seed.tenureMonths)) /
      (Math.pow(1 + monthlyRate, seed.tenureMonths) - 1);
    offer = {
      id: nextId("off"),
      applicationId,
      approvedAmount: principal,
      interestRateApr: rate,
      tenureMonths: seed.tenureMonths,
      monthlyInstallment: Math.round(emi),
      processingFee: Math.round(principal * 0.01),
      status: seed.status === "OFFER" ? "PENDING" : "ACCEPTED",
      expiresAt: new Date(now.getTime() + 7 * 24 * 3600 * 1000).toISOString(),
      createdAt: daysAgo(seed.submittedDaysAgo),
    };
    offers.push(offer);
  }

  let agreement: Agreement | undefined;
  if (seed.agreementSigned || seed.status === "AGREEMENT" || seed.status === "MOCK_DISBURSAL") {
    agreement = {
      id: nextId("agr"),
      applicationId,
      status: seed.agreementSigned ? "SIGNED" : "PENDING_SIGNATURE",
      signedAt: seed.agreementSigned ? daysAgo(1) : undefined,
      documentUrl: seed.agreementSigned ? "#" : undefined,
    };
    agreements.push(agreement);
  }

  const application: LoanApplication = {
    id: applicationId,
    applicationNumber: `LN-2026-${(1000 + index).toString().padStart(5, "0")}`,
    customerId,
    customer: {
      id: customer.id,
      fullName: customer.fullName,
      email: customer.email,
      phone: customer.phone,
    },
    status: seed.status,
    requestedAmount: seed.requestedAmount,
    tenureMonths: seed.tenureMonths,
    purpose: seed.purpose,
    submittedAt: seed.status === "DRAFT" ? null : daysAgo(seed.submittedDaysAgo),
    updatedAt: daysAgo(Math.max(seed.submittedDaysAgo - 1, 0)),
    createdAt: daysAgo(seed.submittedDaysAgo + 1),
    policyVersion: POLICY_VERSION,
    latestCreditScore: credit,
    latestFraudScore: fraud,
    policyResult,
    agentRecommendation: seed.agentRecommendation,
    documents,
    offer,
    agreement,
  };
  applications.push(application);

  // Agent events
  let step = 1;
  const pushEvent = (partial: Omit<AgentEvent, "id" | "applicationId" | "step" | "createdAt">) => {
    agentEvents.push({
      id: nextId("evt"),
      applicationId,
      step: step++,
      createdAt: daysAgo(seed.submittedDaysAgo),
      ...partial,
    });
  };

  if (seed.status !== "DRAFT") {
    pushEvent({ type: "TOOL_CALL", toolName: "fetch_customer_profile", detail: "Fetched verified customer profile from core banking." });
    pushEvent({ type: "TOOL_RESULT", toolName: "fetch_customer_profile", detail: "Profile retrieved: employment, income and account age confirmed." });
  }
  if (documents.length > 0) {
    pushEvent({ type: "TOOL_CALL", toolName: "request_documents", detail: `Requested documents: ${documents.map((d) => d.type).join(", ")}.` });
    pushEvent({ type: "EVIDENCE_ANALYSIS", detail: "Analysed OCR extraction and cross-checked against declared income and identity." });
  }
  if (credit || fraud) {
    if (credit) pushEvent({ type: "TOOL_CALL", toolName: "credit_score", detail: `Invoked credit model ${credit.modelName} (${credit.modelVersion}).` });
    if (fraud) pushEvent({ type: "TOOL_CALL", toolName: "fraud_score", detail: `Invoked fraud model ${fraud.modelName} (${fraud.modelVersion}).` });
  }
  if (policyResult) {
    pushEvent({ type: "TOOL_CALL", toolName: "policy_evaluate", detail: `Evaluated policy ${POLICY_VERSION}.` });
  }
  if (seed.reviewTrigger) {
    pushEvent({ type: "REVIEW_CASE_CREATED", detail: `Created human review case: ${seed.reviewTrigger.join(", ")}.` });
  }
  if (seed.agentRecommendation) {
    pushEvent({ type: "RECOMMENDATION", detail: seed.agentRecommendation.summary });
  }
  if (seed.blockedAgentAction) {
    pushEvent({
      type: "BLOCKED_ACTION",
      toolName: "override_policy_decision",
      detail:
        "Agent attempted to call a prohibited tool (override_policy_decision) to force an approval. Action validation rejected the call before any state change; escalated to fail-safe human queue.",
    });
  }

  // Human review case
  if (seed.reviewTrigger) {
    humanReviewCases.push({
      id: nextId("rev"),
      applicationId,
      application,
      status: seed.reviewDecision ? "CLOSED" : "OPEN",
      triggerReasons: seed.reviewTrigger,
      createdAt: daysAgo(seed.submittedDaysAgo),
      decision: seed.reviewDecision,
    });
  }

  // Audit trail (always at least a creation + status event)
  auditEvents.push({
    id: nextId("aud"),
    applicationId,
    actor: "system",
    action: "APPLICATION_CREATED",
    detail: `Application ${application.applicationNumber} created.`,
    createdAt: application.createdAt,
  });
  if (application.submittedAt) {
    auditEvents.push({
      id: nextId("aud"),
      applicationId,
      actor: customer.fullName,
      action: "APPLICATION_SUBMITTED",
      detail: "Customer submitted application for processing.",
      createdAt: application.submittedAt,
    });
  }
  auditEvents.push({
    id: nextId("aud"),
    applicationId,
    actor: "system",
    action: "STATUS_CHANGED",
    detail: `Status set to ${application.status}.`,
    createdAt: application.updatedAt,
  });
});
