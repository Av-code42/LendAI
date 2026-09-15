import { AlertTriangle, Bot, CheckCircle2, FileSearch, ShieldAlert, Wrench } from "lucide-react";
import type { AgentEvent } from "@/types/domain";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/cn";

const ICONS: Record<AgentEvent["type"], typeof Bot> = {
  TOOL_CALL: Wrench,
  TOOL_RESULT: CheckCircle2,
  EVIDENCE_ANALYSIS: FileSearch,
  REVIEW_CASE_CREATED: ShieldAlert,
  RECOMMENDATION: Bot,
  BLOCKED_ACTION: AlertTriangle,
};

export function AgentTimeline({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-ink-400">No agent activity yet.</p>;
  }
  return (
    <ol className="space-y-0">
      {events.map((event, idx) => {
        const Icon = ICONS[event.type];
        const isBlocked = event.type === "BLOCKED_ACTION";
        return (
          <li key={event.id} className="relative flex gap-3 pb-5 last:pb-0">
            {idx < events.length - 1 && (
              <span className="absolute left-[15px] top-7 h-full w-px bg-ink-100" aria-hidden />
            )}
            <div
              className={cn(
                "z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                isBlocked ? "border-danger-300 bg-danger-50 text-danger-600" : "border-ink-200 bg-white text-brand-600"
              )}
            >
              <Icon className="h-4 w-4" />
            </div>
            <div className="pt-0.5">
              <div className="flex flex-wrap items-center gap-2">
                {event.toolName && (
                  <code className="rounded bg-ink-100 px-1.5 py-0.5 text-xs text-ink-700">{event.toolName}</code>
                )}
                <span className="text-xs text-ink-400">{formatDateTime(event.createdAt)}</span>
                {isBlocked && (
                  <span className="rounded-full bg-danger-100 px-2 py-0.5 text-[11px] font-semibold text-danger-700">
                    Blocked by guardrails
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-ink-700">{event.detail}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
