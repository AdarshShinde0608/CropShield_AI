import { useTranslation } from "react-i18next";
import type { FieldResult, TimeseriesPoint } from "../../types/api";

function countTrailingBelowBaseline(points: TimeseriesPoint[]): number {
  let count = 0;
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    if (point.ndvi == null || point.baseline_median == null || point.ndvi >= point.baseline_median) break;
    count += 1;
  }
  return count;
}

export default function EvidenceList({ field, points }: { field: FieldResult; points: TimeseriesPoint[] }) {
  const { t } = useTranslation();
  const items = [
    [t("field.zScore"), field.z_score == null ? "—" : field.z_score.toFixed(2)],
    [t("field.pctBelowNormal"), field.pct_below_normal == null ? "—" : `${field.pct_below_normal.toFixed(1)}%`],
    [t("field.consecutiveLow"), String(countTrailingBelowBaseline(points))],
    [t("field.validObservations"), String(field.n_valid_obs)],
    [t("field.baselineYears"), String(field.baseline_years)],
    [t("field.rainContext"), field.rain_context ? t(`rainContext.${field.rain_context}`) : "—"]
  ];

  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div className="rounded-xl bg-stone-50 p-4" key={label}>
          <dt className="text-xs font-semibold text-slate-500">{label}</dt>
          <dd className="mt-1 text-sm font-bold text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
