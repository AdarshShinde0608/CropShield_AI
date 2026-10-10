import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

const tabs = [
  { to: "/", key: "nav.dashboard", icon: "⌂", end: true },
  { to: "/queue", key: "nav.queue", icon: "☷", end: false },
  { to: "/methodology", key: "nav.methodology", icon: "ⓘ", end: false }
];

export default function MobileTabBar() {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("nav.primary")} className="fixed inset-x-0 bottom-0 z-[1100] grid grid-cols-3 border-t border-stone-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      {tabs.map((tab) => (
        <NavLink
          aria-label={t(tab.key)}
          className={({ isActive }) => `flex min-h-16 flex-col items-center justify-center gap-1 text-[11px] font-semibold ${isActive ? "text-brand-800" : "text-slate-500"}`}
          end={tab.end}
          key={tab.to}
          to={tab.to}
        >
          <span aria-hidden="true" className="text-xl leading-none">{tab.icon}</span>
          {t(tab.key)}
        </NavLink>
      ))}
    </nav>
  );
}
