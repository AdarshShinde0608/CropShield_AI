import { useTranslation } from "react-i18next";

export default function SyntheticBanner() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3 border-t border-[#c9e0db] bg-[#edf7f5] px-4 py-2.5 text-sm text-[#1b5960] sm:px-6 lg:px-8" role="status">
      <span aria-hidden="true" className="grid h-5 w-5 shrink-0 place-items-center rounded-full border border-current font-semibold">i</span>
      <span className="font-semibold">{t("dashboard.synthetic")}</span>
    </div>
  );
}
