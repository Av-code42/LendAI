import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import {
  mapAgentEvent,
  mapApplication,
  mapAuditEvent,
  mapDocument,
  mapHumanReviewCase,
} from "@/api/mappers";
import type { DocumentType, LoanApplication, ReviewAction } from "@/types/domain";

export const qk = {
  applications: ["applications"] as const,
  application: (id: string) => ["applications", id] as const,
  agentEvents: (id: string) => ["applications", id, "agent-events"] as const,
  auditEvents: (id: string) => ["applications", id, "audit-events"] as const,
  reviews: ["reviews"] as const,
  review: (id: string) => ["reviews", id] as const,
};

export function useApplications() {
  return useQuery({
    queryKey: qk.applications,
    queryFn: async () => (await api.get<any[]>("/applications")).map(mapApplication),
  });
}

export function useApplication(id: string | undefined, opts?: { poll?: boolean }) {
  return useQuery({
    queryKey: qk.application(id ?? ""),
    queryFn: async () => mapApplication(await api.get<any>(`/applications/${id}`)),
    enabled: Boolean(id),
    refetchInterval: opts?.poll ? 2000 : false,
  });
}

/** Fields the real policy/credit engine needs that the UI form now collects
 * (the mock never required them -- see backend/app/schemas/api.py's
 * ApplicationCreate). */
export interface CreateApplicationInput {
  requestedAmount: number;
  tenureMonths: number;
  purpose: string;
  fullName: string;
  email: string;
  phone: string;
  monthlyIncome: number;
  age: number;
  employmentTenureMonths: number;
  bureauScore: number;
  relationshipMonths: number;
  activeLoans?: number;
  existingMonthlyEmi?: number;
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateApplicationInput) => {
      const body = {
        full_name: input.fullName,
        email: input.email,
        phone: input.phone,
        monthly_income: input.monthlyIncome,
        age: input.age,
        employment_tenure_months: input.employmentTenureMonths,
        bureau_score: input.bureauScore,
        relationship_months: input.relationshipMonths,
        active_loans: input.activeLoans ?? 0,
        existing_monthly_emi: input.existingMonthlyEmi ?? 0,
        requested_amount: input.requestedAmount,
        tenure_months: input.tenureMonths,
        purpose: input.purpose,
        channel: "WEB",
      };
      return mapApplication(await api.post<any>("/applications", body));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.applications }),
  });
}

export function useSubmitApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => mapApplication(await api.post<any>(`/applications/${id}/submit`)),
    onSuccess: (app: LoanApplication) => {
      qc.invalidateQueries({ queryKey: qk.applications });
      qc.setQueryData(qk.application(app.id), app);
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      applicationId,
      type,
      fileName,
    }: {
      applicationId: string;
      type: DocumentType;
      fileName: string;
    }) =>
      mapDocument(
        await api.post<any>(`/applications/${applicationId}/documents`, {
          document_type: type,
          file_name: fileName,
        })
      ),
    onSuccess: (_doc, vars) => {
      qc.invalidateQueries({ queryKey: qk.application(vars.applicationId) });
    },
  });
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (applicationId: string) =>
      mapApplication(await api.post<any>(`/applications/${applicationId}/agent/run`)),
    onSuccess: (app: LoanApplication) => {
      qc.setQueryData(qk.application(app.id), app);
      qc.invalidateQueries({ queryKey: qk.agentEvents(app.id) });
      qc.invalidateQueries({ queryKey: qk.applications });
    },
  });
}

export function useAgentEvents(applicationId: string | undefined) {
  return useQuery({
    queryKey: qk.agentEvents(applicationId ?? ""),
    queryFn: async () => (await api.get<any[]>(`/applications/${applicationId}/agent/events`)).map(mapAgentEvent),
    enabled: Boolean(applicationId),
  });
}

export function useAuditEvents(applicationId: string | undefined) {
  return useQuery({
    queryKey: qk.auditEvents(applicationId ?? ""),
    queryFn: async () => (await api.get<any[]>(`/applications/${applicationId}/audit-events`)).map(mapAuditEvent),
    enabled: Boolean(applicationId),
  });
}

export function useReviewCases() {
  return useQuery({
    queryKey: qk.reviews,
    queryFn: async () => (await api.get<any[]>("/reviews")).map(mapHumanReviewCase),
  });
}

export function useReviewCase(id: string | undefined) {
  return useQuery({
    queryKey: qk.review(id ?? ""),
    queryFn: async () => mapHumanReviewCase(await api.get<any>(`/reviews/${id}`)),
    enabled: Boolean(id),
  });
}

export function useDecideReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      reviewId,
      userId,
      userName,
      action,
      reasonCode,
      comment,
      modifiedOfferAmount,
    }: {
      reviewId: string;
      userId: string;
      userName: string;
      action: ReviewAction;
      reasonCode: string;
      comment: string;
      modifiedOfferAmount?: number;
    }) =>
      mapHumanReviewCase(
        await api.post<any>(`/reviews/${reviewId}/decision`, {
          user_id: userId,
          user_name: userName,
          action,
          reason_code: reasonCode,
          comment,
          modified_offer_amount: modifiedOfferAmount,
        })
      ),
    onSuccess: (review) => {
      qc.invalidateQueries({ queryKey: qk.reviews });
      qc.setQueryData(qk.review(review.id), review);
      qc.invalidateQueries({ queryKey: qk.application(review.applicationId) });
    },
  });
}

export function useAcceptOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (applicationId: string) =>
      mapApplication(await api.post<any>(`/applications/${applicationId}/offer/accept`)),
    onSuccess: (app: LoanApplication) => qc.setQueryData(qk.application(app.id), app),
  });
}

export function useSignAgreement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (applicationId: string) =>
      mapApplication(await api.post<any>(`/applications/${applicationId}/agreement`)),
    onSuccess: (app: LoanApplication) => qc.setQueryData(qk.application(app.id), app),
  });
}

export function useDisburse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (applicationId: string) =>
      mapApplication(await api.post<any>(`/applications/${applicationId}/disbursal`)),
    onSuccess: (app: LoanApplication) => qc.setQueryData(qk.application(app.id), app),
  });
}
