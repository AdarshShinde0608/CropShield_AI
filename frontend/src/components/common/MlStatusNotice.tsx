import { useTranslation } from "react-i18next";
import { useMlStatus } from "../../hooks/useMlStatus";

export default function MlStatusNotice() {
  const { t } = useTranslation();
  const { waking, unavailable, secondsRemaining } = useMlStatus();

  if (waking) {
    const progress = Math.min(100, Math.round(((60 - secondsRemaining) / 60) * 100));
    return (
      <div className="mx-auto mt-4 max-w-[1600px] px-4 sm:px-6 lg:px-8" role="status" aria-live="polite">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950">
          <p className="text-sm font-semibold">{t("ml.waking", { seconds: secondsRemaining })}</p>
          <div
            className="mt-3 h-2 overflow-hidden rounded-full bg-amber-100"
            role="progressbar"
            aria-label={t("ml.wakingProgress")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
          >
            <div className="h-full rounded-full bg-amber-500 transition-[width]" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>
    );
  }

  if (unavailable) {
    return (
      <div className="mx-auto mt-4 max-w-[1600px] px-4 sm:px-6 lg:px-8">
        <p className="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950" role="status">
          {t("ml.unavailable")}
        </p>
      </div>
    );
  }

  return null;
}

