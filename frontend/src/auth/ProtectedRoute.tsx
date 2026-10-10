import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-stone-50" aria-live="polite">
        <p className="text-sm font-medium text-brand-700">{t("common.loading")}</p>
      </main>
    );
  }

  return user
    ? <Outlet />
    : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}