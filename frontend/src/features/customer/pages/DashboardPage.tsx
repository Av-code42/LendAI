import { Link, useNavigate } from "react-router-dom";
import { FilePlus2, Inbox } from "lucide-react";
import { useApplications } from "@/api/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PageSpinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { formatCurrency, formatDate } from "@/lib/format";

export function DashboardPage() {
  const { data: applications, isLoading } = useApplications();
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink-900">My Applications</h1>
          <p className="text-sm text-ink-500">Track every loan application from draft through disbursal.</p>
        </div>
        <Link to="/customer/new">
          <Button>
            <FilePlus2 className="h-4 w-4" /> New Application
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader title="Applications" subtitle={applications ? `${applications.length} total` : undefined} />
        <CardBody className="p-0">
          {isLoading ? (
            <PageSpinner />
          ) : !applications || applications.length === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={Inbox}
                title="No applications yet"
                description="Start a new personal loan application to see it tracked here."
                action={
                  <Link to="/customer/new">
                    <Button size="sm">Start application</Button>
                  </Link>
                }
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-ink-100 text-left text-xs uppercase tracking-wide text-ink-400">
                    <th className="px-5 py-3 font-medium">Application</th>
                    <th className="px-5 py-3 font-medium">Amount</th>
                    <th className="px-5 py-3 font-medium">Purpose</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {applications.map((app) => (
                    <tr
                      key={app.id}
                      className="cursor-pointer border-b border-ink-50 last:border-0 hover:bg-ink-50"
                      onClick={() => navigate(`/customer/applications/${app.id}`)}
                    >
                      <td className="px-5 py-3">
                        <Link to={`/customer/applications/${app.id}`} className="font-medium text-brand-700 hover:underline">
                          {app.applicationNumber}
                        </Link>
                      </td>
                      <td className="px-5 py-3 text-ink-700">{formatCurrency(app.requestedAmount)}</td>
                      <td className="px-5 py-3 text-ink-500">{app.purpose}</td>
                      <td className="px-5 py-3">
                        <StatusPill status={app.status} />
                      </td>
                      <td className="px-5 py-3 text-ink-400">{formatDate(app.updatedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
