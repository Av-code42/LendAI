import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateApplication, useSubmitApplication } from "@/api/queries";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { FieldWrapper, TextInput } from "@/components/ui/Field";
import { formatCurrency } from "@/lib/format";
import { POLICY_THRESHOLDS } from "@/lib/policy";

const schema = z.object({
  fullName: z.string().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email"),
  phone: z.string().min(10, "Enter a valid phone number"),
  monthlyIncome: z.coerce.number().positive("Enter your monthly income"),
  requestedAmount: z.coerce.number().positive("Enter an amount"),
  tenureMonths: z.coerce.number().int().min(6).max(60),
  purpose: z.string().min(3, "Tell us what the loan is for"),
});

type FormValues = z.infer<typeof schema>;

export function NewApplicationPage() {
  const navigate = useNavigate();
  const createApplication = useCreateApplication();
  const submitApplication = useSubmitApplication();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tenureMonths: 24, purpose: "" },
  });

  const income = Number(watch("monthlyIncome")) || 0;
  const amount = Number(watch("requestedAmount")) || 0;
  const maxEligible = income * POLICY_THRESHOLDS.maxAmountMultipleOfIncome;

  const onSubmit = async (values: FormValues) => {
    const app = await createApplication.mutateAsync(values);
    await submitApplication.mutateAsync(app.id);
    navigate(`/customer/applications/${app.id}`);
  };

  const submitting = createApplication.isPending || submitApplication.isPending;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink-900">New Personal Loan Application</h1>
        <p className="text-sm text-ink-500">
          A few basic details to get started — you'll upload supporting documents in the next step.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <Card>
          <CardHeader title="Applicant details" />
          <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FieldWrapper label="Full name" htmlFor="fullName" error={errors.fullName?.message}>
              <TextInput id="fullName" placeholder="As per PAN card" {...register("fullName")} error={!!errors.fullName} />
            </FieldWrapper>
            <FieldWrapper label="Email" htmlFor="email" error={errors.email?.message}>
              <TextInput id="email" type="email" placeholder="you@example.com" {...register("email")} error={!!errors.email} />
            </FieldWrapper>
            <FieldWrapper label="Phone" htmlFor="phone" error={errors.phone?.message}>
              <TextInput id="phone" placeholder="+91 90000 00000" {...register("phone")} error={!!errors.phone} />
            </FieldWrapper>
            <FieldWrapper label="Monthly income (₹)" htmlFor="monthlyIncome" error={errors.monthlyIncome?.message}>
              <TextInput
                id="monthlyIncome"
                type="number"
                placeholder="75000"
                {...register("monthlyIncome")}
                error={!!errors.monthlyIncome}
              />
            </FieldWrapper>
          </CardBody>
        </Card>

        <Card className="mt-4">
          <CardHeader title="Loan details" />
          <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FieldWrapper
              label="Requested amount (₹)"
              htmlFor="requestedAmount"
              error={errors.requestedAmount?.message}
              hint={
                income > 0
                  ? `Up to ${formatCurrency(maxEligible)} based on policy PL_2026_V1 (8x monthly income) — final eligibility is decided during policy evaluation.`
                  : undefined
              }
            >
              <TextInput
                id="requestedAmount"
                type="number"
                placeholder="500000"
                {...register("requestedAmount")}
                error={!!errors.requestedAmount}
              />
            </FieldWrapper>
            <FieldWrapper label="Tenure (months)" htmlFor="tenureMonths" error={errors.tenureMonths?.message}>
              <TextInput
                id="tenureMonths"
                type="number"
                min={6}
                max={60}
                defaultValue={24}
                {...register("tenureMonths")}
                error={!!errors.tenureMonths}
              />
            </FieldWrapper>
            <div className="sm:col-span-2">
              <FieldWrapper label="Purpose" htmlFor="purpose" error={errors.purpose?.message}>
                <TextInput id="purpose" placeholder="e.g. Home renovation" {...register("purpose")} error={!!errors.purpose} />
              </FieldWrapper>
            </div>
          </CardBody>
        </Card>

        {income > 0 && amount > maxEligible && (
          <p className="mt-3 text-sm text-warning-700">
            Heads up: {formatCurrency(amount)} is above the {formatCurrency(maxEligible)} guideline for your
            declared income. You can still submit — policy evaluation will make the final call.
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate("/customer")}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            Submit Application
          </Button>
        </div>
      </form>
    </div>
  );
}
