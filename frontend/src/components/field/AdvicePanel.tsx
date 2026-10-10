import { useTranslation } from "react-i18next";
import type { FieldResult } from "../../types/api";

export default function AdvicePanel({ field }: { field: FieldResult }) {
  const { t } = useTranslation();
  const translatedAdvice = field.advice_key
    ? t(field.advice_key, { defaultValue: field.advice ?? t("advice.fallback") })
    : field.advice ?? t("advice.fallback");
  const reason = field.rain_context === "dry_spell"
    ? t("advice.reasonDry")
    : t("advice.reasonBaseline");
  return (
    <section className="rounded-2xl border border-brand-200 bg-brand-50 p-5" aria-labelledby="field-advice-title">
      <h2 id="field-advice-title" className="font-semibold text-brand-950">{t("field.advice")}</h2>
      <p className="mt-2 text-sm font-semibold leading-6 text-brand-950">{translatedAdvice}</p>
      <p className="mt-2 text-xs leading-5 text-brand-900">{reason}</p>
      <p className="mt-4 border-t border-brand-200 pt-3 text-xs font-semibold leading-5 text-slate-800">{t("field.limitation")}</p>
    </section>
  );
}
