import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { getRegionFields, getRegionQueue, getRegionSummary, listRegions } from "../api/regions";
import { getModelInfo, previewRegionScores } from "../api/ml";
import { getThresholdRange } from "../lib/modelInfo";
import { useMlStatus } from "../hooks/useMlStatus";
import RiskMap from "../components/map/RiskMap";
import RiskBadge from "../components/field/RiskBadge";
export default function DashboardPage() {
  const { t } = useTranslation();
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [threshold, setThreshold] = useState<number | null>(null);
  const [debouncedThreshold, setDebouncedThreshold] = useState<number | null>(null);
  const mlStatus = useMlStatus();
  const modelInfoQuery = useQuery({
    queryKey: ["model-info"],
    queryFn: getModelInfo,
    enabled: mlStatus.ready,
    retry: false
  });
  const thresholdRange = getThresholdRange(modelInfoQuery.data);
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: listRegions });
  const region = regionsQuery.data?.[0];
  const summaryQuery = useQuery({
    queryKey: ["region-summary", region?.region_id],
    queryFn: () => getRegionSummary(region!.region_id),
    enabled: Boolean(region?.region_id)
  });
  const fieldsQuery = useQuery({
    queryKey: ["region-fields", region?.region_id],
    queryFn: () => getRegionFields(region!.region_id),
    enabled: Boolean(region?.region_id)
  });
  const queueQuery = useQuery({
    queryKey: ["region-queue", region?.region_id, "top"],
    queryFn: () => getRegionQueue(region!.region_id, { limit: 5 }),
    enabled: Boolean(region?.region_id)
  });
  const regionPreviewQuery = useQuery({
    queryKey: ["region-score-preview", region?.region_id, debouncedThreshold],
    queryFn: () => previewRegionScores(region!.region_id, debouncedThreshold!),
    enabled: drawerOpen && Boolean(region?.region_id) && debouncedThreshold != null,
    retry: false
  });

  useEffect(() => {
    if (!drawerOpen || threshold == null) {
      setDebouncedThreshold(null);
      return;
    }
    const timer = window.setTimeout(() => setDebouncedThreshold(threshold), 450);
    return () => window.clearTimeout(timer);
  }, [drawerOpen, threshold]);

  useEffect(() => {
    if (!drawerOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [drawerOpen]);

  if (regionsQuery.isLoading) return <main id="main-content" tabIndex={-1}><PageMessage>{t("common.loading")}</PageMessage></main>;
  if (regionsQuery.isError) return <main id="main-content" tabIndex={-1}><PageMessage role="alert">{t("common.error")}</PageMessage></main>;
  if (!region) return <main id="main-content" tabIndex={-1}><PageMessage>{t("dashboard.noRegions")}</PageMessage></main>;

  const counts = summaryQuery.data?.counts_by_risk;
  const totalFields = fieldsQuery.data?.features.length;
  const kpis: Array<{ label: string; value: string | number }> = [
    { label: t("dashboard.totalFields"), value: fieldsQuery.isLoading ? "—" : totalFields ?? "—" },
    { label: t("risk.alert"), value: summaryQuery.isLoading ? "—" : counts?.alert ?? "—" },
    { label: t("risk.watch"), value: summaryQuery.isLoading ? "—" : counts?.watch ?? "—" },
    { label: t("risk.cannot_assess"), value: summaryQuery.isLoading ? "—" : counts?.cannot_assess ?? "—" },
    { label: t("risk.normal"), value: summaryQuery.isLoading ? "—" : counts?.normal ?? "—" }
  ];

  return (
    <main className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 pb-24 sm:px-6 sm:py-7 lg:px-8" id="main-content" tabIndex={-1}>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-700">{t("dashboard.region")}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{t("dashboard.title")}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{t("dashboard.subtitle")}</p>
        </div>
        {summaryQuery.data?.latest_observation_date && (
          <span className="rounded-xl border border-stone-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700">
            {t("dashboard.latestObservation")}: {summaryQuery.data.latest_observation_date}
          </span>
        )}
        {mlStatus.ready && modelInfoQuery.data?.enabled === true && thresholdRange && (
          <button
            className="rounded-xl border border-brand-300 bg-white px-4 py-2 text-sm font-semibold text-brand-900 shadow-sm hover:bg-brand-50"
            onClick={() => {
              setThreshold(thresholdRange.default);
              setDrawerOpen(true);
            }}
            type="button"
          >
            {t("ml.regionSensitivity")}
          </button>
        )}
      </header>

      {summaryQuery.isError && <PageMessage role="alert">{t("common.error")}</PageMessage>}
      <section aria-label={t("dashboard.kpis")} className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        {kpis.map((kpi, index) => (
          <article className={`rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5 ${index === 1 ? "border-b-[3px] border-b-red-500" : index === 2 ? "border-b-[3px] border-b-amber-500" : index === 3 ? "border-b-[3px] border-b-slate-400" : index === 4 ? "border-b-[3px] border-b-green-600" : ""}`} key={kpi.label}>
            <div className="flex min-h-7 items-center gap-3">
              <span aria-hidden="true" className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl text-lg font-bold ${index === 1 ? "bg-red-50 text-red-700" : index === 2 ? "bg-amber-50 text-amber-800" : index === 3 ? "bg-slate-100 text-slate-700" : index === 4 ? "bg-green-50 text-green-800" : "bg-brand-50 text-brand-800"}`}>
                {["▦", "△", "⊙", "◩", "✓"][index]}
              </span>
              <span className="text-xs font-semibold text-slate-600">{kpi.label}</span>
            </div>
            <p className="mt-2 pl-[52px] text-2xl font-semibold text-slate-950 sm:text-3xl">{kpi.value}</p>
          </article>
        ))}
      </section>

      {fieldsQuery.isLoading && <MapSkeleton />}
      {fieldsQuery.isError && <PageMessage role="alert">{t("dashboard.mapError")}</PageMessage>}
      {fieldsQuery.data && fieldsQuery.data.features.length === 0 && <PageMessage>{t("common.empty")}</PageMessage>}
      {fieldsQuery.data && fieldsQuery.data.features.length > 0 && (
        <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_350px]">
          <div className="min-w-0 overflow-hidden rounded-3xl border border-stone-200 bg-white p-3 shadow-sm sm:p-5">
            <div className="mb-4 px-1">
              <h2 className="font-semibold text-slate-950">{t("dashboard.mapTitle")}</h2>
              <p className="mt-1 text-xs text-slate-500">{t("dashboard.mapHelp")}</p>
            </div>
            <RiskMap fields={fieldsQuery.data} onSelectField={setSelectedField} selectedFieldId={selectedField} />
          </div>
          <aside className="rounded-3xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="top-fields-heading">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 id="top-fields-heading" className="font-semibold text-slate-950">{t("dashboard.topFields")}</h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">{t("dashboard.topFieldsHelp")}</p>
              </div>
              <Link className="shrink-0 text-xs font-bold text-brand-700 hover:text-brand-900" to="/queue">{t("dashboard.viewQueue")}</Link>
            </div>
            {queueQuery.isLoading && <div className="mt-4 space-y-3" aria-label={t("common.loading")}><div className="h-14 animate-pulse rounded-xl bg-stone-100" /><div className="h-14 animate-pulse rounded-xl bg-stone-100" /></div>}
            {queueQuery.isError && <p className="mt-4 text-sm text-red-700" role="alert">{t("dashboard.queueError")}</p>}
            {queueQuery.data?.length === 0 && <p className="mt-4 text-sm text-slate-500">{t("queue.empty")}</p>}
            {queueQuery.data && queueQuery.data.length > 0 && (
              <ol className="mt-4 divide-y divide-stone-100">
                {queueQuery.data.map((item) => (
                  <li key={item.field_id}>
                    <Link
                      className={`flex items-center justify-between gap-3 rounded-xl px-2 py-3 transition hover:bg-stone-50 ${selectedField === item.field_id ? "bg-brand-50" : ""}`}
                      onMouseEnter={() => setSelectedField(item.field_id)}
                      onMouseLeave={() => setSelectedField(null)}
                      to={`/fields/${encodeURIComponent(item.field_id)}`}
                    >
                      <span className="flex min-w-0 items-center gap-3">
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand-900">{item.priority_rank ?? "—"}</span>
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-slate-900">{item.name ?? item.field_id}</span>
                          <span className="mt-1 block text-xs text-slate-500">{item.latest_obs_date ?? "—"}</span>
                        </span>
                      </span>
                      <RiskBadge risk={item.risk} />
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </aside>
        </section>
      )}
      {drawerOpen && thresholdRange && (
        <div className="fixed inset-0 z-[1000] flex justify-end bg-slate-950/35" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setDrawerOpen(false);
        }}>
          <section
            aria-labelledby="region-sensitivity-heading"
            aria-modal="true"
            className="h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-2xl sm:p-7"
            role="dialog"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-brand-700">{region.name}</p>
                <h2 id="region-sensitivity-heading" className="mt-1 text-xl font-semibold text-slate-950">{t("ml.regionSensitivity")}</h2>
                <p className="mt-2 text-sm text-brand-900">{t("ml.previewOnly")}</p>
              </div>
              <button
                aria-label={t("ml.closeDrawer")}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-stone-200 text-xl text-slate-700 hover:bg-stone-50"
                onClick={() => setDrawerOpen(false)}
                type="button"
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
            <label className="mt-7 block text-sm font-semibold text-slate-800" htmlFor="region-sensitivity">
              {t("ml.thresholdLabel", { value: (threshold ?? thresholdRange.default).toFixed(2) })}
            </label>
            <input
              id="region-sensitivity"
              aria-label={t("ml.thresholdLabel", { value: (threshold ?? thresholdRange.default).toFixed(2) })}
              className="mt-3 w-full accent-brand-700"
              disabled={!mlStatus.ready}
              max={thresholdRange.maximum}
              min={thresholdRange.minimum}
              onChange={(event) => setThreshold(Number(event.target.value))}
              step={Math.max((thresholdRange.maximum - thresholdRange.minimum) / 100, Number.EPSILON)}
              type="range"
              value={threshold ?? thresholdRange.default}
            />
            <div className="mt-1 flex justify-between text-xs text-slate-600" aria-hidden="true">
              <span>{thresholdRange.minimum}</span><span>{thresholdRange.maximum}</span>
            </div>
            <button
              className="mt-3 text-sm font-semibold text-brand-800 underline decoration-brand-400 underline-offset-2"
              onClick={() => setThreshold(thresholdRange.default)}
              type="button"
            >
              {t("ml.reset")}
            </button>
            <div className="mt-8 space-y-4">
              <CountPanel title={t("ml.saved")} counts={counts} loading={summaryQuery.isLoading} />
              <CountPanel
                title={t("ml.withTheseSettings")}
                counts={regionPreviewQuery.data?.counts_by_risk}
                loading={regionPreviewQuery.isLoading}
                error={regionPreviewQuery.isError}
              />
              {regionPreviewQuery.data && (
                <p className="text-xs text-slate-600">
                  {t("ml.previewFieldCount", {
                    scored: regionPreviewQuery.data.scored_fields,
                    total: regionPreviewQuery.data.total_fields
                  })}
                </p>
              )}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function CountPanel({
  title,
  counts,
  loading,
  error = false
}: {
  title: string;
  counts: { normal: number; watch: number; alert: number; cannot_assess: number } | undefined;
  loading: boolean;
  error?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded-2xl border border-stone-200 p-4" aria-label={title}>
      <h3 className="mb-3 text-sm font-semibold text-slate-800">{title}</h3>
      {loading && <p role="status" className="text-sm text-slate-600">{t("common.loading")}</p>}
      {error && <p role="alert" className="text-sm text-amber-900">{t("ml.previewUnavailable")}</p>}
      {!loading && !error && counts && (
        <ul className="grid grid-cols-2 gap-2">
          {(["alert", "watch", "normal", "cannot_assess"] as const).map((risk) => (
            <li className="flex items-center justify-between gap-2 rounded-lg bg-stone-50 px-3 py-2 text-sm" key={risk}>
              <RiskBadge risk={risk} />
              <span className="font-semibold text-slate-900">{counts[risk]}</span>
            </li>
          ))}
        </ul>
      )}
      {!loading && !error && !counts && <p className="text-sm text-slate-600">{t("common.notAvailable")}</p>}
    </section>
  );
}

function MapSkeleton() {
  const { t } = useTranslation();
  return <div aria-label={t("common.loading")} className="h-[min(62vh,560px)] min-h-[340px] animate-pulse rounded-3xl border border-stone-200 bg-stone-100" role="status" />;
}

function PageMessage({ children, role = "status" }: { children: ReactNode; role?: "status" | "alert" }) {
  return <div className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-slate-600" role={role}>{children}</div>;
}
