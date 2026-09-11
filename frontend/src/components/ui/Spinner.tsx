import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-500">
      <Loader2 className={cn("h-4 w-4 animate-spin", className)} />
      {label}
    </div>
  );
}

export function PageSpinner() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner label="Loading…" />
    </div>
  );
}
