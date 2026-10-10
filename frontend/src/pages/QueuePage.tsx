import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { getRegionQueue, getRegionSummary, listRegions } from "../api/regions";
import RiskBadge from "../components/field/RiskBadge";
import type { QueueItem, Risk } from "../types/api";

const riskFilters: Array<Risk | "all"> = ["all", "alert", "watch", "normal", "cannot_assess"];

export default function QueuePage() {
  const { t } = useTranslation();
  const [risk, setRisk] = useState<Risk | "all">("all");
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: listRegions });
  const region = regionsQuery.data?.[0];
  const summaryQuery = useQuery({
    queryKey: ["region-summary", region?.region_id],
    queryFn: () => getRegionSummary(region!.region_id),
    enabled: Boolean(region?.region_id)
  });
  const queueQuery = useQuery({
    queryKey: ["region-queue", region?.region_id, risk],
    queryFn: () => getRegionQueue(region!.region_id, { risk: risk === "all" ? undefined : risk }),
    enabled: Boolean(region?.region_id)
  });

  if (regionsQuery.isLoading) return <main id="main-content" tabIndex={-1}><StateMessage>{t("common.loading")}</StateMessage></main>;
  if (regionsQuery.isError) return <main id="main-content" tabIndex={-1}><StateMessage role="alert">{t("common.error")}</StateMessage></main>;
  if (!region) return <main id="main-content" tabIndex={-1}><StateMessage>{t("dashboard.noRegions")}</StateMessage></main>;
  if (queueQuery.isLoading || summaryQuery.isLoading) return <main id="main-content" tabIndex={-1}><StateMessage>{t("common.loading")}</StateMessage></main>;
  if (queueQuery.isError || summaryQuery.isError) return <main id="main-content" tabIndex={-1}><StateMessage role="alert">{t("common.error")}</StateMessage></main>;
  const items = queueQuery.data ?? [];

  return (
    <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 pb-24 sm:px-6 sm:py-9" id="main-content" tabIndex={-1}>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{t("queue.title")}</h1>
          <p className="mt-2 text-sm text-slate-600">{t("queue.subtitle")}</p>
        </div>
        <button className="rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 hover:bg-stone-50 disabled:opacity-50" disabled={!items.length} onClick={() => exportCsv(items, t)} type="button">
          {t("queue.exportCsv")}
        </button>
      </header>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-slate-700">{t("queue.filterRisk")}</span>
        <div aria-label={t("queue.filterRisk")} className="flex flex-wrap gap-2" role="group">
          {riskFilters.map((filter) => (
            <button
              aria-pressed={risk === filter}
              className={`rounded-full border px-4 py-2 text-xs font-semibold transition ${risk === filter ? "border-brand-800 bg-brand-800 text-white" : "border-stone-200 bg-white text-slate-700 hover:border-brand-300 hover:bg-brand-50"}`}
              key={filter}
              onClick={() => setRisk(filter)}
              type="button"
            >
              {filter === "all" ? t("queue.allRisks") : t(`risk.${filter}`)}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-500">{t("queue.sortPriority")}</span>
      </div>

      {items.length === 0 && <StateMessage>{t("queue.empty")}</StateMessage>}
      {items.length > 0 && (
        <>
          <div className="hidden overflow-hidden rounded-2xl border border-stone-200 bg-white md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-stone-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">{t("queue.rank")}</th>
                  <th className="px-5 py-3">{t("queue.field")}</th>
                  <th className="px-5 py-3">{t("field.risk")}</th>
                  <th className="px-5 py-3">{t("field.confidence")}</th>
                  <th className="px-5 py-3">{t("field.latest")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {items.map((item) => (
                  <QueueTableRow item={item} key={item.field_id} />
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-3 md:hidden">
            {items.map((item) => (
              <li key={item.field_id}>
                <Link className="block rounded-2xl border border-stone-200 bg-white p-4 shadow-sm hover:border-brand-200" to={`/fields/${encodeURIComponent(item.field_id)}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-xs font-bold text-brand-900">{item.priority_rank ?? "—"}</span>
                      <span className="truncate text-sm font-semibold text-slate-900">{item.name ?? item.field_id}</span>
                    </span>
                    <RiskBadge risk={item.risk} />
                  </div>
                  <div className="mt-3 flex justify-between gap-3 text-xs text-slate-600">
                    <span>{t("field.confidence")}: {t(`confidence.${item.confidence_label}`)}</span>
                    <span>{item.latest_obs_date ?? "—"}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

function QueueTableRow({ item }: { item: QueueItem }) {
  const { t } = useTranslation();
  return (
    <tr className="hover:bg-stone-50">
      <td className="px-5 py-4 font-bold text-slate-800">{item.priority_rank ?? "—"}</td>
      <td className="px-5 py-4">
        <Link className="font-semibold text-brand-800 hover:underline" to={`/fields/${encodeURIComponent(item.field_id)}`}>
          {item.name ?? item.field_id}
        </Link>
      </td>
      <td className="px-5 py-4"><RiskBadge risk={item.risk} /></td>
      <td className="px-5 py-4">{t(`confidence.${item.confidence_label}`)}</td>
      <td className="px-5 py-4 text-slate-600">{item.latest_obs_date ?? "—"}</td>
    </tr>
  );
}

function exportCsv(items: QueueItem[], t: (key: string) => string) {
  const header = [t("queue.rank"), t("queue.field"), t("field.risk"), t("field.confidence"), t("field.latest")];
  const rows = items.map((item) => [
    item.priority_rank ?? "",
    item.name ?? item.field_id,
    t(`risk.${item.risk}`),
    t(`confidence.${item.confidence_label}`),
    item.latest_obs_date ?? ""
  ]);
  const csv = [header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\r\n");
  const file = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(file);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "cropshield-inspection-queue.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function escapeCsv(value: string | number): string {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function StateMessage({ children, role = "status" }: { children: ReactNode; role?: "status" | "alert" }) {
  return <div className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-slate-600" role={role}>{children}</div>;
}
