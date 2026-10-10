import api from "./client";
import type { FieldResult, TimeseriesResponse } from "../types/api";

export async function getField(fieldId: string): Promise<FieldResult> {
  const response = await api.get<FieldResult>(`/fields/${encodeURIComponent(fieldId)}`);
  return response.data;
}

export async function getFieldTimeseries(fieldId: string): Promise<TimeseriesResponse> {
  const response = await api.get<TimeseriesResponse>(
    `/fields/${encodeURIComponent(fieldId)}/timeseries`
  );
  return response.data;
}