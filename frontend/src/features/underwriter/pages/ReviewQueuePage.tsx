import { Link } from "react-router-dom";
import { Inbox } from "lucide-react";
import { useReviewCases } from "@/api/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { PageSpinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Badge } from "@/components/ui/Badge";
import { RiskPill } from "@/components/ui/StatusPill";
import { formatCurrency, formatDateTime, titleCase } from "@/lib/format";

export function ReviewQueuePage() {
  const { data: reviews, isLoading } = useReviewCases();
  const open = reviews?.filter((r) => r.status === "OPEN") ?? [];
  const closed = reviews?.filter((r) => r.status === "CLOSED") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink-900">Review Queue</h1>
        <p className="text-sm text-ink-500">Applications routed to mandatory human review.</p>
      </div>

      <Card>
        <CardHeader title="Open cases" subtitle={`${open.length} awaiting decision`} />
        <CardBody className="p-0">
          {isLoading ? (
            <PageSpinner />
          ) : open.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={Inbox} title="Queue is empty" description="No applications currently need human review." />
            </div>
          ) : (
            <ReviewTable cases={open} />
          )}
        </CardBody>
      </Card>

      {closed.length > 0 && (
        <Card>
          <CardHeader title="Recently decided" />
          <CardBody className="p-0">
            <ReviewTable cases={closed} />
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function ReviewTable({ cases }: { cases: ReturnType<typeof useReviewCases>["data"] }) {
  if (!cases) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-100 text-left text-xs uppercase tracking-wide text-ink-400">
            <th className="px-5 py-3 font-medium">Application</th>
            <th className="px-5 py-3 font-medium">Customer</th>
            <th className="px-5 py-3 font-medium">Amount</th>
            <th className="px-5 py-3 font-medium">Fraud</th>
            <th className="px-5 py-3 font-medium">Credit</th>
            <th className="px-5 py-3 font-medium">Trigger</th>
            <th className="px-5 py-3 font-medium">Created</th>
            <th className="px-5 py-3 font-medium">Decision</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.id} className="border-b border-ink-50 last:border-0 hover:bg-ink-50">
              <td className="px-5 py-3">
                <Link to={`/review/${c.id}`} className="font-medium text-brand-700 hover:underline">
                  {c.application.applicationNumber}
                </Link>
              </td>
              <td className="px-5 py-3 text-ink-700">{c.application.customer.fullName}</td>
              <td className="px-5 py-3 text-ink-700">{formatCurrency(c.application.requestedAmount)}</td>
              <td className="px-5 py-3">
                {c.application.latestFraudScore ? <RiskPill level={c.application.latestFraudScore.riskLevel} /> : "—"}
              </td>
              <td className="px-5 py-3">
                {c.application.latestCreditScore ? <RiskPill level={c.application.latestCreditScore.riskLevel} /> : "—"}
              </td>
              <td className="px-5 py-3">
                <div className="flex flex-wrap gap-1">
                  {c.triggerReasons.map((r) => (
                    <Badge key={r} tone="warning">
                      {titleCase(r)}
                    </Badge>
                  ))}
                </div>
              </td>
              <td className="px-5 py-3 text-ink-400">{formatDateTime(c.createdAt)}</td>
              <td className="px-5 py-3">
                {c.decision ? (
                  <Badge tone={c.decision.action === "APPROVE" ? "success" : c.decision.action === "REJECT" ? "danger" : "info"}>
                    {titleCase(c.decision.action)}
                  </Badge>
                ) : (
                  <span className="text-ink-400">Pending</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
