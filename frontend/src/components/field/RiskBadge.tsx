import { useTranslation } from "react-i18next";
import type { Risk } from "../../types/api";

const riskAppearance: Record<Risk, { dot: string; surface: string; icon: string }> = {
  normal: { dot: "bg-risk-normal", surface: "bg-green-50 text-green-900 ring-green-200", icon: "✓" },
  watch: { dot: "bg-risk-watch", surface: "bg-amber-50 text-amber-950 ring-amber-200", icon: "!" },
  alert: { dot: "bg-risk-alert", surface: "bg-red-50 text-red-950 ring-red-200", icon: "!" },
  cannot_assess: { dot: "bg-risk-cannot_assess", surface: "bg-slate-100 text-slate-800 ring-slate-200", icon: "–" }
};

export default function RiskBadge({ risk }: { risk: Risk }) {
  const { t } = useTranslation();
  const appearance = riskAppearance[risk];
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold ring-1 ring-inset ${appearance.surface}`}>
      <span aria-hidden="true" className={`grid h-4 w-4 place-items-center rounded-full text-[10px] text-white ${appearance.dot}`}>
        {appearance.icon}
      </span>
      {t(`risk.${risk}`)}
    </span>
  );
}
