import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <main className="mx-auto grid min-h-[60vh] max-w-3xl content-center justify-items-start px-4 py-10 sm:px-6">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-700">404</p>
      <h1 className="mt-3 text-3xl font-semibold text-slate-950">{t("notFound.title")}</h1>
      <p className="mt-2 text-sm text-slate-600">{t("notFound.body")}</p>
      <Link className="mt-6 rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-800" to="/">{t("common.backHome")}</Link>
    </main>
  );
}