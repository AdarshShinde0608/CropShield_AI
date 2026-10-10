import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { previewFieldScore } from "../../api/ml";
import type { Risk, ThresholdRange } from "../../types/api";
import RiskBadge from "./RiskBadge";

export default function SensitivityPreview({
  fieldId,
  savedRisk,
  range
}: {
  fieldId: string;
  savedRisk: Risk;
  range: ThresholdRange;
}) {
  const { t } = useTranslation();
  const [threshold, setThreshold] = useState(range.default);
  const [debouncedThreshold, setDebouncedThreshold] = useState(range.default);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedThreshold(threshold), 450);
    return () => window.clearTimeout(timer);
  }, [threshold]);

  const previewQuery = useQuery({
    queryKey: ["field-score-preview", fieldId, debouncedThreshold],
    queryFn: () => previewFieldScore(fieldId, debouncedThreshold),
    enabled: Boolean(fieldId),
    retry: false
  });

  return (
    <section className="rounded-2xl border border-brand-200 bg-brand-50/70 p-5 shadow-sm" aria-labelledby="sensitivity-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="sensitivity-heading" className="font-semibold text-slate-950">{t("ml.sensitivity")}</h2>
          <p className="mt-1 text-xs font-semibold text-brand-900">{t("ml.previewOnly")}</p>
        </div>
        <button
          className="text-sm font-semibold text-brand-800 underline decoration-brand-400 underline-offset-2 hover:text-brand-950"
          onClick={() => setThreshold(range.default)}
          type="button"
        >
          {t("ml.reset")}
        </button>
      </div>
      <label className="mt-5 block text-sm font-medium text-slate-800" htmlFor="field-sensitivity">
        {t("ml.thresholdLabel", { value: threshold.toFixed(2) })}
      </label>
      <input
        id="field-sensitivity"
        aria-label={t("ml.thresholdLabel", { value: threshold.toFixed(2) })}
        className="mt-3 w-full accent-brand-700"
        max={range.maximum}
        min={range.minimum}
        onChange={(event) => setThreshold(Number(event.target.value))}
        step={Math.max((range.maximum - range.minimum) / 100, Number.EPSILON)}
        type="range"
        value={threshold}
      />
      <div className="mt-1 flex justify-between text-xs text-slate-600" aria-hidden="true">
        <span>{range.minimum}</span><span>{range.maximum}</span>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-white bg-white p-3">
          <p className="mb-2 text-xs font-semibold text-slate-600">{t("ml.saved")}</p>
          <RiskBadge risk={savedRisk} />
        </div>
        <div className="rounded-xl border border-white bg-white p-3" aria-live="polite">
          <p className="mb-2 text-xs font-semibold text-slate-600">{t("ml.withTheseSettings")}</p>
          {previewQuery.isLoading && <p className="text-sm text-slate-600" role="status">{t("common.loading")}</p>}
          {previewQuery.isError && <p className="text-sm text-amber-900" role="alert">{t("ml.previewUnavailable")}</p>}
          {previewQuery.data && <RiskBadge risk={previewQuery.data.risk} />}
        </div>
      </div>
    </section>
  );
}

