import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { getField, getFieldTimeseries } from "../api/fields";
import AdvicePanel from "../components/field/AdvicePanel";
import ActionTracker from "../components/field/ActionTracker";
import ConfidenceMeter from "../components/field/ConfidenceMeter";
import EvidenceList from "../components/field/EvidenceList";
import NdviChart from "../components/field/NdviChart";
import RainfallBars from "../components/field/RainfallBars";
import RiskBadge from "../components/field/RiskBadge";
import ReadAloudButton from "../components/common/ReadAloudButton";
import ModelResultCard from "../components/field/ModelResultCard";
import SensitivityPreview from "../components/field/SensitivityPreview";
import { getModelInfo } from "../api/ml";
import { getThresholdRange } from "../lib/modelInfo";
import { useMlStatus } from "../hooks/useMlStatus";
import type { Language } from "../types/api";

export default function FieldDetailPage() {
  const { t, i18n } = useTranslation();
  const { fieldId = "" } = useParams();
  const mlStatus = useMlStatus();
  const modelInfoQuery = useQuery({
    queryKey: ["model-info"],
    queryFn: getModelInfo,
    enabled: mlStatus.ready,
    retry: false
  });
  const fieldQuery = useQuery({
    queryKey: ["field", fieldId],
    queryFn: () => getField(fieldId),
    enabled: Boolean(fieldId)
  });
  const timeseriesQuery = useQuery({
    queryKey: ["field-timeseries", fieldId],
    queryFn: () => getFieldTimeseries(fieldId),
    enabled: Boolean(fieldId)
  });

  if (fieldQuery.isLoading) return <StateMessage>{t("common.loading")}</StateMessage>;
  if (fieldQuery.isError || !fieldQuery.data) return <StateMessage role="alert">{t("field.notFound")}</StateMessage>;
  const field = fieldQuery.data;
  const thresholdRange = getThresholdRange(modelInfoQuery.data);
  const points = timeseriesQuery.data?.points ?? [];
  const rainfall = timeseriesQuery.data?.rainfall ?? [];
  const observationsByDate = new Map(points.map((point) => [point.date, point]));
  const chartPoints = Array.from(new Set([...points.map((point) => point.date), ...rainfall.map((point) => point.date)]))
    .sort()
    .map((date) => observationsByDate.get(date) ?? {
      date,
      ndvi: null,
      baseline_median: null,
      band_low: null,
      band_high: null,
      z: null,
      low_quality: false,
      is_interpolated: false
    });
  const language: Language = i18n.resolvedLanguage === "mr" || i18n.resolvedLanguage === "hi" ? i18n.resolvedLanguage : "en";
  const explanation = [
    t("field.readAloudIntro", { risk: t(`risk.${field.risk}`), field: field.field_id }),
    t("field.readAloudConfidence", { confidence: t(`confidence.${field.confidence_label}`) }),
    field.z_score == null ? "" : t("field.readAloudZ", { value: field.z_score.toFixed(2) }),
    field.pct_below_normal == null ? "" : t("field.readAloudPct", { value: field.pct_below_normal.toFixed(1) }),
    field.rain_context ? t("field.readAloudRain", { context: t(`rainContext.${field.rain_context}`) }) : "",
    field.advice_key ? t(field.advice_key, { defaultValue: field.advice ?? t("advice.fallback") }) : field.advice ?? t("advice.fallback"),
    t("field.limitation")
  ].filter(Boolean).join(" ");

  return (
    <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 pb-24 sm:px-6 sm:py-9" id="main-content" tabIndex={-1}>
      <Link className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900" to="/">
        <span aria-hidden="true">←</span> {t("common.backHome")}
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-7">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-700">{t("field.title")}</p>
          <h1 className="mt-2 break-words text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{field.field_id}</h1>
          {field.pct_below_normal != null && (
            <p className="mt-2 inline-flex rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-800">
              {t("field.belowNormalChip", { percent: field.pct_below_normal.toFixed(1) })}
            </p>
          )}
          <p className="mt-2 text-sm text-slate-600">{t("field.latest")}: {field.latest_obs_date ?? "—"}</p>
        </div>
        <div className="flex flex-wrap items-center gap-5">
          <RiskBadge risk={field.risk} />
          {field.risk === "alert" && field.severity && (
            <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-800">
              {t(`severity.${field.severity}`)}
            </span>
          )}
          <ConfidenceMeter label={field.confidence_label} value={field.confidence} />
        </div>
      </header>
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.7fr)_minmax(270px,0.8fr)]">
        <div className="min-w-0 space-y-5">
          <ModelResultCard field={field} fallbackPoints={points} />
          <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-4">
              <h2 className="font-semibold text-slate-950">{t("field.ndviHistory")}</h2>
              <p className="mt-1 text-xs text-slate-500">{t("chart.bandLegend")}</p>
            </div>
            {timeseriesQuery.isLoading && <p className="py-8 text-sm text-slate-600" role="status">{t("common.loading")}</p>}
            {timeseriesQuery.isError && <p className="py-8 text-sm text-red-700" role="alert">{t("common.error")}</p>}
            {timeseriesQuery.data && (
              <>
                <NdviChart dropStart={timeseriesQuery.data.drop_start} points={chartPoints} />
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-600">
                  <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-brand-700" />{t("chart.observed")}</span>
                  <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-600" />{t("chart.lowQuality")}</span>
                  <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-slate-500" />{t("chart.interpolated")}</span>
                </div>
                <h3 className="mt-6 text-sm font-semibold text-slate-800">{t("chart.rainfall")}</h3>
                <RainfallBars points={chartPoints} rainfall={rainfall} />
              </>
            )}
            {timeseriesQuery.data && points.length === 0 && <p className="text-sm text-slate-500">{t("common.empty")}</p>}
          </section>
          <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6">
            <h2 className="mb-4 font-semibold text-slate-950">{t("field.evidence")}</h2>
            <EvidenceList field={field} points={points} />
          </section>
          <ActionTracker fieldId={field.field_id} />
        </div>
        <aside className="space-y-5">
          {mlStatus.ready && modelInfoQuery.data?.enabled === true && thresholdRange && (
            <SensitivityPreview
              fieldId={field.field_id}
              range={thresholdRange}
              savedRisk={field.risk}
            />
          )}
          <AdvicePanel field={field} />
          <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-slate-950">{t("readAloud.heading")}</h2>
            <ReadAloudButton language={language} text={explanation} />
          </section>
        </aside>
      </section>
    </main>
  );
}

function StateMessage({ children, role = "status" }: { children: ReactNode; role?: "status" | "alert" }) {
  return <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6" id="main-content" tabIndex={-1}><div className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-slate-600" role={role}>{children}</div></main>;
}
