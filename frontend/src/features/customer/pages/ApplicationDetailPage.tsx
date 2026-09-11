import { useParams, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Banknote, CheckCircle2, PlayCircle, ShieldCheck } from "lucide-react";
import {
  useAcceptOffer,
  useAgentEvents,
  useApplication,
  useDisburse,
  useRunAgent,
  useSignAgreement,
} from "@/api/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PageSpinner } from "@/components/ui/Spinner";
import { StatusPill } from "@/components/ui/StatusPill";
import { Stepper } from "@/components/ui/Stepper";
import { ScoreCard } from "@/components/ScoreCard";
import { PolicyRuleTable } from "@/components/PolicyRuleTable";
import { AgentTimeline } from "@/components/AgentTimeline";
import { DocumentUploader } from "@/features/customer/components/DocumentUploader";
import { formatCurrency, formatDate, titleCase } from "@/lib/format";

const AGENT_RUNNABLE_STATUSES = ["SUBMITTED", "DATA_COLLECTION", "WAITING_FOR_DOCUMENT"];

export function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: app } = useApplication(id, { poll: true });
  const isLoading = !app;
  const { data: events } = useAgentEvents(id);
  const runAgent = useRunAgent();
  const acceptOffer = useAcceptOffer();
  const signAgreement = useSignAgreement();
  const disburse = useDisburse();

  if (isLoading || !app) return <PageSpinner />;

  const canRunAgent = AGENT_RUNNABLE_STATUSES.includes(app.status) && app.documents.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/customer")} className="rounded-md p-1.5 text-ink-500 hover:bg-ink-100">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold text-ink-900">{app.applicationNumber}</h1>
            <StatusPill status={app.status} />
          </div>
          <p className="text-sm text-ink-500">
            {formatCurrency(app.requestedAmount)} · {app.tenureMonths} months · {app.purpose}
          </p>
        </div>
      </div>

      <Card>
        <CardBody className="overflow-x-auto">
          <Stepper status={app.status} />
        </CardBody>
      </Card>

      {app.status === "DECLINED" && (
        <Card className="border-danger-200 bg-danger-50">
          <CardBody className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger-600" />
            <div>
              <p className="font-medium text-danger-800">This application was declined</p>
              <p className="mt-1 text-sm text-danger-700">
                {app.agentRecommendation?.summary ?? "Policy evaluation did not pass all required rules."}
              </p>
            </div>
          </CardBody>
        </Card>
      )}

      {app.status === "HUMAN_REVIEW" && (
        <Card className="border-warning-200 bg-warning-50">
          <CardBody className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-warning-600" />
            <div>
              <p className="font-medium text-warning-800">Under underwriter review</p>
              <p className="mt-1 text-sm text-warning-700">
                Your application needs a manual check before we can proceed. We'll notify you as soon as a
                decision is made — no action needed from you right now.
              </p>
            </div>
          </CardBody>
        </Card>
      )}

      {(app.status === "SUBMITTED" || app.status === "DATA_COLLECTION" || app.status === "WAITING_FOR_DOCUMENT") && (
        <Card>
          <CardHeader
            title="Documents"
            subtitle="Upload the documents below, then run evidence collection to proceed."
          />
          <CardBody>
            <DocumentUploader applicationId={app.id} documents={app.documents} />
            <div className="mt-4 flex justify-end">
              <Button onClick={() => runAgent.mutate(app.id)} loading={runAgent.isPending} disabled={!canRunAgent}>
                <PlayCircle className="h-4 w-4" /> Run Evidence Collection
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {app.documents.length > 0 &&
        !["SUBMITTED", "DATA_COLLECTION", "WAITING_FOR_DOCUMENT"].includes(app.status) && (
          <Card>
            <CardHeader title="Documents" />
            <CardBody>
              <DocumentUploader applicationId={app.id} documents={app.documents} />
            </CardBody>
          </Card>
        )}

      {(app.latestCreditScore || app.latestFraudScore) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {app.latestCreditScore && <ScoreCard output={app.latestCreditScore} label="Credit risk (default probability)" />}
          {app.latestFraudScore && <ScoreCard output={app.latestFraudScore} label="Fraud risk" />}
        </div>
      )}

      {app.policyResult && (
        <Card>
          <CardHeader title={`Policy evaluation — ${app.policyResult.policyVersion}`} />
          <CardBody>
            <PolicyRuleTable policyResult={app.policyResult} />
          </CardBody>
        </Card>
      )}

      {app.offer && app.status === "OFFER" && (
        <Card className="border-brand-200 bg-brand-50">
          <CardHeader title="Your loan offer" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Approved amount" value={formatCurrency(app.offer.approvedAmount)} />
              <Stat label="Interest rate" value={`${app.offer.interestRateApr}% APR`} />
              <Stat label="Tenure" value={`${app.offer.tenureMonths} months`} />
              <Stat label="Monthly EMI" value={formatCurrency(app.offer.monthlyInstallment)} />
            </div>
            <p className="text-xs text-ink-500">
              Processing fee {formatCurrency(app.offer.processingFee)} · Offer valid until{" "}
              {formatDate(app.offer.expiresAt)}
            </p>
            <div className="flex justify-end">
              <Button onClick={() => acceptOffer.mutate(app.id)} loading={acceptOffer.isPending} variant="success">
                <CheckCircle2 className="h-4 w-4" /> Accept Offer
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {app.agreement && app.status === "AGREEMENT" && (
        <Card>
          <CardHeader title="Loan agreement" subtitle="Review and sign to proceed to disbursal." />
          <CardBody className="flex items-center justify-between">
            <p className="text-sm text-ink-600">
              Status: <span className="font-medium">{titleCase(app.agreement.status)}</span>
            </p>
            {app.agreement.status === "PENDING_SIGNATURE" && (
              <Button onClick={() => signAgreement.mutate(app.id)} loading={signAgreement.isPending}>
                Sign Agreement (mock e-sign)
              </Button>
            )}
          </CardBody>
        </Card>
      )}

      {app.status === "MOCK_DISBURSAL" && app.offer && (
        <Card className="border-success-200 bg-success-50">
          <CardBody className="flex items-start gap-3">
            <Banknote className="mt-0.5 h-5 w-5 shrink-0 text-success-600" />
            <div>
              <p className="font-medium text-success-800">Funds disbursed (mock)</p>
              <p className="mt-1 text-sm text-success-700">
                {formatCurrency(app.offer.approvedAmount)} has been mock-disbursed to your linked account.
              </p>
            </div>
          </CardBody>
        </Card>
      )}

      {app.agreement?.status === "SIGNED" && app.status === "AGREEMENT" && (
        <div className="flex justify-end">
          <Button onClick={() => disburse.mutate(app.id)} loading={disburse.isPending}>
            <Banknote className="h-4 w-4" /> Simulate Disbursal
          </Button>
        </div>
      )}

      {events && events.length > 0 && (
        <Card>
          <CardHeader title="Agent activity" subtitle="What the agent did while processing this application" />
          <CardBody>
            <AgentTimeline events={events} />
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-ink-500">{label}</p>
      <p className="mt-0.5 text-base font-semibold text-ink-900">{value}</p>
    </div>
  );
}
