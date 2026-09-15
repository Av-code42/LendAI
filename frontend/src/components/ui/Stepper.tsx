import { Check, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { STATUS_META } from "@/lib/statusMeta";
import { APPLICATION_STATUS_ORDER, type ApplicationStatus } from "@/types/domain";

/**
 * Visualizes the PRD state machine:
 * DRAFT -> SUBMITTED -> DATA_COLLECTION -> VERIFICATION -> RISK_ASSESSMENT
 *       -> POLICY_EVALUATION -> [AUTO_APPROVE/HUMAN_REVIEW/DECLINED] -> OFFER
 *       -> AGREEMENT -> MOCK_DISBURSAL
 */
export function Stepper({ status }: { status: ApplicationStatus }) {
  const isDeclined = status === "DECLINED";
  const isWaiting = status === "WAITING_FOR_DOCUMENT";
  const effectiveStatus: ApplicationStatus =
    status === "AUTO_APPROVED" ? "HUMAN_REVIEW" : status; // auto-approve visually passes through the same slot as review
  const currentIndex = APPLICATION_STATUS_ORDER.indexOf(
    isWaiting ? "DATA_COLLECTION" : isDeclined ? "POLICY_EVALUATION" : effectiveStatus
  );

  return (
    <div className="flex flex-wrap items-center gap-y-3">
      {APPLICATION_STATUS_ORDER.map((step, index) => {
        const isReviewSlot = step === "HUMAN_REVIEW";
        const label = isReviewSlot
          ? status === "AUTO_APPROVED"
            ? "Auto-Approved"
            : "Decision"
          : STATUS_META[step].label;
        // A step only checks off once its slot is actually *complete*.
        // AUTO_APPROVED/MOCK_DISBURSAL finish their slot; anything still
        // pending a downstream action (HUMAN_REVIEW awaiting a decision,
        // OFFER awaiting acceptance, etc.) stays "in progress" instead of
        // falsely showing a checkmark.
        const isResolvedTerminal = status === "AUTO_APPROVED" || status === "MOCK_DISBURSAL";
        const done = index < currentIndex || (index === currentIndex && isResolvedTerminal);
        const isCurrent = index === currentIndex && !done && !isDeclined;
        const failed = isDeclined && isReviewSlot;

        return (
          <div key={step} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold",
                  failed
                    ? "border-danger-500 bg-danger-500 text-white"
                    : done
                    ? "border-brand-600 bg-brand-600 text-white"
                    : isCurrent
                    ? "border-brand-500 bg-white text-brand-600"
                    : "border-ink-200 bg-white text-ink-400"
                )}
              >
                {failed ? <X className="h-3.5 w-3.5" /> : done ? <Check className="h-3.5 w-3.5" /> : index + 1}
              </div>
              <span
                className={cn(
                  "max-w-[6.5rem] text-center text-[11px] leading-tight",
                  done || isCurrent ? "font-medium text-ink-800" : "text-ink-400"
                )}
              >
                {label}
              </span>
            </div>
            {index < APPLICATION_STATUS_ORDER.length - 1 && (
              <div
                className={cn(
                  "mx-1.5 h-px w-6 sm:w-10",
                  index < currentIndex ? "bg-brand-600" : "bg-ink-200"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
