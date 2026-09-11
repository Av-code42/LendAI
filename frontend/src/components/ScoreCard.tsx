import { cn } from "@/lib/cn";
import { formatPercent, titleCase } from "@/lib/format";
import { RiskPill } from "@/components/ui/StatusPill";
import type { ModelOutput } from "@/types/domain";

const TONE_BAR: Record<ModelOutput["riskLevel"], string> = {
  LOW: "bg-success-500",
  MEDIUM: "bg-warning-500",
  HIGH: "bg-danger-500",
};

export function ScoreCard({ output, label }: { output: ModelOutput; label: string }) {
  return (
    <div className="rounded-lg border border-ink-100 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
        <RiskPill level={output.riskLevel} />
      </div>
      <p className="mt-2 text-2xl font-bold text-ink-900">{formatPercent(output.score)}</p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
        <div
          className={cn("h-full rounded-full", TONE_BAR[output.riskLevel])}
          style={{ width: `${Math.min(output.score * 100, 100)}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-ink-400">
        {titleCase(output.modelName)} · {output.modelVersion}
      </p>
    </div>
  );
}
