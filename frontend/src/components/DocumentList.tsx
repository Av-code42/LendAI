import { AlertCircle, CheckCircle2, Clock, FileText } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatPercent, titleCase } from "@/lib/format";
import type { DocumentRecord } from "@/types/domain";

const STATUS_STYLE: Record<DocumentRecord["status"], { icon: typeof FileText; tone: string }> = {
  UPLOADED: { icon: Clock, tone: "text-ink-500" },
  SCANNING: { icon: Clock, tone: "text-ink-500" },
  OCR_PROCESSING: { icon: Clock, tone: "text-brand-600" },
  CLASSIFIED: { icon: Clock, tone: "text-brand-600" },
  EXTRACTED: { icon: Clock, tone: "text-brand-600" },
  VALIDATED: { icon: CheckCircle2, tone: "text-success-600" },
  REJECTED: { icon: AlertCircle, tone: "text-danger-600" },
  NEEDS_REUPLOAD: { icon: AlertCircle, tone: "text-warning-600" },
};

export function DocumentList({ documents }: { documents: DocumentRecord[] }) {
  if (documents.length === 0) {
    return <p className="text-sm text-ink-400">No documents uploaded yet.</p>;
  }
  return (
    <ul className="divide-y divide-ink-100">
      {documents.map((doc) => {
        const style = STATUS_STYLE[doc.status];
        const Icon = style.icon;
        return (
          <li key={doc.id} className="flex items-center justify-between gap-3 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ink-100">
                <FileText className="h-4 w-4 text-ink-500" />
              </div>
              <div>
                <p className="text-sm font-medium text-ink-800">{titleCase(doc.type)}</p>
                <p className="text-xs text-ink-400">{doc.fileName}</p>
                {doc.mismatchFlags && doc.mismatchFlags.length > 0 && (
                  <p className="mt-0.5 text-xs text-warning-700">{doc.mismatchFlags.map(titleCase).join(", ")}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 text-right">
              {doc.ocrConfidence !== undefined && (
                <span className="text-xs text-ink-400">OCR {formatPercent(doc.ocrConfidence, 0)}</span>
              )}
              <span className={cn("flex items-center gap-1 text-xs font-medium", style.tone)}>
                <Icon className="h-3.5 w-3.5" />
                {titleCase(doc.status)}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
