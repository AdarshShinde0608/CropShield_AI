import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTranslation } from "react-i18next";
import type { RainPoint, TimeseriesPoint } from "../../types/api";

export default function RainfallBars({
  rainfall,
  points
}: {
  rainfall: RainPoint[];
  points: TimeseriesPoint[];
}) {
  const { t } = useTranslation();
  const values = new Map(rainfall.map((point) => [point.date, point.rain_mm]));
  const data = points.map((point) => ({ date: point.date, rain_mm: values.get(point.date) ?? null }));
  return (
    <div className="h-32 w-full sm:h-40" role="img" aria-label={t("chart.rainDescription")}>
      {data.length ? (
        <ResponsiveContainer height="100%" width="100%">
          <BarChart data={data} margin={{ top: 4, right: 14, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#e8ece7" strokeDasharray="3 4" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} minTickGap={32} />
            <YAxis tick={{ fontSize: 10 }} tickLine={false} width={36} />
            <Tooltip formatter={(value) => [`${value ?? "—"} mm`, t("chart.rainfall")]} />
            <Bar dataKey="rain_mm" fill="#70a9c6" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="py-8 text-sm text-slate-500">{t("chart.noRainfall")}</p>
      )}
    </div>
  );
}
