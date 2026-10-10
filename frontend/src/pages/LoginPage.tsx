import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AuthLayout from "../auth/AuthLayout";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../lib/apiError";

interface LoginLocationState {
  from?: string;
}

export default function LoginPage() {
  const { t } = useTranslation();
  const { login, user, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) return null;
  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError(t("auth.emailRequired"));
      return;
    }
    if (password.length < 8) {
      setError(t("auth.passwordRequired"));
      return;
    }
    setIsSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      const state = location.state as LoginLocationState | null;
      navigate(state?.from ?? "/", { replace: true });
    } catch (reason) {
      setError(apiErrorMessage(reason, t("auth.loginFailure")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout>
      <div className="w-full">
        <div className="mb-8">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-brand-700 lg:hidden">{t("auth.loginEyebrow")}</p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{t("auth.loginTitle")}</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">{t("auth.loginSubtitle")}</p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-semibold text-slate-800">{t("common.email")}</label>
            <input
              autoComplete="email"
              className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 text-sm shadow-sm placeholder:text-slate-400 focus:border-brand-500 focus:ring-brand-500"
              id="email"
              name="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              required
              type="email"
              value={email}
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label htmlFor="password" className="block text-sm font-semibold text-slate-800">{t("common.password")}</label>
            </div>
            <div className="relative">
              <input
                autoComplete="current-password"
                className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 pr-20 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
                id="password"
                minLength={8}
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? t("common.hidePassword") : t("common.showPassword")}
                className="absolute inset-y-0 right-3 my-auto text-xs font-semibold text-brand-700 hover:text-brand-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600"
                onClick={() => setShowPassword((shown) => !shown)}
                type="button"
              >
                {showPassword ? t("common.hidePassword") : t("common.showPassword")}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">{t("auth.passwordHint")}</p>
          </div>
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
              {error}
            </div>
          )}
          <button
            className="inline-flex w-full items-center justify-center rounded-xl bg-brand-700 px-5 py-3.5 text-sm font-bold text-white shadow-sm transition hover:bg-brand-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSubmitting}
            type="submit"
          >
            {isSubmitting ? t("auth.loginLoading") : t("auth.loginButton")}
          </button>
        </form>

        <p className="mt-7 text-center text-sm text-slate-600">
          {t("auth.noAccount")}{" "}
          <Link className="font-bold text-brand-700 hover:text-brand-900" to="/register">{t("auth.createAccount")}</Link>
        </p>
      </div>
    </AuthLayout>
  );
}