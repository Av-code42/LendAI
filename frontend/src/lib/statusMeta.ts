import type { ApplicationStatus, RiskLevel } from "@/types/domain";

export interface StatusMeta {
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
}

export const STATUS_META: Record<ApplicationStatus, StatusMeta> = {
  DRAFT: { label: "Draft", tone: "neutral" },
  SUBMITTED: { label: "Submitted", tone: "info" },
  DATA_COLLECTION: { label: "Data Collection", tone: "info" },
  VERIFICATION: { label: "Verification", tone: "info" },
  RISK_ASSESSMENT: { label: "Risk Assessment", tone: "info" },
  POLICY_EVALUATION: { label: "Policy Evaluation", tone: "info" },
  AUTO_APPROVED: { label: "Auto-Approved", tone: "success" },
  HUMAN_REVIEW: { label: "Human Review", tone: "warning" },
  DECLINED: { label: "Declined", tone: "danger" },
  OFFER: { label: "Offer", tone: "info" },
  AGREEMENT: { label: "Agreement", tone: "info" },
  MOCK_DISBURSAL: { label: "Disbursed", tone: "success" },
  WAITING_FOR_DOCUMENT: { label: "Waiting for Document", tone: "warning" },
};

export const RISK_META: Record<RiskLevel, StatusMeta> = {
  LOW: { label: "Low", tone: "success" },
  MEDIUM: { label: "Medium", tone: "warning" },
  HIGH: { label: "High", tone: "danger" },
};

/** Terminal / branch statuses that fall outside the linear happy-path stepper. */
export const TERMINAL_STATUSES: ApplicationStatus[] = [
  "DECLINED",
  "AUTO_APPROVED",
];
