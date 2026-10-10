export type Language = "en" | "mr" | "hi";
export type UserRole = "officer" | "farmer";
export type Risk = "normal" | "watch" | "alert" | "cannot_assess";
export type Severity = "moderate" | "high";
export type ConfidenceLabel = "high" | "medium" | "low";
export type ActionStatus = "pending" | "done" | "needs_expert";
export type RainContext = "dry_spell" | "normal" | "not_applicable";

export interface ApiError {
  detail: string;
  code: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  language: Language;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  language?: Language;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ProfileUpdateRequest {
  name?: string;
  language?: Language;
}

export interface Region {
  region_id: string;
  name: string;
  state: string | null;
  latest_run_id: string | null;
  latest_observation_date: string | null;
  is_synthetic: boolean | null;
}

export interface RiskCounts {
  normal: number;
  watch: number;
  alert: number;
  cannot_assess: number;
}

export interface RegionSummary {
  region_id: string;
  counts_by_risk: RiskCounts;
  latest_observation_date: string | null;
  run_id: string | null;
  is_synthetic: boolean | null;
}

export interface FieldResult {
  field_id: string;
  risk: Risk;
  severity: Severity | null;
  confidence: number;
  confidence_label: ConfidenceLabel;
  z_score: number | null;
  pct_below_normal: number | null;
  drop_start: string | null;
  latest_obs_date: string | null;
  n_valid_obs: number;
  baseline_years: number;
  rain_context: RainContext | null;
  advice_key: string | null;
  advice: string | null;
  priority_score: number | null;
  priority_rank: number | null;
  if_flag: boolean | null;
  is_synthetic: boolean;
  model_version?: string | null;
  model_score?: number | null;
  top_factors?: string[] | Record<string, number> | null;
  evidence?: ModelEvidence | null;
  decision_threshold?: number | null;
}

export interface FieldProperties extends FieldResult {
  name?: string | null;
}

export interface GeoJsonPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface FieldFeature {
  type: "Feature";
  geometry: GeoJsonPolygon;
  properties: FieldProperties;
}

export interface FieldCollection {
  type: "FeatureCollection";
  features: FieldFeature[];
}

export interface QueueItem {
  field_id: string;
  name: string | null;
  risk: Risk;
  severity: Severity | null;
  confidence_label: ConfidenceLabel;
  latest_obs_date: string | null;
  priority_rank: number | null;
  is_synthetic: boolean;
}

export interface TimeseriesPoint {
  date: string;
  ndvi: number | null;
  baseline_median: number | null;
  band_low: number | null;
  band_high: number | null;
  z: number | null;
  low_quality: boolean;
  is_interpolated: boolean;
}

export interface RainPoint {
  date: string;
  rain_mm: number | null;
  rain14: number | null;
  rain30: number | null;
}

export interface TimeseriesResponse {
  field_id: string;
  drop_start: string | null;
  points: TimeseriesPoint[];
  rainfall: RainPoint[];
}

export interface ModelEvidencePoint {
  date?: string | null;
  dos?: number | null;
  ndvi?: number | null;
  baseline_median?: number | null;
  baseline_lower?: number | null;
  baseline_upper?: number | null;
  deviation_from_median?: number | null;
  below_baseline_band?: boolean;
  is_clear?: boolean;
}

export interface ModelEvidence {
  observations?: ModelEvidencePoint[];
  [key: string]: unknown;
}

export interface ScorePreview {
  field_id: string;
  risk: Risk;
  severity: Severity | null;
  confidence: number | null;
  confidence_label: ConfidenceLabel | null;
  model_score: number | null;
  top_factors: string[] | Record<string, number> | null;
  evidence: ModelEvidence;
  drop_start: string | null;
  rain_context: string;
  model_version: string | null;
  decision_threshold: number | null;
  cannot_assess_reason?: string | null;
  preview: true;
}

export interface MlStatus {
  status?: string;
  ready?: boolean;
  model_version?: string | null;
  [key: string]: unknown;
}

export interface ModelInfo {
  enabled?: boolean;
  source?: string;
  model_version?: string | null;
  name?: string | null;
  task?: string | null;
  training_data?: unknown;
  trained_on?: unknown;
  measured_metrics?: unknown;
  metrics?: unknown;
  limitations?: string[] | null;
  licence?: string | null;
  license?: string | null;
  attribution?: string | null;
  output_specification?: unknown;
  decision_threshold?: unknown;
  risk_mapping?: unknown;
  [key: string]: unknown;
}

export interface ThresholdRange {
  minimum: number;
  maximum: number;
  default: number;
}

export interface RegionScorePreview {
  region_id: string;
  preview: true;
  total_fields: number;
  scored_fields: number;
  counts_by_risk: RiskCounts;
}

export interface ActionCreate {
  status: ActionStatus;
  note?: string | null;
}

export interface ActionUpdate {
  status?: ActionStatus;
  note?: string | null;
}

export interface ActionOut {
  id: string;
  user_id: string;
  field_id: string;
  status: ActionStatus;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface MethodologyOut {
  run_id: string | null;
  params: Record<string, unknown>;
  method_steps: string[];
  validation_report: Record<string, unknown> | null;
  limitations: string[];
  created_at: string | null;
}

export interface HealthResponse {
  status: string;
}