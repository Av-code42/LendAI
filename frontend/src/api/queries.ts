import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  AgentEvent,
  AuditEvent,
  DocumentRecord,
  DocumentType,
  HumanReviewCase,
  LoanApplication,
  ReviewAction,
} from "@/types/domain";

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
    queryFn: () => api.get<LoanApplication[]>("/applications"),
  });
}

export function useApplication(id: string | undefined, opts?: { poll?: boolean }) {
  return useQuery({
    queryKey: qk.application(id ?? ""),
    queryFn: () => api.get<LoanApplication>(`/applications/${id}`),
    enabled: Boolean(id),
    refetchInterval: opts?.poll ? 2000 : false,
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      requestedAmount: number;
      tenureMonths: number;
      purpose: string;
      fullName: string;
      email: string;
      phone: string;
      monthlyIncome: number;
    }) => api.post<LoanApplication>("/applications", input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.applications }),
  });
}

export function useSubmitApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<LoanApplication>(`/applications/${id}/submit`),
    onSuccess: (app) => {
      qc.invalidateQueries({ queryKey: qk.applications });
      qc.setQueryData(qk.application(app.id), app);
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ applicationId, type, fileName }: { applicationId: string; type: DocumentType; fileName: string }) =>
      api.post<DocumentRecord>(`/applications/${applicationId}/documents`, { type, fileName }),
    onSuccess: (_doc, vars) => {
      qc.invalidateQueries({ queryKey: qk.application(vars.applicationId) });
    },
  });
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => api.post<LoanApplication>(`/applications/${applicationId}/agent/run`),
    onSuccess: (app) => {
      qc.setQueryData(qk.application(app.id), app);
      qc.invalidateQueries({ queryKey: qk.agentEvents(app.id) });
      qc.invalidateQueries({ queryKey: qk.applications });
    },
  });
}

export function useAgentEvents(applicationId: string | undefined) {
  return useQuery({
    queryKey: qk.agentEvents(applicationId ?? ""),
    queryFn: () => api.get<AgentEvent[]>(`/applications/${applicationId}/agent/events`),
    enabled: Boolean(applicationId),
  });
}

export function useAuditEvents(applicationId: string | undefined) {
  return useQuery({
    queryKey: qk.auditEvents(applicationId ?? ""),
    queryFn: () => api.get<AuditEvent[]>(`/applications/${applicationId}/audit-events`),
    enabled: Boolean(applicationId),
  });
}

export function useReviewCases() {
  return useQuery({
    queryKey: qk.reviews,
    queryFn: () => api.get<HumanReviewCase[]>("/reviews"),
  });
}

export function useReviewCase(id: string | undefined) {
  return useQuery({
    queryKey: qk.review(id ?? ""),
    queryFn: () => api.get<HumanReviewCase>(`/reviews/${id}`),
    enabled: Boolean(id),
  });
}

export function useDecideReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      reviewId,
      ...body
    }: {
      reviewId: string;
      userId: string;
      userName: string;
      action: ReviewAction;
      reasonCode: string;
      comment: string;
      modifiedOfferAmount?: number;
    }) => api.post<HumanReviewCase>(`/reviews/${reviewId}/decision`, body),
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
    mutationFn: (applicationId: string) => api.post<LoanApplication>(`/applications/${applicationId}/offer/accept`),
    onSuccess: (app) => qc.setQueryData(qk.application(app.id), app),
  });
}

export function useSignAgreement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => api.post<LoanApplication>(`/applications/${applicationId}/agreement`),
    onSuccess: (app) => qc.setQueryData(qk.application(app.id), app),
  });
}

export function useDisburse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => api.post<LoanApplication>(`/applications/${applicationId}/disbursal`),
    onSuccess: (app) => qc.setQueryData(qk.application(app.id), app),
  });
}
