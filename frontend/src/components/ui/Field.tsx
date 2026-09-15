import { forwardRef, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface FieldWrapperProps {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}

export function FieldWrapper({ label, htmlFor, error, hint, children }: FieldWrapperProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-ink-800">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-ink-500">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-danger-600">{error}</p>}
    </div>
  );
}

const inputBase =
  "w-full rounded-lg border bg-white px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40";

// forwardRef is required here, not cosmetic: react-hook-form's register()
// passes a ref that must reach the real DOM <input>/<select> so it can
// read the field's value at validation/submit time (it's an uncontrolled-
// input library -- without the ref attaching, every registered field
// silently reads as undefined on submit, regardless of what's visibly
// typed in it).
export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { error?: boolean }>(
  ({ error, className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(inputBase, error ? "border-danger-400" : "border-ink-200 focus:border-brand-500", className)}
        {...props}
      />
    );
  }
);
TextInput.displayName = "TextInput";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { error?: boolean }>(
  ({ error, className, children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(inputBase, error ? "border-danger-400" : "border-ink-200 focus:border-brand-500", className)}
        {...props}
      >
        {children}
      </select>
    );
  }
);
Select.displayName = "Select";
