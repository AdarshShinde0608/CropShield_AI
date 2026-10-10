import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../auth/AuthContext";
import type { Language } from "../../types/api";

const languages: Array<{ code: Language; labelKey: string }> = [
  { code: "en", labelKey: "common.english" },
  { code: "mr", labelKey: "common.marathi" },
  { code: "hi", labelKey: "common.hindi" }
];

interface LanguageSwitcherProps {
  compact?: boolean;
}

export default function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation();
  const { changeLanguage } = useAuth();
  const [updateError, setUpdateError] = useState(false);

  const selectLanguage = async (value: string) => {
    if (value !== "en" && value !== "mr" && value !== "hi") return;
    setUpdateError(false);
    try {
      await changeLanguage(value);
    } catch {
      setUpdateError(true);
    }
  };

  return (
    <label className={compact ? "sr-only" : "flex items-center gap-3 text-xs font-semibold text-slate-600"}>
      {!compact && <span>{t("common.language")}</span>}
      <span className="inline-flex flex-col">
        <select
          aria-label={t("common.language")}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          value={i18n.resolvedLanguage ?? "en"}
          onChange={(event) => void selectLanguage(event.target.value)}
        >
          {languages.map(({ code, labelKey }) => (
            <option value={code} key={code}>{t(labelKey)}</option>
          ))}
        </select>
        {updateError && <span className="absolute mt-10 text-xs text-red-700" role="alert">{t("common.languageSaveError")}</span>}
      </span>
    </label>
  );
}
