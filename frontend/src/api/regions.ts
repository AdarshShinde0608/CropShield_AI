import api from "./client";
import type { FieldCollection, MethodologyOut, QueueItem, Region, RegionSummary } from "../types/api";

export async function listRegions(): Promise<Region[]> {
  const response = await api.get<Region[]>("/regions");
  return response.data;
}

export async function getRegionSummary(regionId: string): Promise<RegionSummary> {
  const response = await api.get<RegionSummary>(
    `/regions/${encodeURIComponent(regionId)}/summary`
  );
  return response.data;
}

export async function getRegionFields(regionId: string): Promise<FieldCollection> {
  const response = await api.get<FieldCollection>(
    `/regions/${encodeURIComponent(regionId)}/fields`
  );
  return response.data;
}

export async function getRegionQueue(
  regionId: string,
  options: { risk?: string; limit?: number } = {}
): Promise<QueueItem[]> {
  const response = await api.get<QueueItem[]>(
    `/regions/${encodeURIComponent(regionId)}/queue`,
    { params: options }
  );
  return response.data;
}

export async function getMethodology(): Promise<MethodologyOut> {
  const response = await api.get<MethodologyOut>("/methodology");
  return response.data;
}