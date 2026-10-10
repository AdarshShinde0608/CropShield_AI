import { Link, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

const navigation = [
  { to: "/", key: "nav.dashboard", icon: "⌂", end: true },
  { to: "/queue", key: "nav.queue", icon: "☷", end: false },
  { to: "/methodology", key: "nav.methodology", icon: "ⓘ", end: false }
];

export default function Sidebar() {
  const { t } = useTranslation();
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 flex-col bg-[#0d402b] px-4 py-6 text-white lg:flex">
      <Link aria-label={t("brand.name")} className="mb-9 flex items-center gap-3 px-3 font-bold tracking-tight text-white" to="/">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#168447] text-xl text-white" aria-hidden="true">♧</span>
        <span className="text-lg">{t("brand.name")}</span>
      </Link>
      <nav aria-label={t("nav.primary")} className="space-y-2">
        {navigation.map((item) => (
          <NavLink
            className={({ isActive }) => `flex items-center gap-3 rounded-xl border-l-[3px] px-3 py-3 text-sm font-semibold transition ${isActive ? "border-[#79d69b] bg-[#286746] text-white" : "border-transparent text-emerald-50/85 hover:bg-white/10 hover:text-white"}`}
            end={item.end}
            key={item.to}
            to={item.to}
          >
            <span aria-hidden="true" className="grid h-6 w-6 place-items-center text-lg">{item.icon}</span>
            {t(item.key)}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto border-t border-white/20 px-3 pt-5">
        <p className="text-xs font-bold uppercase tracking-wider text-emerald-100">{t("brand.tagline")}</p>
        <p className="mt-2 text-xs leading-5 text-emerald-50/80">{t("sidebar.disclaimer")}</p>
      </div>
    </aside>
  );
}
