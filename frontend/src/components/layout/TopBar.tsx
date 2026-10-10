import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listRegions, getRegionSummary } from "../../api/regions";
import { useAuth } from "../../auth/AuthContext";
import LanguageSwitcher from "../common/LanguageSwitcher";
import SyntheticBanner from "../common/SyntheticBanner";

export default function TopBar() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const regionsQuery = useQuery({ queryKey: ["regions"], queryFn: listRegions });
  const region = regionsQuery.data?.[0];
  const summaryQuery = useQuery({
    queryKey: ["region-summary", region?.region_id],
    queryFn: () => getRegionSummary(region!.region_id),
    enabled: Boolean(region?.region_id)
  });
  const isSynthetic = Boolean(region?.is_synthetic || summaryQuery.data?.is_synthetic);
  return (
    <header className="sticky top-0 z-20 border-b border-stone-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex min-h-[76px] max-w-[1600px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="min-w-0">
          <p className="flex items-center gap-2 truncate text-sm font-bold text-emerald-900">
            <span aria-hidden="true" className="text-base">⌖</span>
            {region?.name ?? t("topbar.region")}
          </p>
          <p className="mt-0.5 pl-6 text-xs text-slate-500">
            {t("topbar.currentSeason")}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {summaryQuery.data?.latest_observation_date && (
            <span className="hidden items-center gap-2 rounded-lg border border-stone-200 px-3 py-2 text-xs text-slate-600 sm:inline-flex">
              <span aria-hidden="true">▦</span>
              {t("topbar.latestObservation")}: <strong className="text-slate-900">{summaryQuery.data.latest_observation_date}</strong>
            </span>
          )}
          <LanguageSwitcher />
          <details className="relative">
            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-stone-50">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-900" aria-hidden="true">
                {user?.name.slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden max-w-32 truncate sm:inline">{user?.name}</span>
              <span aria-hidden="true">⌄</span>
            </summary>
            <div className="absolute right-0 top-full mt-2 w-52 rounded-xl border border-stone-200 bg-white p-2 shadow-lg">
              <p className="truncate px-3 py-2 text-xs text-slate-500">{user?.email}</p>
              <button className="w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-700 hover:bg-stone-50" onClick={logout} type="button">
                {t("nav.logout")}
              </button>
            </div>
          </details>
        </div>
      </div>
      {isSynthetic && <SyntheticBanner />}
    </header>
  );
}
