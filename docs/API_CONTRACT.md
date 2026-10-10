# CropShield AI REST API Contract

This contract follows Section 6 of `TECHNICAL_ARCHITECTURE.md`. Base path: `/api`. Requests and responses use JSON unless otherwise noted. Authentication uses `Authorization: Bearer <JWT>` on every route except health, registration, login, and methodology.

## Common conventions

- IDs in paths are URL-encoded strings.
- Dates use ISO 8601 calendar form (`YYYY-MM-DD`) unless a timestamp is specified.
- Ordinary data endpoints serve precomputed pipeline results and do not call Earth Engine or calculate risk. The explicit ML score-preview endpoints below are non-persistent exceptions; they proxy stored observations to the optional ML service.
- Risk values: `normal`, `watch`, `alert`, `cannot_assess`.
- `severity` is `moderate` or `high` only when risk is `alert`.
- Confidence labels: `high`, `medium`, `low`; numeric confidence is in `[0,1]`.
- On persisted field results, `confidence` and `confidence_label` describe the pipeline risk assessment; they are not a crop classifier's `model_score`. Preview responses contain the optional model service's mapping and are never persisted.
- Synthetic data is explicitly marked `is_synthetic: true`; the result flag is projected from the associated analysis run.
- Action notes are limited to 500 characters.
- Error body for all routes:

```json
{
  "detail": "Human-readable explanation",
  "code": "STABLE_ERROR_CODE"
}
```

The backend returns the appropriate HTTP status with this shape. Error codes shown in future implementations must be stable and must not expose secrets or internal stack traces.

## Endpoints

### `GET /health`

**Authentication:** none  
**Success:** `200`

```json
{"status":"ok"}
```

Reports process health. It must not claim database readiness unless the implementation checks MongoDB as well.

### `POST /auth/register`

**Authentication:** none  
**Request:** JSON containing `email`, `password`, and any registration profile fields required by the backend schema. Email must be valid; password must contain at least eight characters.

**Success:** `201`. A duplicate email returns `409`.

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "user": {
    "id": "<user-id>",
    "email": "officer@example.org",
    "name": "<display-name>",
    "role": "officer",
    "language": "en"
  }
}
```

`password_hash` and submitted password must never appear in the response.

### `POST /auth/login`

**Authentication:** none  
**Request:**

```json
{"email":"officer@example.org","password":"<password>"}
```

**Success:** `200`; response shape matches registration. Invalid credentials return `401` with a generic message and the common error shape. The endpoint accepts at most five attempts per client IP in a rolling 60-second window; further attempts return `429` with code `RATE_LIMITED`.

### `GET /auth/me`

**Authentication:** required  
**Success:** `200`; returns the safe current-user representation (`id`, `email`, `name`, `role`, `language`). It must not return `password_hash`.

### `PATCH /auth/me`

**Authentication:** required  
**Request:** one or both mutable profile fields:

```json
{"name":"<display-name>","language":"mr"}
```

`language` is one of `en`, `mr`, `hi`. **Success:** `200`; returns the updated safe current-user representation.

### `GET /regions`

**Authentication:** required  
**Success:** `200`; JSON array of region entries with region identity/name/state and latest-run information when available. Exact region response fields follow the response schema and collection dictionary; missing latest-run data is represented as unavailable, not fabricated.

### `GET /regions/{region_id}/summary`

**Authentication:** required  
**Success:** `200`

Returns risk counts, latest observation date, latest run ID, and `is_synthetic` from the latest analysis run. Counts include the supported risk vocabulary. If no run exists, the response distinguishes no available result from a count of zero observations.

### `GET /regions/{region_id}/fields`

**Authentication:** required  
**Success:** `200`; GeoJSON `FeatureCollection`. Each feature contains the field Polygon geometry and result properties. Result properties include, when available, `field_id`, `risk`, `severity`, `confidence`, `confidence_label`, `z_score`, `pct_below_normal`, `drop_start`, `latest_obs_date`, `n_valid_obs`, `baseline_years`, `rain_context`, `advice`, `priority_rank`, `crop_type`, `model_version`, `model_score`, `top_factors`, `evidence`, `decision_threshold`, and `is_synthetic`.

The API must not emit invalid GeoJSON. Fields lacking an assessable result remain identifiable as `cannot_assess`.
The risk and confidence fields are produced by the existing pipeline stress detector, not by the audited crop-type model. Optional model fields may be null or omitted when the model is disabled or unavailable. `model_score` is not confidence unless separately calibrated and validated; otherwise clients must label it as a model score. The crop-type model never changes risk or alert severity.

### `GET /regions/{region_id}/queue`

**Authentication:** required  
**Query parameters:**

| Name | Type | Meaning |
|---|---|---|
| `risk` | Optional risk enum | Restrict results to the selected risk value. |
| `limit` | Optional positive integer | Bound the returned item count. The implementation defines and validates the maximum; invalid limits return a 4xx error. |

**Success:** `200`; ranked inspection list ordered by `priority_rank`, including field ID, risk, severity when applicable, confidence label, latest observation date, and synthetic status.

### `GET /fields/{field_id}`

**Authentication:** required  
**Success:** `200`; latest full field result as described in the field-result dictionary and GeoJSON feature properties. **Not found:** `404` with the common error shape.

### `GET /fields/{field_id}/timeseries`

**Authentication:** required  
**Success:** `200`

```json
{
  "field_id": "F012",
  "drop_start": "2026-01-14",
  "points": [
    {
      "date": "2026-01-04",
      "ndvi": 0.51,
      "baseline_median": 0.58,
      "band_low": 0.52,
      "band_high": 0.64,
      "z": -0.9,
      "low_quality": false,
      "is_interpolated": false
    }
  ],
  "rainfall": [
    {"date":"2026-01-04","rain_mm":0.0,"rain30":4.2}
  ]
}
```

Values above are illustrative only. `drop_start`, baseline band, or rainfall may be absent/null when they cannot be determined; unavailable rainfall is not a measured zero. The loader persists only current-season observations and rainfall rows. Each current observation carries its computed baseline median and spread so the chart can render evidence without historical raw seasons in MongoDB.

### `GET /fields/{field_id}/actions`

**Authentication:** required  
**Success:** `200`; array of the authenticated user’s action records for the field. Each record identifies `id`, `user_id`, `field_id`, `status`, `note`, `created_at`, and `updated_at`. Records owned by other users are not returned.

### `POST /fields/{field_id}/actions`

**Authentication:** required  
**Request:**

```json
{"status":"pending","note":"<optional inspection note>"}
```

`status` is required and one of `pending`, `done`, `needs_expert`; `note` is optional and at most 500 characters. The server assigns current user, field, and timestamps rather than trusting client-supplied ownership/timestamps. **Success:** `201`; returns the created action.

### `PATCH /actions/{action_id}`

**Authentication:** required  
**Request:** one or both mutable fields:

```json
{"status":"done","note":"<optional inspection note>"}
```

`status` uses the action status enum; `note` is at most 500 characters. The API only updates an action the authenticated user owns. **Success:** `200`; returns the updated action. Updating another user's action returns `403`.

### `GET /methodology`

**Authentication:** none  
**Success:** `200`; returns the latest `run_id`, stored run `params`, the ordered plain-language `method_steps`, `validation_report`, fixed `limitations`, and `created_at` when available. `validation_report` contains the report associated with the latest run or `null` when no report exists; no metrics may be fabricated or inferred. If no run exists, `run_id` and `created_at` are `null`, `params` and `validation_report` are empty/null respectively.

### Optional ML service routes

These authenticated endpoints are for explicit operator previews and service
health only. They do not alter persisted `field_results`, trigger Earth Engine,
or place the optional service on the normal dashboard/map/chart path. The
backend communicates with `ml-service` only through HTTP and maps timeouts or
connection failures to `ML_WAKING`; other upstream errors, including an
invalid service key or an open circuit breaker, become `ML_UNAVAILABLE`.

| Method and path | Success | Behavior |
|---|---:|---|
| `GET /ml/status` | `200` | Returns the ML service's `/ready` response. Requires authentication. |
| `POST /ml/warmup` | `202` | Schedules a liveness request; rate-limited to five attempts per client IP per minute. Requires authentication. |
| `GET /model-info` | `200` | Returns service metadata; when the service is waking, falls back to the active `model_artifacts` metadata document with `source: "database"` and `enabled: false`. Requires authentication. |
| `POST /fields/{field_id}/score-preview` | `200` | Sends current-season field observations to `/v1/score`, returns the service result with `preview: true`, and saves nothing. Requires authentication. |
| `POST /regions/{region_id}/score-preview` | `200` | Sends current-season region fields to `/v1/score/batch` in bounded batches and returns total/scored field counts and counts by risk. Requires authentication. |

Score-preview requests may optionally include
`{"decision_threshold": 0.7}`. The backend first checks the active model
metadata and only forwards the override if the model card explicitly declares
a threshold configuration with `minimum`, `maximum`, and `default`; otherwise
it returns `422 VALIDATION_ERROR`. The ML service remains responsible for
clamping supported overrides to the model-card range.

The preview adapter forwards stored date, day-of-season, NDVI, valid fraction,
quality flags, indices, bands, baseline, and rainfall context when available.
It never fabricates model inputs. If current-season records lack the indices
or bands required by the ML contract, the preview returns `422
ML_INPUT_UNAVAILABLE`. A missing field or region returns `404 NOT_FOUND`.
Preview errors and upstream outages never change stored risk results.

## Authentication and error behavior

- JWT algorithm: HS256; claims include `sub` (user ID), `role`, and `exp` (60 minutes after issue).
- Invalid, expired, or missing credentials on protected routes return `401`.
- Unknown region, field, or action identifiers return `404` with code `NOT_FOUND`.
- Pydantic validation failures return a 4xx response with the common error shape.
- Login rate-limit failures return `429` with code `RATE_LIMITED`.
- Authenticated requests for an existing resource owned by another user must not disclose or mutate that resource; return the repository’s consistent authorization/not-found status.
- Database or upstream operational failures must not be converted to successful empty data.

## Compatibility

Endpoint paths and field names are part of the contract. A breaking change requires coordinated updates to this file, `TECHNICAL_ARCHITECTURE.md`, backend schemas/routes, frontend types, and tests.

## Internal ML service contract

The optional inference service is not part of the `/api` backend and is never
called by the browser. It supports only the audited model's row-wise crop-type
context task; it does not return a project risk, severity, or confidence and
does not consume the current NDVI-only time-series schema. Its required feature
row, authentication, limits, errors, model-info response, and readiness
semantics are specified in [ML_SERVICE_CONTRACT.md](./ML_SERVICE_CONTRACT.md).

The pipeline may call the service over authenticated HTTP during a batch run
only after the model gates pass. Pipeline loading persists prediction metadata
alongside `field_results`; the backend serves persisted records and never
imports model code or calls the service to compute a user's request. The model
service is stateless and has no MongoDB connection. Service failure omits
optional crop-type context and does not block the existing pipeline result.