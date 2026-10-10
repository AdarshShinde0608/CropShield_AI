import api from "./client";
import type {
  MlStatus,
  ModelInfo,
  RegionScorePreview,
  ScorePreview
} from "../types/api";

export async function getMlStatus(): Promise<MlStatus> {
  const response = await api.get<MlStatus>("/ml/status");
  return response.data;
}

export async function warmupMlService(): Promise<void> {
  await api.post("/ml/warmup");
}

export async function getModelInfo(): Promise<ModelInfo> {
  const response = await api.get<ModelInfo>("/model-info");
  return response.data;
}

export async function previewFieldScore(
  fieldId: string,
  decisionThreshold: number
): Promise<ScorePreview> {
  const response = await api.post<ScorePreview>(
    `/fields/${encodeURIComponent(fieldId)}/score-preview`,
    { decision_threshold: decisionThreshold }
  );
  return response.data;
}

export async function previewRegionScores(
  regionId: string,
  decisionThreshold: number
): Promise<RegionScorePreview> {
  const response = await api.post<RegionScorePreview>(
    `/regions/${encodeURIComponent(regionId)}/score-preview`,
    { decision_threshold: decisionThreshold }
  );
  return response.data;
}

