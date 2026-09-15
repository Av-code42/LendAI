import type { ReactNode } from "react";
import { TopNav } from "@/components/layout/TopNav";

export function AppShell({ mode, children }: { mode: "customer" | "underwriter"; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-ink-50">
      <TopNav mode={mode} />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 pt-2 text-center text-xs text-ink-400 sm:px-6">
        LendAI MVP — synthetic demo data, illustrative policy thresholds only. Not real bank policy or real
        customer data.
      </footer>
    </div>
  );
}
