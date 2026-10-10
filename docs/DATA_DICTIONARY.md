# CropShield AI Data Dictionary

Field names and collections follow Section 5 of `TECHNICAL_ARCHITECTURE.md`. Examples are illustrative and do not represent observed or validated measurements. `N/A` means no constrained enum/value set is defined; it does not mean the field is optional. Exact required/optional/nullability rules are enforced by the implementation schemas.

## Shared conventions

| Convention | Definition |
|---|---|
| ID | String identifier unless an implementation-specific MongoDB `_id` is used internally. API IDs are serialized as strings. |
| Date | Calendar date serialized as ISO 8601 `YYYY-MM-DD`. |
| Timestamp | UTC date-time serialized as ISO 8601. |
| Boolean | JSON `true` or `false`. |
| Missing | Missing/unavailable data remains missing/null as schema permits; it is never silently replaced by zero. |
| Synthetic | If an output is synthetic, `is_synthetic` is `true` and the UI displays a banner. |
| Common enums | `risk`: `normal`, `watch`, `alert`, `cannot_assess`; `severity`: `moderate`, `high` only for `alert`; `confidence_label`: `high`, `medium`, `low`. |

## MongoDB collections

### `users`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `email` | string | Login identity. | `officer@example.org` | Valid email; unique. |
| `password_hash` | string | bcrypt hash; never returned by API. | `<bcrypt-hash>` | Hash only; never plaintext. |
| `name` | string | Display name. | `Officer` | N/A |
| `role` | string | Application user role. | `officer` | `officer`, `farmer` |
| `language` | string | User's selected locale. | `mr` | `en`, `mr`, `hi` |
| `created_at` | timestamp | Account creation time. | `2026-01-01T12:00:00Z` | UTC timestamp. |

### `regions`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `name` | string | Region display name. | `Example region` | N/A |
| `state` | string | State/province containing region. | `Example state` | N/A |
| `bbox` | GeoJSON-style bounds object/array | Spatial bounding box used for extraction/display. | `<configured region bounds>` | Coordinate reference and exact schema must be consistent with extraction. |
| `centroid` | GeoJSON Point or coordinate pair | Representative region centre. | `<configured centroid>` | Valid geographic coordinates. |

### `fields`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `region_id` | string | Parent region ID. | `region-01` | Must identify a stored region. |
| `field_id` | string | Stable field identifier. | `F012` | Unique. |
| `name` | string | Field display name. | `Field 12` | N/A |
| `geometry` | GeoJSON Polygon | Field boundary. | `{"type":"Polygon","coordinates":[...]}` | Valid GeoJSON Polygon; 2dsphere indexed. |
| `area_ha` | number | Field area in hectares. | `2.4` | Non-negative finite number. |
| `is_synthetic_boundary` | boolean | Indicates generated/demo boundary geometry. | `true` | Boolean. |
| `cluster` | string/number or null | Optional grouping/cluster label. | `cluster-1` | N/A; nullable if not assigned. |

### `seasons`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `season_id` | string | Stable season identifier. | `2025-26` | Unique. |
| `label` | string | Human-readable season. | `2025-26` | N/A |
| `start` | date | Season start. | `2025-11-01` | ISO date. |
| `end` | date | Season end. | `2026-03-31` | ISO date; not before start. |
| `role` | string | Season's use in analysis. | `current` | `baseline`, `current` |

### `observations`

Unique key: `(field_id, season_id, date)`.
MongoDB retains current-season observations only. Each plotted current
observation carries computed baseline median/spread values; historical raw
observations remain in offline pipeline inputs rather than the online database.

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `field_id` | string | Observed field. | `F012` | References a field. |
| `season_id` | string | Observation season. | `2025-26` | References a season. |
| `date` | date | Acquisition/regularised observation date. | `2026-01-04` | ISO date. |
| `dos` | integer | Day-of-season count from 1 November. | `65` | Positive integer in the configured season. |
| `ndvi` | number or null | NDVI observation. | `0.51` | Finite value when measured; missing remains null/unavailable. |
| `valid_frac` | number or null | Fraction of valid pixels/area for the observation. | `0.82` | `[0,1]`. |
| `baseline_median` | number or null | Historical median for comparable DOS. | `0.58` | Finite number when assessable. |
| `baseline_sigma` | number or null | Robust baseline spread used by scoring. | `0.07` | Non-negative finite value when assessable. |
| `z` | number or null | Robust standardized deviation from baseline. | `-0.9` | Finite when calculable. |
| `pct_dev` | number or null | Percentage deviation from baseline. | `-12.1` | Finite when calculable; formula/configuration documented by pipeline. |
| `is_interpolated` | boolean | Whether the value was interpolated. | `false` | Boolean. |
| `low_quality` | boolean | Whether observation quality is below configured standard. | `false` | Boolean. |

### `rainfall`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `region_id` | string | Region associated with rainfall data. | `region-01` | References a region. |
| `season_id` | string | Season for the rainfall observation. | `2025-26` | Only current-season rainfall rows are persisted. |
| `date` | date | Rainfall observation date. | `2026-01-04` | ISO date. |
| `rain_mm` | number or null | Rainfall amount in millimetres. | `0.0` | Non-negative when measured; unavailable is not zero. |
| `rain14` | number or null | Configured trailing 14-day rainfall aggregate. | `4.2` | Non-negative when available. |
| `rain30` | number or null | Configured trailing 30-day rainfall aggregate. | `4.2` | Non-negative when available. |
| `rain_z` | number or null | Standardized rainfall anomaly/context value. | `-0.8` | Finite when calculable. |

### `field_results`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `field_id` | string | Field the result describes. | `F012` | References a field. |
| `region_id` | string | Region containing the field. | `region-01` | References a region. |
| `season_id` | string | Current analysis season. | `2025-26` | References a season. |
| `run_id` | string | Producing pipeline run. | `run-2026-02-08-a` | References an analysis run. |
| `risk` | string | Field-level risk category. | `alert` | Common risk enum. |
| `severity` | string or null | Alert severity. | `moderate` | `moderate`, `high`; only when risk is `alert`. |
| `confidence` | number | Pipeline assessment confidence, separate from any crop-classifier score. | `0.62` | `[0,1]`; produced by the pipeline's documented confidence method. |
| `confidence_label` | string | Human-readable pipeline confidence band. | `medium` | `high`, `medium`, `low`. |
| `crop_type` | string or null | Optional crop-type context returned by the approved crop classifier. | `null` | Verified model-card class only; never a stress or risk label. |
| `model_version` | string or null | Version of the model that produced optional model fields. | `null` | Must match the verified model card; null when no model output exists. |
| `model_score` | number or null | Raw score returned by an approved model. | `null` | Preserve the model's documented scale; not pipeline confidence or a failure probability. |
| `top_factors` | array of objects or null | Per-field model explanation, only when the inference implementation emits one. | `null` | Never substitute global feature importance. |
| `evidence` | object or null | Pipeline baseline evidence supporting the separate risk decision. | `null` | Values must come from measured observations/baseline; does not assert a cause. |
| `decision_threshold` | number or null | Threshold used by an approved, versioned model decision, if applicable. | `null` | Null when no approved model decision threshold was used. |
| `z_score` | number or null | Current robust standardized anomaly score. | `-2.1` | Finite when calculable. |
| `pct_below_normal` | number or null | Percent below baseline as defined by pipeline. | `24` | Finite when calculable; not a probability. |
| `drop_start` | date or null | Supported onset date for qualifying trend. | `2026-01-14` | ISO date or unavailable. |
| `latest_obs_date` | date or null | Latest observation contributing to result. | `2026-02-08` | ISO date or unavailable. |
| `n_valid_obs` | integer | Number of valid observations used. | `3` | Non-negative integer. |
| `baseline_years` | integer | Number of baseline seasons used. | `6` | Non-negative integer. |
| `rain_context` | string or null | Categorical rainfall context. | `dry_spell` | Categories defined by pipeline; null/unavailable is distinct from normal/zero rainfall. |
| `advice_key` | string or null | Localization key for advice. | `advice.inspect_moisture` | Must resolve through locale dictionaries when supplied. |
| `advice` | string or null | Inspection-oriented advice text. | `Check soil moisture and irrigation status in this field.` | Use inspect/check wording; no diagnosis. |
| `priority_score` | number or null | Configured score used to order inspection. | `0.78` | Finite when ranked; no universal scale implied. |
| `priority_rank` | integer or null | Relative rank for the region/season. | `3` | Positive integer when ranked. |
| `if_flag` | boolean or null | Legacy optional Isolation Forest flag. | `null` | Retiring from the target inference path; null when not produced. It never determines project risk alone. |
| `is_synthetic` | boolean (API projection) | Synthetic flag from the associated analysis run, returned with the result. | `false` | Boolean; true must remain visible in UI. It may be joined from `analysis_runs` rather than stored redundantly in this collection. |

`evidence`, when present, is a pipeline-produced object with only measured,
available fields. Its baseline comparison may contain `latest_observation_date`,
`observed_ndvi`, `baseline_median`, `baseline_sigma`, `z_score`,
`pct_below_normal`, and `baseline_years`; unavailable values remain null or are
omitted according to the API schema. It supports the independent pipeline risk
decision and is not a causal explanation from the crop-type model.
Synthetic evidence is generated for UI/demo-path testing only. It must carry
`is_synthetic=true` and must never be used as evidence of model accuracy.

### `model_metadata`

This collection stores model-card metadata only. It must never contain model
weights or serialized Python objects. Unknown or unmeasured model-card values
remain null/unavailable.

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `model_version` | string | Immutable identifier for the reviewed model artifact set. | `<verified-version>` | Unique; do not invent before artifact verification. |
| `task` | string | Supported model task. | `crop_type_context` | Must not claim crop-stress detection for the audited model. |
| `feature_names` | array of strings | Required input feature names. | `[]` | Must match the verified artifact and accepted service schema. |
| `class_names` | array of strings | Verified model class labels. | `[]` | Derive from trusted model metadata; do not guess from source categories. |
| `sha256` | object | Mapping of each artifact filename to its expected checksum. | `{}` | Every value is a 64-character SHA-256 hex digest from the trusted build artifact; never weights. |
| `runtime` | object | Runtime and library versions used by the image. | `null` | Record actual pinned and tested versions. |
| `trained_on` | object or null | Verified training-data identity and description. | `null` | Dataset provenance, domain, and license must be verified. |
| `attribution` | string or null | Required data/model attribution. | `null` | Must follow verified license terms. |
| `metrics` | object or null | Metrics from an actual recorded evaluation. | `null` | No metric without a real run and documented protocol. |
| `limitations` | array of strings | Known task/input/domain limitations. | `[]` | Must include that the audited model is not stress detection. |

### `analysis_runs`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `run_id` | string | Unique identifier for pipeline execution. | `run-2026-02-08-a` | Unique. |
| `created_at` | timestamp | Run creation time. | `2026-02-08T10:00:00Z` | UTC timestamp. |
| `season_id` | string | Current season analyzed by the run. | `2025-26` | Must match the current-season result rows. |
| `model_version` | string or null | Version of the approved model used by the run. | `null` | Null if no approved model contributed. |
| `model_checksum` | string or null | SHA-256 checksum identifying the model artifact set used. | `null` | 64 hexadecimal characters when a model contributed; null otherwise. |
| `params` | object | Snapshot of every configured constant used. | `{"DOS_WINDOW":12,"MIN_BASELINE_YEARS":3}` | Keys/values correspond to `pipeline/config.py` for the run. |
| `is_synthetic` | boolean | Whether this run's data/results are synthetic. | `true` | Boolean. |
| `n_fields` | integer | Number of fields processed. | `12` | Non-negative integer. |
| `notes` | string | Operator/run notes. | `Synthetic demo seed` | N/A |

### `validation_reports`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `run_id` | string | Run that produced the report. | `run-2026-02-08-a` | References an analysis run. |
| `loyo` | object | Leave-one-year-out validation output, including false alerts per field-season. | `<measured report object>` | Only actual `pipeline/validate.py` output. |
| `injection` | object | Injected anomaly metrics, including recall, false-alarm rate, delay, F1, and per-magnitude results when computed. | `<measured report object>` | Only computed metrics; absent metrics are unavailable. |
| `thresholds_sweep` | array/object | Results of configured threshold sweep. | `<measured sweep output>` | Only actual validation output. |

Nested metric keys depend on the validation procedure and are documented with the emitted `pipeline/validate.py` schema. Never create placeholder measurements that look real.

### `actions`

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `user_id` | string | User who created/owns the action. | `user-01` | References a user; server-assigned. |
| `field_id` | string | Field inspected. | `F012` | References a field. |
| `status` | string | Inspection-action state. | `pending` | `pending`, `done`, `needs_expert`. |
| `note` | string or null | User-entered inspection note. | `Checked field boundary.` | Optional; maximum 500 characters. |
| `created_at` | timestamp | Action creation time. | `2026-02-08T11:00:00Z` | UTC timestamp; server-assigned. |
| `updated_at` | timestamp | Last update time. | `2026-02-08T11:00:00Z` | UTC timestamp; server-assigned. |

## API-visible fields not stored as a single collection field

| Field | Type | Meaning | Example | Allowed values / constraint |
|---|---|---|---|---|
| `access_token` | string | Signed JWT returned by login/register. | `<JWT>` | HS256; 60-minute expiry; treat as secret. |
| `token_type` | string | Authorization scheme. | `bearer` | `bearer`. |
| `id` | string | Serialized user identifier in safe profile response. | `user-01` | String representation of user ID. |
| `status` | string | Health response status. | `ok` | `ok` only when process reports healthy. |
| `regions` | array | Region entries returned by `GET /regions`. | `[]` | Each entry includes region identity/name/state and available latest-run information. |
| `risk_counts` | object | Counts grouped by risk in region summary. | `{"alert":2,"watch":1}` | Keys use the risk enum; values are non-negative integers. |
| `latest_observation_date` | date or null | Most recent observation represented in region summary. | `2026-02-08` | ISO date or unavailable. |
| `run_id` | string or null | Analysis run represented in summary/feature. | `run-2026-02-08-a` | References `analysis_runs`; null only when unavailable. |
| `type` (GeoJSON FeatureCollection) | string | GeoJSON collection discriminator. | `FeatureCollection` | Literal `FeatureCollection`. |
| `features` | array | Field features in region GeoJSON response. | `[]` | Valid GeoJSON Feature objects. |
| `type` (GeoJSON Feature) | string | GeoJSON feature discriminator. | `Feature` | Literal `Feature`. |
| `geometry` (API feature) | GeoJSON Polygon or null | Field geometry rendered on map. | `{"type":"Polygon","coordinates":[...]}` | Valid GeoJSON geometry. |
| `properties` | object | Field result properties attached to feature. | `{"field_id":"F012","risk":"watch"}` | Uses field-result fields below. |
| `field_id` | string | Field identifier in result, queue, and feature responses. | `F012` | Stable field ID. |
| `risk` | string | Risk state returned to UI. | `watch` | `normal`, `watch`, `alert`, `cannot_assess`. |
| `severity` | string or null | Alert severity. | `moderate` | `moderate`, `high` only for alert. |
| `confidence` | number | Numeric confidence in result. | `0.62` | `[0,1]`. |
| `confidence_label` | string | Confidence category. | `medium` | `high`, `medium`, `low`. |
| `crop_type` | string or null | Optional crop-type context prediction. | `null` | Verified model-card class only; never a risk label. |
| `model_version` | string or null | Version associated with optional model output. | `null` | Verified model-card version or null. |
| `model_score` | number or null | Uncalibrated crop-classifier score. | `null` | `[0,1]` only when returned by that classifier; label as model score, not confidence. |
| `top_factors` | array of objects or null | Optional per-field model explanation. | `null` | Null unless the inference implementation provides verified per-field factors. |
| `evidence` | object or null | Baseline evidence supporting the pipeline risk decision. | `null` | Measured observations and baseline only; no causal diagnosis. |
| `decision_threshold` | number or null | Threshold for a validated risk decision model, if applicable. | `null` | Null for the audited crop-type classifier; thresholds are pipeline-configured and validation-selected. |
| `z_score` | number or null | Field-level robust anomaly score. | `-2.1` | Finite when calculable. |
| `pct_below_normal` | number or null | Percent below baseline per pipeline definition. | `24` | Finite when calculable; not probability. |
| `drop_start` | date or null | Supported start date of qualifying deviation. | `2026-01-14` | ISO date or unavailable. |
| `latest_obs_date` | date or null | Most recent contributing observation. | `2026-02-08` | ISO date or unavailable. |
| `n_valid_obs` | integer | Number of valid observations used. | `3` | Non-negative integer. |
| `baseline_years` | integer | Number of historical seasons used. | `6` | Non-negative integer. |
| `rain_context` | string or null | Rain context label. | `dry_spell` | Defined by pipeline; unavailable is distinct. |
| `advice` | string or null | Localizable inspection-oriented advice. | `Check soil moisture and irrigation status in this field.` | No confirmed diagnosis. |
| `priority_rank` | integer or null | Relative queue order. | `3` | Positive integer when ranked. |
| `is_synthetic` | boolean | Signals synthetic data/result to client, sourced from the associated analysis run. | `true` | Boolean; visible banner required when true. |
| `points` | array of objects | Time-series observations for a field. | `[{"date":"2026-01-04","ndvi":0.51}]` | Each point uses the documented timeseries fields. |
| `date` | date | Point or rainfall date. | `2026-01-04` | ISO date. |
| `ndvi` | number or null | Vegetation index for the date. | `0.51` | Finite when measured. |
| `baseline_median` | number or null | Historical median on comparable DOS. | `0.58` | Finite when calculable. |
| `band_low`, `band_high` | number or null | Lower/upper baseline band for a plotted observation. | `0.52`, `0.64` | Finite when calculated; otherwise unavailable. |
| `z` | number or null | Observation-level anomaly score in timeseries. | `-0.9` | Finite when calculable. |
| `low_quality` | boolean | Observation quality flag. | `false` | Boolean. |
| `is_interpolated` | boolean | Indicates interpolated point. | `false` | Boolean. |
| `rainfall` | array of objects | Available rainfall points associated with the field time series. | `[{"date":"2026-01-04","rain_mm":0.0,"rain30":4.2}]` | Empty/unavailable is not represented as measured zero. |
| `rain_mm` | number or null | Rainfall amount. | `0.0` | Non-negative when measured. |
| `rain30` | number or null | Rolling 30-day rainfall aggregate. | `4.2` | Non-negative when available. |
| `action_id` | string | Serialized action identifier used by PATCH route. | `action-01` | References an action record. |
| `note` | string or null | Action note. | `Checked field boundary.` | Optional text. |
| `created_at`, `updated_at` | timestamp | Action/profile timestamps as applicable. | `2026-02-08T11:00:00Z` | ISO 8601 UTC. |