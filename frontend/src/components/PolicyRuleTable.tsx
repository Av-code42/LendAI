import { Check, X } from "lucide-react";
import { cn } from "@/lib/cn";
import type { PolicyResult } from "@/types/domain";

export function PolicyRuleTable({ policyResult }: { policyResult: PolicyResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-100 text-left text-xs uppercase tracking-wide text-ink-400">
            <th className="py-2 pr-4 font-medium">Rule</th>
            <th className="py-2 pr-4 font-medium">Actual</th>
            <th className="py-2 pr-4 font-medium">Threshold</th>
            <th className="py-2 pr-4 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {policyResult.rules.map((rule) => (
            <tr key={rule.ruleCode} className="border-b border-ink-50 last:border-0">
              <td className="py-2.5 pr-4 text-ink-800">{rule.label}</td>
              <td className="py-2.5 pr-4 text-ink-600">{rule.actualValue}</td>
              <td className="py-2.5 pr-4 text-ink-600">{rule.threshold}</td>
              <td className="py-2.5 pr-4">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                    rule.pass ? "bg-success-100 text-success-700" : "bg-danger-100 text-danger-700"
                  )}
                >
                  {rule.pass ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                  {rule.pass ? "Pass" : "Fail"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-ink-400">
        Policy {policyResult.policyVersion} · evaluated{" "}
        {new Date(policyResult.evaluatedAt).toLocaleString("en-IN")}
      </p>
    </div>
  );
}
