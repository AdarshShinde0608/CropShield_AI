import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AuthLayout from "../auth/AuthLayout";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../lib/apiError";

export default function RegisterPage() {
  const { t, i18n } = useTranslation();
  const { register, user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) return null;
  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    if (!name.trim()) {
      setError(t("auth.nameRequired"));
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError(t("auth.emailRequired"));
      return;
    }
    if (password.length < 8) {
      setError(t("auth.passwordRequired"));
      return;
    }
    if (password !== confirmPassword) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setIsSubmitting(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
        language: i18n.resolvedLanguage === "mr" || i18n.resolvedLanguage === "hi"
          ? i18n.resolvedLanguage
          : "en"
      });
      navigate("/", { replace: true });
    } catch (reason) {
      setError(apiErrorMessage(reason, t("common.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout>
      <div className="w-full">
        <div className="mb-7">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-brand-700 lg:hidden">{t("auth.registerEyebrow")}</p>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">{t("auth.registerTitle")}</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">{t("auth.registerSubtitle")}</p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="name" className="mb-2 block text-sm font-semibold text-slate-800">{t("common.name")}</label>
            <input
              autoComplete="name"
              className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
              id="name"
              maxLength={100}
              minLength={1}
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
          </div>
          <div>
            <label htmlFor="email" className="mb-2 block text-sm font-semibold text-slate-800">{t("common.email")}</label>
            <input
              autoComplete="email"
              className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-2 block text-sm font-semibold text-slate-800">{t("common.password")}</label>
            <div className="relative">
              <input
                autoComplete="new-password"
                className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 pr-20 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
                id="password"
                minLength={8}
                onChange={(event) => setPassword(event.target.value)}
                required
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? t("common.hidePassword") : t("common.showPassword")}
                className="absolute inset-y-0 right-3 my-auto text-xs font-semibold text-brand-700"
                onClick={() => setShowPassword((shown) => !shown)}
                type="button"
              >
                {showPassword ? t("common.hidePassword") : t("common.showPassword")}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">{t("auth.passwordHint")}</p>
          </div>
          <div>
            <label htmlFor="confirm-password" className="mb-2 block text-sm font-semibold text-slate-800">{t("auth.confirmPassword")}</label>
            <input
              autoComplete="new-password"
              className="form-input w-full rounded-xl border-slate-200 bg-white px-4 py-3 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
              id="confirm-password"
              minLength={8}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              type={showPassword ? "text" : "password"}
              value={confirmPassword}
            />
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
            {isSubmitting ? t("auth.registerLoading") : t("auth.registerButton")}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          {t("auth.hasAccount")}{" "}
          <Link className="font-bold text-brand-700 hover:text-brand-900" to="/login">{t("auth.signIn")}</Link>
        </p>
      </div>
    </AuthLayout>
  );
}