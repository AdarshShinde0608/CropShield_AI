import { useTranslation } from "react-i18next";
import NdviChart from "./NdviChart";
import RiskBadge from "./RiskBadge";
import type { FieldResult, ModelEvidencePoint, TimeseriesPoint } from "../../types/api";

export default function ModelResultCard({
  field,
  fallbackPoints
}: {
  field: FieldResult;
  fallbackPoints: TimeseriesPoint[];
}) {
  const { t } = useTranslation();
  const hasResult = Boolean(field.model_version);
  const evidencePoints = modelEvidencePoints(field.evidence?.observations);
  const points = evidencePoints.length ? evidencePoints : fallbackPoints;
  const factors = factorEntries(field.top_factors);

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6" aria-labelledby="model-result-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="model-result-heading" className="font-semibold text-slate-950">{t("ml.modelResult")}</h2>
          {field.model_version && (
            <span className="mt-2 inline-flex rounded-full bg-brand-50 px-3 py-1 text-xs font-bold text-brand-900">
              {t("ml.version", { version: field.model_version })}
            </span>
          )}
        </div>
        {hasResult && <RiskBadge risk={field.risk} />}
      </div>

      {!hasResult && (
        <p className="mt-4 text-sm leading-6 text-slate-600" role="status">{t("ml.noSavedModelResult")}</p>
      )}

      {hasResult && (
        <>
          {field.risk === "alert" && (
            <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-950">
              {t("ml.inspectMessage")}
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {field.model_score != null && (
              <p className="text-sm text-slate-700">
                <span className="font-semibold">{t("ml.modelScore")}</span>{" "}
                {field.model_score.toFixed(3)}
              </p>
            )}
          </div>
          {factors.length > 0 && (
            <div className="mt-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-800">{t("ml.mainFactors")}</h3>
              <ul className="space-y-3">
                {factors.map(({ label, weight }) => (
                  <li key={label}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-xs text-slate-700">
                      <span>{label}</span>
                      {weight != null && <span>{weight.toFixed(2)}</span>}
                    </div>
                    <div className="h-2 rounded-full bg-stone-100" aria-hidden="true">
                      <div className="h-2 rounded-full bg-brand-700" style={{ width: `${factorWidth(weight)}%` }} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-5 border-t border-stone-100 pt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold text-slate-800">{t("ml.baselineEvidence")}</h3>
              <p className="text-xs text-slate-600">
                {t("ml.evidenceOnset")}: {field.drop_start ?? t("common.notAvailable")}
              </p>
            </div>
            {points.length ? (
              <>
                <NdviChart dropStart={field.drop_start} points={points} />
                <p className="mt-2 text-xs text-slate-500">{t("ml.evidenceChartDescription")}</p>
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-500" role="status">{t("ml.noEvidenceChart")}</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function modelEvidencePoints(evidence: ModelEvidencePoint[] | undefined): TimeseriesPoint[] {
  if (!evidence) return [];
  return evidence.flatMap((point) => {
    if (!point.date) return [];
    return [{
      date: point.date,
      ndvi: point.ndvi ?? null,
      baseline_median: point.baseline_median ?? null,
      band_low: point.baseline_lower ?? null,
      band_high: point.baseline_upper ?? null,
      z: point.deviation_from_median ?? null,
      low_quality: point.is_clear === false,
      is_interpolated: false
    }];
  });
}

function factorEntries(factors: FieldResult["top_factors"]): Array<{ label: string; weight: number | null }> {
  if (Array.isArray(factors)) return factors.map((label) => ({ label, weight: null }));
  if (factors) return Object.entries(factors).map(([label, weight]) => ({ label, weight }));
  return [];
}

function factorWidth(weight: number | null): number {
  if (weight == null) return 72;
  return Math.max(6, Math.min(100, Math.round(Math.abs(weight) * 100)));
}
