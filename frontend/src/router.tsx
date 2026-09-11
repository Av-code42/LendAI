import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/features/customer/pages/DashboardPage";
import { NewApplicationPage } from "@/features/customer/pages/NewApplicationPage";
import { ApplicationDetailPage } from "@/features/customer/pages/ApplicationDetailPage";
import { ReviewQueuePage } from "@/features/underwriter/pages/ReviewQueuePage";
import { ReviewDetailPage } from "@/features/underwriter/pages/ReviewDetailPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/customer" replace />} />

      <Route
        path="/customer"
        element={
          <AppShell mode="customer">
            <DashboardPage />
          </AppShell>
        }
      />
      <Route
        path="/customer/new"
        element={
          <AppShell mode="customer">
            <NewApplicationPage />
          </AppShell>
        }
      />
      <Route
        path="/customer/applications/:id"
        element={
          <AppShell mode="customer">
            <ApplicationDetailPage />
          </AppShell>
        }
      />

      <Route
        path="/review"
        element={
          <AppShell mode="underwriter">
            <ReviewQueuePage />
          </AppShell>
        }
      />
      <Route
        path="/review/:id"
        element={
          <AppShell mode="underwriter">
            <ReviewDetailPage />
          </AppShell>
        }
      />

      <Route path="*" element={<Navigate to="/customer" replace />} />
    </Routes>
  );
}
