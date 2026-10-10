import { useTranslation } from "react-i18next";
import type { ConfidenceLabel } from "../../types/api";

const confidenceColors: Record<ConfidenceLabel, string> = {
  high: "bg-green-700",
  medium: "bg-amber-600",
  low: "bg-slate-500"
};

export default function ConfidenceMeter({
  value,
  label
}: {
  value: number;
  label: ConfidenceLabel;
}) {
  const { t } = useTranslation();
  const percent = Math.round(value * 100);
  return (
    <div aria-label={t("field.confidencePercent", { percent, label: t(`confidence.${label}`) })} className="min-w-36">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold text-slate-600">{t("field.confidence")}</span>
        <span className="font-bold text-slate-900">{t(`confidence.${label}`)} · {percent}%</span>
      </div>
      <div aria-hidden="true" className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${confidenceColors[label]}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
