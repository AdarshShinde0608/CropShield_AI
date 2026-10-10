import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import MobileTabBar from "./components/layout/MobileTabBar";
import SkipLink from "./components/common/SkipLink";
import MlStatusNotice from "./components/common/MlStatusNotice";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const FieldDetailPage = lazy(() => import("./pages/FieldDetailPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const MethodologyPage = lazy(() => import("./pages/MethodologyPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
const QueuePage = lazy(() => import("./pages/QueuePage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

function AppShell() {
  return (
    <div className="min-h-screen bg-[#f4f8f5]">
      <SkipLink />
      <Sidebar />
      <div className="min-h-screen lg:pl-72">
        <TopBar />
        <MlStatusNotice />
        <OutletContent />
      </div>
      <MobileTabBar />
    </div>
  );
}

function OutletContent() {
  return <Outlet />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<RouteLoading />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/methodology" element={<MethodologyPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<AppShell />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="fields/:fieldId" element={<FieldDetailPage />} />
                  <Route path="queue" element={<QueuePage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function RouteLoading() {
  const { t } = useTranslation();
  return <main aria-live="polite" className="grid min-h-screen place-items-center bg-[#f5f7f2]"><p className="text-sm font-semibold text-brand-800">{t("common.loading")}</p></main>;
}