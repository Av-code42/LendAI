import { useParams, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useDecideReview, useReviewCase } from "@/api/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PageSpinner } from "@/components/ui/Spinner";
import { StatusPill } from "@/components/ui/StatusPill";
import { Badge } from "@/components/ui/Badge";
import { FieldWrapper, Select, TextInput } from "@/components/ui/Field";
import { ScoreCard } from "@/components/ScoreCard";
import { PolicyRuleTable } from "@/components/PolicyRuleTable";
import { DocumentList } from "@/components/DocumentList";
import { formatCurrency, titleCase } from "@/lib/format";
import type { ReviewAction } from "@/types/domain";

// Mock signed-in underwriter -- stands in for real auth/session in the MVP.
const CURRENT_UNDERWRITER = { userId: "uw_demo_1", userName: "Priyanka Rao" };

const REASON_CODES_BY_ACTION: Record<ReviewAction, string[]> = {
  APPROVE: ["EVIDENCE_SUFFICIENT", "RISK_ACCEPTABLE_ON_REVIEW"],
  REJECT: ["FRAUD_CONFIRMED", "UNVERIFIABLE_INCOME", "RISK_TOO_HIGH"],
  REQUEST_INFORMATION: ["ADDITIONAL_DOCUMENT_NEEDED", "INCOME_CLARIFICATION_NEEDED"],
  MODIFY_OFFER: ["REDUCED_AMOUNT_WITHIN_POLICY", "ADJUSTED_TENURE"],
  ESCALATE: ["REQUIRES_SENIOR_UNDERWRITER", "POLICY_EXCEPTION_REQUEST"],
};

const schema = z
  .object({
    action: z.enum(["APPROVE", "REJECT", "REQUEST_INFORMATION", "MODIFY_OFFER", "ESCALATE"]),
    reasonCode: z.string().min(1, "Select a reason code"),
    comment: z.string().min(5, "Add a short comment for the audit trail"),
    modifiedOfferAmount: z.coerce.number().positive().optional(),
  })
  .refine((data) => data.action !== "MODIFY_OFFER" || !!data.modifiedOfferAmount, {
    message: "Enter the modified amount",
    path: ["modifiedOfferAmount"],
  });

type FormValues = z.infer<typeof schema>;

export function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: review, isLoading } = useReviewCase(id);
  const decide = useDecideReview();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { action: "APPROVE", reasonCode: "" },
  });
  const action = watch("action");

  if (isLoading || !review) return <PageSpinner />;

  const app = review.application;
  const decided = review.status === "CLOSED";

  const onSubmit = async (values: FormValues) => {
    await decide.mutateAsync({ reviewId: review.id, ...CURRENT_UNDERWRITER, ...values });
    navigate("/review");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/review")} className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold text-ink-900">{app.applicationNumber}</h1>
            <StatusPill status={app.status} />
          </div>
          <p className="text-sm text-ink-500">
            {app.customer.fullName} · {app.customer.email} · {app.customer.phone}
          </p>
        </div>
      </div>

      <Card>
        <CardHeader title="Why this case needs review" />
        <CardBody className="flex flex-wrap gap-2">
          {review.triggerReasons.map((r) => (
            <Badge key={r} tone="warning">
              {titleCase(r)}
            </Badge>
          ))}
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-ink-100 bg-white p-4 shadow-card">
          <p className="text-xs text-ink-500">Requested amount</p>
          <p className="mt-0.5 text-lg font-semibold text-ink-900">{formatCurrency(app.requestedAmount)}</p>
          <p className="text-xs text-ink-400">{app.tenureMonths} months · {app.purpose}</p>
        </div>
        {app.latestCreditScore && <ScoreCard output={app.latestCreditScore} label="Credit risk" />}
        {app.latestFraudScore && <ScoreCard output={app.latestFraudScore} label="Fraud risk" />}
      </div>

      {app.policyResult && (
        <Card>
          <CardHeader title={`Policy evaluation — ${app.policyResult.policyVersion}`} />
          <CardBody>
            <PolicyRuleTable policyResult={app.policyResult} />
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Documents & evidence" />
        <CardBody>
          <DocumentList documents={app.documents} />
        </CardBody>
      </Card>

      {app.agentRecommendation && (
        <Card className="border-brand-200 bg-brand-50">
          <CardHeader title="Agent recommendation" subtitle="Advisory only — the agent cannot approve, decline, or override policy." />
          <CardBody>
            <p className="text-sm font-medium text-ink-800">{titleCase(app.agentRecommendation.action)}</p>
            <p className="mt-1 text-sm text-ink-600">{app.agentRecommendation.summary}</p>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="Decision" subtitle={decided ? "This case has already been decided." : "Recorded with your user id, timestamp, and reason code."} />
        <CardBody>
          {decided && review.decision ? (
            <div className="flex items-start gap-3 rounded-lg bg-success-50 p-4">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success-600" />
              <div className="text-sm text-success-800">
                <p className="font-medium">{titleCase(review.decision.action)} by {review.decision.userName}</p>
                <p className="mt-1">
                  Reason: {titleCase(review.decision.reasonCode)} — {review.decision.comment}
                </p>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FieldWrapper label="Action" htmlFor="action">
                  <Select id="action" {...register("action")}>
                    <option value="APPROVE">Approve</option>
                    <option value="REJECT">Reject</option>
                    <option value="REQUEST_INFORMATION">Request Information</option>
                    <option value="MODIFY_OFFER">Modify Offer (within policy)</option>
                    <option value="ESCALATE">Escalate</option>
                  </Select>
                </FieldWrapper>
                <FieldWrapper label="Reason code" htmlFor="reasonCode" error={errors.reasonCode?.message}>
                  <Select id="reasonCode" defaultValue="" {...register("reasonCode")} error={!!errors.reasonCode}>
                    <option value="" disabled>
                      Select a reason
                    </option>
                    {REASON_CODES_BY_ACTION[action].map((code) => (
                      <option key={code} value={code}>
                        {titleCase(code)}
                      </option>
                    ))}
                  </Select>
                </FieldWrapper>
              </div>

              {action === "MODIFY_OFFER" && (
                <FieldWrapper
                  label="Modified amount (₹)"
                  htmlFor="modifiedOfferAmount"
                  error={errors.modifiedOfferAmount?.message}
                  hint={`Must stay within policy — original request was ${formatCurrency(app.requestedAmount)}.`}
                >
                  <TextInput
                    id="modifiedOfferAmount"
                    type="number"
                    {...register("modifiedOfferAmount")}
                    error={!!errors.modifiedOfferAmount}
                  />
                </FieldWrapper>
              )}

              <FieldWrapper label="Comment" htmlFor="comment" error={errors.comment?.message}>
                <textarea
                  id="comment"
                  rows={3}
                  className="w-full rounded-lg border border-ink-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  placeholder="Explain your decision for the audit trail…"
                  {...register("comment")}
                />
              </FieldWrapper>

              <div className="flex justify-end">
                <Button type="submit" loading={decide.isPending}>
                  Submit Decision
                </Button>
              </div>
            </form>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
