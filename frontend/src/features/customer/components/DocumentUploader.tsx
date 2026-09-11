import { useRef } from "react";
import { UploadCloud } from "lucide-react";
import { useUploadDocument } from "@/api/queries";
import { Button } from "@/components/ui/Button";
import { titleCase } from "@/lib/format";
import type { DocumentRecord, DocumentType } from "@/types/domain";

const REQUIRED_DOCS: DocumentType[] = ["PAN_CARD", "AADHAAR", "SALARY_SLIP", "BANK_STATEMENT"];

export function DocumentUploader({
  applicationId,
  documents,
}: {
  applicationId: string;
  documents: DocumentRecord[];
}) {
  const upload = useUploadDocument();
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const latestFor = (type: DocumentType) =>
    [...documents].reverse().find((d) => d.type === type);

  const handleFile = (type: DocumentType, file: File | undefined) => {
    if (!file) return;
    upload.mutate({ applicationId, type, fileName: file.name });
  };

  return (
    <div className="space-y-3">
      {REQUIRED_DOCS.map((type) => {
        const existing = latestFor(type);
        const needsAction = !existing || existing.status === "NEEDS_REUPLOAD" || existing.status === "REJECTED";
        return (
          <div key={type} className="flex items-center justify-between rounded-lg border border-ink-100 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-800">{titleCase(type)}</p>
              <p className="text-xs text-ink-400">
                {existing
                  ? `${existing.fileName} · ${titleCase(existing.status)}`
                  : "Not uploaded yet"}
              </p>
            </div>
            <div>
              <input
                ref={(el) => (inputRefs.current[type] = el)}
                type="file"
                className="hidden"
                onChange={(e) => handleFile(type, e.target.files?.[0])}
              />
              <Button
                size="sm"
                variant={needsAction ? "primary" : "secondary"}
                onClick={() => inputRefs.current[type]?.click()}
                loading={upload.isPending && upload.variables?.type === type}
              >
                <UploadCloud className="h-3.5 w-3.5" />
                {existing && !needsAction ? "Replace" : "Upload"}
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
