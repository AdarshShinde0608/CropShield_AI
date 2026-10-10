import { useTranslation } from "react-i18next";
import { riskStyles } from "../../lib/riskStyles";
import type { Risk } from "../../types/api";

const risks: Risk[] = ["normal", "watch", "alert", "cannot_assess"];

export default function MapLegend() {
  const { t } = useTranslation();
  return (
    <ul aria-label={t("map.legend")} className="flex flex-wrap gap-x-4 gap-y-2">
      {risks.map((risk) => (
        <li className="flex items-center gap-2 text-xs font-semibold text-slate-700" key={risk}>
          <span
            aria-hidden="true"
            className={`grid h-5 w-5 place-items-center rounded-md border text-[10px] ${risk === "normal" ? "border-green-700 bg-green-100 text-green-900" : risk === "watch" ? "border-amber-700 border-dashed bg-amber-100 text-amber-950" : risk === "alert" ? "border-red-700 border-dotted bg-red-100 text-red-950" : "border-slate-600 border-dashed bg-[repeating-linear-gradient(135deg,#e2e8f0,#e2e8f0_3px,#ffffff_3px,#ffffff_6px)] text-slate-900"}`}
          >
            {riskStyles[risk].marker}
          </span>
          {t(riskStyles[risk].labelKey)}
        </li>
      ))}
    </ul>
  );
}
