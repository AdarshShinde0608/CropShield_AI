import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { TimeseriesPoint } from "../../types/api";
import { useTranslation } from "react-i18next";

interface NdviChartProps {
  points: TimeseriesPoint[];
  dropStart: string | null;
}

export default function NdviChart({ points, dropStart }: NdviChartProps) {
  const { t } = useTranslation();
  const chartData = points.map((point) => ({
    ...point,
    bandUpper: point.band_high,
    bandLower: point.band_low
  }));

  if (!points.length) return <p className="py-8 text-sm text-slate-500">{t("common.empty")}</p>;

  return (
    <div className="h-72 w-full sm:h-80" role="img" aria-label={t("chart.ndviDescription")}>
      <ResponsiveContainer height="100%" width="100%">
        <ComposedChart data={chartData} margin={{ top: 12, right: 14, bottom: 4, left: 0 }}>
          <CartesianGrid stroke="#e8ece7" strokeDasharray="3 4" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} minTickGap={32} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickLine={false} width={36} />
          <Tooltip
            content={({ active, payload, label }) => {
              const point = payload?.[0]?.payload as TimeseriesPoint | undefined;
              if (!active || !point) return null;
              return (
                <div className="rounded-xl border border-stone-200 bg-white p-3 text-xs shadow-lg">
                  <p className="mb-2 font-bold text-slate-900">{label}</p>
                  <p>{t("chart.observed")}: {point.ndvi?.toFixed(3) ?? "—"}</p>
                  <p>{t("chart.baseline")}: {point.baseline_median?.toFixed(3) ?? "—"}</p>
                  <p>{t("chart.zScore")}: {point.z?.toFixed(2) ?? "—"}</p>
                  {point.low_quality && <p className="mt-1 text-amber-800">{t("chart.lowQuality")}</p>}
                  {point.is_interpolated && <p className="mt-1 text-slate-600">{t("chart.interpolated")}</p>}
                </div>
              );
            }}
          />
          <Area dataKey="bandUpper" fill="#d9eadb" fillOpacity={0.82} stroke="none" type="monotone" isAnimationActive={false} />
          <Area dataKey="bandLower" fill="#ffffff" fillOpacity={1} stroke="none" type="monotone" isAnimationActive={false} />
          <Line
            dataKey="baseline_median"
            name={t("chart.baseline")}
            stroke="#6d8d67"
            strokeDasharray="5 4"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          {dropStart && (
            <ReferenceLine
              x={dropStart}
              stroke="#a62c28"
              strokeDasharray="4 4"
              label={{ value: t("field.dropStart"), position: "insideTopRight", fill: "#8e2923", fontSize: 10 }}
            />
          )}
          <Line
            dataKey="ndvi"
            name={t("chart.observed")}
            stroke="#236744"
            strokeWidth={2.5}
            connectNulls={false}
            isAnimationActive={false}
            dot={(props) => {
              const { cx, cy, payload } = props;
              if (cx == null || cy == null || payload.ndvi == null) return <g />;
              const fill = payload.low_quality ? "#d97706" : payload.is_interpolated ? "#64748b" : "#236744";
              return <circle cx={cx} cy={cy} r={payload.low_quality || payload.is_interpolated ? 4.5 : 3} fill={fill} stroke="white" strokeWidth={1.5} />;
            }}
            activeDot={{ r: 5 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
