import { Badge } from "@/components/ui/Badge";
import { STATUS_META, RISK_META } from "@/lib/statusMeta";
import type { ApplicationStatus, RiskLevel } from "@/types/domain";

export function StatusPill({ status }: { status: ApplicationStatus }) {
  const meta = STATUS_META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function RiskPill({ level }: { level: RiskLevel }) {
  const meta = RISK_META[level];
  return <Badge tone={meta.tone}>{meta.label} risk</Badge>;
}
