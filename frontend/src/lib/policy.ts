/**
 * Client-side mirror of policy PL_2026_V1 thresholds, for display purposes
 * only (e.g. showing the applicant what the requested amount limit is on
 * the New Application form). The authoritative evaluation always happens
 * server-side / in the mock policy-evaluate endpoint -- the frontend must
 * never make an approve/decline decision itself.
 */
export const POLICY_VERSION = "PL_2026_V1";

export const POLICY_THRESHOLDS = {
  minAge: 21,
  maxAge: 60,
  minMonthlyIncome: 50_000,
  minBureauScore: 700,
  maxFoirPercent: 50,
  minEmploymentTenureMonths: 6,
  maxAmountMultipleOfIncome: 8,
} as const;

export const RULE_LABELS: Record<string, string> = {
  AGE_RANGE: "Age between 21-60",
  MIN_INCOME: "Monthly income ≥ ₹50,000",
  BUREAU_SCORE: "Bureau score ≥ 700",
  FOIR: "FOIR ≤ 50%",
  EMPLOYMENT_TENURE: "Employment tenure ≥ 6 months",
  MAX_AMOUNT: "Requested amount ≤ 8x monthly income",
};
