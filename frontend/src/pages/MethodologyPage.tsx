import type { PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getMethodology } from "../api/regions";
import { getModelInfo } from "../api/ml";
import { useAuth } from "../auth/AuthContext";
import LanguageSwitcher from "../components/common/LanguageSwitcher";
import SyntheticBanner from "../components/common/SyntheticBanner";
import SkipLink from "../components/common/SkipLink";
import { displayMetadata } from "../lib/modelInfo";

export default function MethodologyPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const modelInfoQuery = useQuery({
    queryKey: ["model-info"],
    queryFn: getModelInfo,
    enabled: Boolean(user),
    retry: false
  });
  const methodologyQuery = useQuery({
    queryKey: ["methodology"],
    queryFn: getMethodology
  });

  return (
    <main className="mx-auto min-h-screen max-w-5xl space-y-6 px-4 py-6 sm:px-6 sm:py-10" id="main-content" tabIndex={-1}>
      <SkipLink />
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          {user && <Link className="text-sm font-semibold text-brand-700 hover:text-brand-900" to="/">← {t("common.backHome")}</Link>}
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{t("methodology.title")}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">{t("methodology.subtitle")}</p>
        </div>
        {!user && (
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <Link className="rounded-xl bg-brand-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-800" to="/login">{t("auth.signIn")}</Link>
          </div>
        )}
      </header>
      {methodologyQuery.isLoading && <Message role="status">{t("common.loading")}</Message>}
      {methodologyQuery.isError && <Message role="alert">{t("common.error")}</Message>}
      {methodologyQuery.data && (
        <>
          {methodologyQuery.data.params.is_synthetic === true && <SyntheticBanner />}
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950" role="note">
            {t("methodology.syntheticDisclaimer")}
          </div>
          <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-7">
            <h2 className="text-lg font-semibold text-slate-950">{t("methodology.steps")}</h2>
            <ol className="mt-4 space-y-3">
              {methodologyQuery.data.method_steps.map((step, index) => (
                <li className="flex gap-3 text-sm leading-6 text-slate-700" key={`${index}-${step}`}>
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand-800">{index + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </section>
          <section className="grid gap-5 md:grid-cols-2">
            <InfoPanel title={t("methodology.params")}>
              {methodologyQuery.data.run_id
                ? <pre className="overflow-auto text-xs leading-5 text-slate-700">{JSON.stringify(methodologyQuery.data.params, null, 2)}</pre>
                : <p className="text-sm text-slate-600">{t("methodology.noRun")}</p>}
            </InfoPanel>
            <InfoPanel title={t("methodology.validation")}>
              {methodologyQuery.data.validation_report
                ? <pre className="overflow-auto text-xs leading-5 text-slate-700">{JSON.stringify(methodologyQuery.data.validation_report, null, 2)}</pre>
                : <p className="text-sm text-slate-600">{t("methodology.noValidation")}</p>}
            </InfoPanel>
          </section>
          <section className="rounded-2xl border border-stone-200 bg-white p-5 sm:p-7" aria-labelledby="about-model-heading">
            <h2 id="about-model-heading" className="text-lg font-semibold text-slate-950">{t("ml.aboutModel")}</h2>
            {modelInfoQuery.isLoading && user && <p className="mt-4 text-sm text-slate-600" role="status">{t("common.loading")}</p>}
            {modelInfoQuery.isError && user && <p className="mt-4 text-sm text-amber-900" role="status">{t("ml.metadataUnavailable")}</p>}
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <MetadataItem label={t("ml.modelName")} value={modelInfoQuery.data?.name} fallback={t("common.notAvailable")} />
              <MetadataItem label={t("ml.modelVersion")} value={modelInfoQuery.data?.model_version} fallback={t("common.notAvailable")} />
              <MetadataItem label={t("ml.modelTask")} value={modelInfoQuery.data?.task} fallback={t("common.notAvailable")} />
              <MetadataItem
                label={t("ml.trainedOn")}
                value={modelInfoQuery.data?.training_data ?? modelInfoQuery.data?.trained_on}
                fallback={t("common.notAvailable")}
              />
              <MetadataItem
                label={t("ml.measuredMetrics")}
                value={modelInfoQuery.data?.measured_metrics ?? modelInfoQuery.data?.metrics}
                fallback={t("ml.notYetMeasured")}
              />
              <MetadataItem
                label={t("ml.licenceAttribution")}
                value={[
                  displayMetadata(modelInfoQuery.data?.licence ?? modelInfoQuery.data?.license),
                  displayMetadata(modelInfoQuery.data?.attribution)
                ].filter(Boolean).join(" · ")}
                fallback={t("common.notAvailable")}
              />
            </dl>
            <div className="mt-5 border-t border-stone-100 pt-4">
              <h3 className="text-sm font-semibold text-slate-800">{t("ml.limitations")}</h3>
              {modelInfoQuery.data?.limitations?.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
                  {modelInfoQuery.data.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{t("common.notAvailable")}</p>
              )}
            </div>
          </section>
          <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 sm:p-7">
            <h2 className="text-lg font-semibold text-amber-950">{t("methodology.limitations")}</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-amber-950">
              {methodologyQuery.data.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}

function MetadataItem({ label, value, fallback }: { label: string; value: unknown; fallback: string }) {
  const content = displayMetadata(value);
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm leading-6 text-slate-800">{content ?? fallback}</dd>
    </div>
  );
}

function InfoPanel({ title, children }: PropsWithChildren<{ title: string }>) {
  return <section className="min-w-0 rounded-2xl border border-stone-200 bg-white p-5 sm:p-7"><h2 className="mb-4 text-lg font-semibold text-slate-950">{title}</h2>{children}</section>;
}

function Message({ children, role }: PropsWithChildren<{ role: "status" | "alert" }>) {
  return <div className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-slate-600" role={role}>{children}</div>;
}