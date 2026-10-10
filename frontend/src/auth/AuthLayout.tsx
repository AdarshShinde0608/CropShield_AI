import type { PropsWithChildren } from "react";
import { useTranslation } from "react-i18next";
import LanguageSwitcher from "../components/common/LanguageSwitcher";
import SkipLink from "../components/common/SkipLink";

export default function AuthLayout({ children }: PropsWithChildren) {
  const { t } = useTranslation();
  return (
    <main className="min-h-screen bg-[#f5f7f2]" id="main-content" tabIndex={-1}>
      <SkipLink />
      <div className="mx-auto grid min-h-screen max-w-[1440px] lg:grid-cols-[1.04fr_0.96fr]">
        <section className="relative hidden overflow-hidden bg-brand-800 px-12 py-10 text-white lg:flex lg:flex-col xl:px-20">
          <div className="absolute inset-0 opacity-25" aria-hidden="true">
            <div className="absolute -left-40 -top-40 h-[560px] w-[560px] rounded-full border border-white/30" />
            <div className="absolute -left-24 -top-24 h-[400px] w-[400px] rounded-full border border-white/30" />
            <div className="absolute -left-8 -top-8 h-[240px] w-[240px] rounded-full border border-white/30" />
            <div className="absolute bottom-0 left-0 h-[42%] w-full bg-gradient-to-t from-black/20 to-transparent" />
          </div>
          <div className="relative flex items-center gap-3">
            <BrandMark />
            <span className="text-xl font-bold tracking-tight">{t("brand.name")}</span>
          </div>
          <div className="relative my-auto max-w-xl py-20">
            <p className="mb-5 text-xs font-bold uppercase tracking-[0.22em] text-brand-200">{t("auth.loginEyebrow")}</p>
            <h1 className="max-w-lg text-5xl font-semibold leading-[1.12] tracking-tight xl:text-6xl">{t("auth.accountTitle")}</h1>
            <p className="mt-6 max-w-lg text-lg leading-8 text-brand-100">{t("auth.accountBody")}</p>
            <ul className="mt-10 space-y-4">
              {(["point1", "point2", "point3"] as const).map((key) => (
                <li key={key} className="flex items-center gap-3 text-sm text-white/90">
                  <span aria-hidden="true" className="grid h-6 w-6 place-items-center rounded-full bg-white/15 text-brand-100">✓</span>
                  {t(`auth.${key}`)}
                </li>
              ))}
            </ul>
          </div>
          <p className="relative text-xs text-white/70">{t("auth.footer")}</p>
        </section>
        <section className="flex min-h-screen flex-col px-5 py-6 sm:px-10 lg:px-12 xl:px-20">
          <header className="flex items-center justify-between">
            <div className="flex items-center gap-2 lg:hidden">
              <BrandMark dark />
              <span className="font-bold text-slate-900">{t("brand.name")}</span>
            </div>
            <div className="ml-auto">
              <LanguageSwitcher />
            </div>
          </header>
          <div className="mx-auto flex w-full max-w-md flex-1 items-center py-10">
            {children}
          </div>
          <p className="text-center text-xs text-slate-500 lg:hidden">{t("auth.footer")}</p>
        </section>
      </div>
    </main>
  );
}

function BrandMark({ dark = false }: { dark?: boolean }) {
  return (
    <span className={`grid h-10 w-10 place-items-center rounded-xl ${dark ? "bg-brand-100 text-brand-700" : "bg-white/15 text-white"}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" className="h-6 w-6" fill="none">
        <path d="M25.5 5.5C16 5.5 8 8.8 8 17c0 4 2.8 6.5 6.5 6.5 7.8 0 11-8.4 11-18Z" fill="currentColor" />
        <path d="M6 27c3.1-6.5 7.4-10.6 14-14" stroke={dark ? "#315b2e" : "#315b2e"} strokeWidth="2.2" strokeLinecap="round" />
      </svg>
    </span>
  );
}
