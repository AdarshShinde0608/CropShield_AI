# ML service contract

**Status:** proposed, gated contract. The audited model is not approved for
packaging or production use. This service is optional and is not on the
dashboard/map/chart critical path. The service never writes to MongoDB; the
pipeline owns result persistence and the existing backend serves stored
results. The only database access permitted to the service is a read-only query
of `model_artifacts` by `/v1/model-info`; it does not read operational field,
observation, result, or user data.

## Scope and supported task

The current nested model supports a single-row crop-type prediction and a
separate generic Isolation Forest outlier score. It does **not** implement a
validated field-level crop-stress time-series model. The service exposes the
crop-type result only as optional context after license/provenance, checksum,
loadability, and input-compatibility gates pass.

The model's exact serialized class list, model version, training provenance,
and licensing are not yet verified. The source preprocessing mentions Rice,
Wheat, Cotton, Sugarcane, Builtup, and `Other`; `Other` is dropped before
classifier training, but the actual encoder contents have not been inspected.
The deployed model card must report the verified class list. Do not guess or
map a crop class to a risk state.

## Network and authentication

The service is internal. It has no browser-facing CORS and must only be
reachable from the authorized pipeline caller over HTTPS or a trusted private
network. The backend does not invoke inference for user requests.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | None | Process liveness only; does not imply the model is ready. |
| `GET` | `/ready` | None | `200` only after the image artifact checksum matches the active model card and the model has loaded. Otherwise `503`. |
| `GET` | `/v1/model-info` | `X-Service-Key` | Return the verified model card summary and limitations; no unmeasured metrics. |
| `POST` | `/v1/score` | `X-Service-Key` | Score one field only when a verified active card declares a supported field-level crop-stress mapping. |
| `POST` | `/v1/score/batch` | `X-Service-Key` | Score an all-or-nothing bounded list using the same gated field-level contract. |

The key is supplied to the service and caller through secret environment
configuration, never source control or browser code. Compare keys without
revealing them in logs or errors. Rotate and scope the key to service callers.
Do not log request bodies or model feature values.

## Input

The current audited model is row-wise crop-type classification, not a
field-level stress model. It is not eligible for the risk endpoints and the
service rejects it with `503 MODEL_MAPPING_UNSUPPORTED`. Requests below define
the supported shape for a future verified field-level stress model. The scorer
uses the shared core feature builder for each dated observation; an active
model card must declare the exact supported feature names. No temporal,
spectral, or derived feature may be invented by the service.

`POST /v1/score` request:

```json
{
  "field_id": "F012",
  "observations": [
    {
      "date": "2026-01-04",
      "dos": 65,
      "ndvi": 0.51,
      "valid_frac": 0.82,
      "season": "Rabi",
      "low_quality": false,
      "is_interpolated": false,
      "indices": {
        "NDVI": 0.51,
        "NDWI": 0.12,
        "EVI": 0.34,
        "GNDVI": 0.42,
        "SAVI": 0.38
      },
      "bands": {
        "Red": 0.11,
        "Green": 0.14,
        "Blue": 0.09,
        "NIR": 0.48,
        "SWIR": 0.23
      },
      "baseline_median": 0.57,
      "baseline_sigma": 0.08,
      "rain_z": -0.7
    }
  ],
  "baseline_observations": [
    {
      "dos": 65,
      "baseline_median": 0.57,
      "baseline_sigma": 0.08
    }
  ],
  "decision_threshold": null
}
```

All numeric values above are illustrative, not measured or recommended feature
values. Each observation has a date, day-of-season, NDVI, valid fraction,
quality flags, season, the documented index and band structures, and optional
rain/baseline context. Dates must be unique valid `YYYY-MM-DD` calendar dates;
`ndvi` must match `indices.NDVI`, be finite, and fall in `[-1, 1]`. Missing,
null, non-finite, extra, or malformed inputs are rejected. A single field is
capped at 180 observations by default. The quality gate runs before model-card
mapping or inference; too few clear observations or stale latest clear data
returns `cannot_assess` without consulting the model. After the gate passes,
the current shared feature builder constructs the model row from the latest
clear observation.
Baseline evidence and onset are computed from the supplied observed/baseline
values using the shared core. `field_id` is an opaque caller correlation ID:
the service does not query operational field data and cannot confirm that it
exists.

The request does not accept `risk`, `severity`, `confidence`, `model_score`,
arbitrary model paths, serialized data, or caller-computed predictions. An
optional `decision_threshold` is supported only when the verified model card
defines a threshold mapping and safe minimum/maximum; the supplied value is
clamped to that card range. Otherwise an override returns
`422 VALIDATION_ERROR`. The service builds model input itself; it never loads
artifacts from a request or fetches model files over the network.

`POST /v1/score/batch` accepts `{"items":[<single-score request>, ...]}`.
Every item meets the single-score schema. By default, a batch is capped at 32
fields, each with at most 180 observations; the configured request byte limit
also applies. The endpoint returns no partial-success response; invalid input
or inference failure rejects the complete batch without echoing feature values.

## Output

`POST /v1/score` success (`200`):

```json
{
  "field_id": "F012",
  "risk": "watch",
  "severity": null,
  "confidence": 0.72,
  "confidence_label": "medium",
  "model_score": 0.72,
  "top_factors": null,
  "evidence": {"observations": []},
  "drop_start": null,
  "rain_context": "not_applicable",
  "model_version": "<version from verified model card>",
  "decision_threshold": null,
  "cannot_assess_reason": null
}
```

The response values above are illustrative. A successful risk response is
available only for a verified model card declaring task `field-level
crop-stress`, class-to-risk mappings, alert severity, and calibrated
`predict_proba` confidence cutoffs. The audited crop-type model does not meet
these requirements. Uncalibrated probabilities remain `model_score` only and
must not be returned as `confidence`. `top_factors` is non-null only when the
loaded estimator exposes per-prediction factors; global feature importance is
not returned as a field explanation.

An unassessable response uses risk `cannot_assess`, null severity/confidence/
model score/threshold/version, a stable `cannot_assess_reason`, and any
baseline/rain evidence that could be computed. This result is returned before
model consultation.

Batch success is `200` with `items` in request order, each using the single-row
response shape. Result count must equal request item count.

`GET /v1/model-info` returns a model-card summary containing `model_version`,
verified task, verified class names, trained-on data description and
attribution, input feature names, artifact SHA-256, runtime/library versions,
measured metrics (or `null` if not produced by a real run), known limitations,
and whether the model is enabled. Do not expose local file paths, secrets, or
unverified dataset claims.

## Errors

All errors use `{"detail": "...", "code": "..."}` and the corresponding HTTP
status. `detail` is safe for callers and does not disclose tracebacks, paths,
keys, or feature values.

| HTTP | Code | Meaning |
|---:|---|---|
| `401` | `SERVICE_KEY_INVALID` | Missing or invalid service key on a protected route. |
| `422` | `VALIDATION_ERROR` | Missing/invalid feature, malformed request, or invalid batch item. |
| `413` | `PAYLOAD_TOO_LARGE` | Request body exceeds configured byte or batch limit. |
| `429` | `RATE_LIMITED` | Caller exceeded the configured service limit. |
| `503` | `MODEL_NOT_LOADED` | Model is not loaded; `/health` may still be live. |
| `503` | `MODEL_MISMATCH` | Checksum/model-card mismatch; fail closed and do not predict. |
| `503` | `MODEL_FORMAT_UNSUPPORTED` | Candidate uses a blocked format or the safe runtime adapter is unavailable. |
| `503` | `MODEL_MAPPING_UNSUPPORTED` | Active model task or mapping is not approved for risk scoring. |
| `500` | `INFERENCE_FAILED` | Prediction failed; no success-shaped fallback. |
| `504` | `REQUEST_TIMEOUT` | Request body receive or application processing exceeded the configured deadline. |

## Startup, artifact integrity, and service limits

The model files are baked into a controlled image under `models/<version>/`.
At startup, and no more frequently than `MODEL_REFRESH_INTERVAL_SECONDS`, the
service reads the active version and its checksum manifest from the read-only
`model_artifacts` collection. It resolves only that validated version name
under the configured image model root, compares the database manifest with the
baked `model_card.json` version and checksum manifest, and verifies every
listed local file. Missing or mismatched files fail closed with `/ready`
returning `503 MODEL_MISMATCH`. The current service has no model deserializer
or ONNX runtime adapter, so every candidate currently remains unready with
`503 MODEL_FORMAT_UNSUPPORTED`; no model is loaded or scoring-enabled. When a
reviewed ONNX adapter is added, a valid newer version must be fully prepared
before one atomic runtime-reference swap. If refresh fails, the previously
loaded runtime remains in memory. The service never downloads model files,
accepts model paths from requests, or loads files from request data.

Production enforces `MODEL_DIR=models`, relative to the repository-root
working directory used by Render's native Python service. Reviewed files are
placed in that directory during the build and verified locally at startup.
Development may point `MODEL_DIR` at a local model directory; production must
use files from the reviewed build and must never download or load files from a
request.

Defaults are `MAX_REQUEST_BYTES=1048576` (1 MiB), `MAX_BATCH_SIZE=32`,
`MAX_OBSERVATIONS_PER_FIELD=180`, and `REQUEST_TIMEOUT_SECONDS=30`. The
middleware bounds both declared and streamed request bodies and applies the
deadline to body receive and application processing. Each response includes
`X-Request-ID`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'`,
and `Cache-Control: no-store`.

The default rate limit is 60 requests per minute for each service-key digest
and each direct client IP, with `/health` and `/ready` exempt. These in-memory
windows are per process/instance only; limits are not shared across replicas
and reset on restart. Behind a proxy, the limiter sees the peer IP from the
ASGI connection; do not trust forwarded-IP headers unless the proxy chain is
explicitly configured and trusted.

The service constructs its initial runtime once during application startup and
logs the measured model-load duration and process resident memory. Do not
record these values as deployment characteristics until a real, checksum-
verified model has been loaded in the target Render native service. No such
model load has yet been measured; the existing model artifacts remain gated
and are not approved for service use. The ML service currently refuses all
model formats because its approved ONNX adapter is not implemented.

The service previously deserialized joblib artifacts; P47 removed that code
path and its runtime dependencies. `.joblib`, `.pkl`, and `.pickle` candidates
are now explicitly rejected, and `.onnx` candidates are also rejected until
the ONNX runtime adapter and parity checks are implemented. SHA-256 verifies
file integrity, not provenance; reintroducing pickle/joblib would restore a
high-severity arbitrary-code-execution risk and is prohibited.

Focused P47 code-path review found no `eval`, `exec`, subprocess execution, or
model deserialization in `ml-service/app/`. MongoDB supplies only the active
version and checksum manifest; no file is downloaded or loaded from request
data. The service remains fail-closed and cannot load any candidate model
until a reviewed safe runtime is implemented.

A local Windows pytest/TestClient startup using a metadata test double with no
active model record measured
`startup_elapsed_ms=0.34` and `process_memory_bytes=95842304`;
`model_load_time_ms` was `null` because no model was available to load. This
is test-harness baseline telemetry only, not loaded-model or target-image
memory evidence. The model's 512 MB fit therefore remains unknown.

The measured on-disk artifact total is 337.28 MiB. Loaded-model resident
memory, cold-start time, and inference latency are unknown. Treat 512 MB as
the stated free-tier planning limit, not a proven capacity. Do not enable the
service on that tier until the complete image has passed measured memory and
startup tests. If it does not fit, inference is batch-only in a controlled
pipeline worker; the pipeline persists outputs and the existing backend serves
stored results.
`ml-service` has no result persistence and performs no MongoDB writes. Its
restricted read-only metadata connection is limited to `model_artifacts`.

Deployment must provide a dedicated MongoDB credential restricted to
read-only access to `model_artifacts`; effective database permissions have not
been verified against a live MongoDB deployment. If metadata is missing or the
database is unavailable, `/v1/model-info` returns a structured `503` error
and never manufactures a success-shaped response. The service code does not
write model metadata or predictions.

The service is optional. Failure or disablement omits crop-type context and
must not block the pipeline's existing risk results or web application. A
missing/invalid core observation remains `cannot_assess` according to the
pipeline rules; classifier failure must never turn it into `normal` or change
its risk.

## P48 local validation status

The P48 parity test runs the same two-observation fixture through the existing
pipeline baseline scorer and the HTTP scoring route with a deterministic,
test-only estimator. It asserts matching risk, severity, and evidence-based
`drop_start`; its `1e-6` tolerance checks the test estimator's fixed score
against its fixture value. This is contract coverage only: it does not
establish parity with a production stress model or ONNX export. The pipeline
has no model score for this existing baseline path, and no approved ONNX
adapter or active model artifact is present. The model-store success test
likewise substitutes a checksum-verifying test loader to cover store
orchestration; it does not prove that the production loader can load ONNX.

The native Render service's build step installs the ML requirements and runs
`scripts/fetch_model.py`. With all artifact settings unset, it explicitly
skips model retrieval; the service remains unready because no active,
supported model exists. If configured, the build retrieves only from HTTPS,
checks the archive digest and every model-card file checksum, and fails on any
mismatch.

At the time of the P48 validation, `models/` contained no active version and
the native Render runtime had not been exercised. Consequently the following
requested deployment measurements were **not measured**:

| Measurement | P48 result |
|---|---|
| Installed dependency size | Not measured for a clean Render build. |
| Native service startup time | Not measured for a Render process. |
| Model load time | Not measured: no active model artifact or supported ONNX loader is available. |
| Process memory after model load | Not measured: no model was loaded. |
| p95 `/v1/score` latency on synthetic data | Not measured: scoring requires a verified model; test-double latency is not a production measurement. |

## Release verification

The current workspace still has no active model under `models/`. The 39
passing ML-service tests (including the parity contract test) exercise a
deterministic test-only estimator and mock model store; they do not load a
production artifact or establish real-model parity. A full local service
journey was not established because MongoDB was not listening locally.
Installed size, native service startup, model-load time, loaded process
memory, and live scoring latency remain unmeasured.
