import type { ModelInfo, ThresholdRange } from "../types/api";

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

export function getThresholdRange(info: ModelInfo | undefined): ThresholdRange | null {
  if (!info) return null;
  const output = record(info.output_specification);
  const candidates = [
    info.decision_threshold,
    info.risk_mapping,
    output?.decision_threshold,
    output?.risk_mapping
  ];
  for (const item of candidates) {
    const candidate = record(item);
    if (!candidate) continue;
    const nested = record(candidate.decision_threshold) ?? candidate;
    const minimum = nested.minimum;
    const maximum = nested.maximum;
    const defaultValue = nested.default;
    if (
      typeof minimum === "number" &&
      Number.isFinite(minimum) &&
      typeof maximum === "number" &&
      Number.isFinite(maximum) &&
      typeof defaultValue === "number" &&
      Number.isFinite(defaultValue) &&
      minimum >= 0 &&
      maximum <= 1 &&
      minimum < maximum &&
      minimum <= defaultValue &&
      defaultValue <= maximum
    ) {
      return { minimum, maximum, default: defaultValue };
    }
  }
  return null;
}

export function displayMetadata(value: unknown): string | null {
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    const entries = value.map(displayMetadata).filter((entry): entry is string => Boolean(entry));
    return entries.length ? entries.join(", ") : null;
  }
  const item = record(value);
  if (!item) return null;
  const entries = Object.entries(item).map(([key, child]) => {
    const formatted = displayMetadata(child);
    return formatted ? `${key}: ${formatted}` : null;
  }).filter((entry): entry is string => Boolean(entry));
  return entries.length ? entries.join("; ") : null;
}
