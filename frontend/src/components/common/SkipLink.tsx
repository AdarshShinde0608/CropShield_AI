import { useTranslation } from "react-i18next";

export default function SkipLink() {
  const { t } = useTranslation();
  return (
    <a
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[10000] focus:rounded-lg focus:bg-white focus:px-4 focus:py-3 focus:font-bold focus:text-brand-900 focus:shadow-lg"
      href="#main-content"
    >
      {t("common.skipToMain")}
    </a>
  );
}
