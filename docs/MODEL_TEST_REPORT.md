# CropShield AI model test report

**Status:** Criteria approved and frozen; evaluation complete to the extent
the maintained code and data permit.
**Prepared:** 2026-10-10
**Scope:** Read-only evaluation of the integrated model and its pipeline/service
surfaces. No model code or weights may be changed during testing.

## SUMMARY

**NO-GO for integrated-model validation.** The maintained `models/` directory
has no versioned artifact, `pipeline/model_runtime/` is absent, and the ML
service's actual loader fails closed even for a checksum-matching ONNX-shaped
fixture because ONNX inference is not implemented. `pipeline/run_pipeline()`
still calls the baseline scorer and writes `model_version` and
`model_checksum` as `null`; it does not invoke a model. No model weights or
model code were changed or deserialized.

The shared-core, pipeline, and ML-service suites passed (15, 37, and 39 tests).
Those results cover the current baseline and service contracts, not the
integrated production model. Input probes found two confirmed criteria
failures: the ML request schema accepts NDVI `-0.5`, outside the approved
`[-0.1, 1.0]` range, and rejects an empty series rather than returning
`cannot_assess`. NaN/Inf, duplicates, and missing dates are rejected.
Insufficient, all-cloudy, and stale observations returned `cannot_assess` with
zero estimator calls in test-only spy probes.

There is no labelled dataset or extracted field data in `pipeline/data/`, so
held-out metrics, real-field CSV/charts, disagreement analysis, and the
requested perturbation matrix were not run. A native target service run was
not performed; model load
time, memory, and live `/v1/score` and `/v1/score/batch` latency were not
measured. Existing parity coverage uses a deterministic test estimator only.
Fix request validation and provide an approved, checksum-verifiable ONNX model
and implemented runtime before attempting end-to-end model validation.

## Approved pass/fail criteria — frozen before testing

**Approved by the user on 2026-10-10 before test execution.** The values below
are frozen and were not adjusted after results were collected.

| ID | Layer | Pass criterion | Decision |
|---|---|---|---|
| C1 | Artifact and integrity | A versioned artifact exists in the maintained `models/<version>/` path; every artifact checksum exactly matches the model card and active metadata. Only the documented safe runtime may load it. Missing artifacts, absent loader, or checksum mismatch fail closed. Do not deserialize `.pkl`, `.pickle`, or `.joblib` files. | APPROVED — frozen |
| C2 | Repeatability | For the same artifact, runtime, and input, repeated inference returns exactly equal classes and scores (no numeric tolerance). | APPROVED — frozen |
| C3 | Output and model card | Output shape, field names, types, and numeric bounds match the model card and API contract. Required card fields are complete: name, version, task, inputs/outputs, class mapping and cut-offs where applicable, training-data provenance, measured metrics or explicit unknowns, limitations, licence/attribution, runtime versions, source revision, and checksums. Missing required metadata is a failure. | APPROVED — frozen |
| C4 | Input validation and gating | Non-finite NDVI is never replaced with zero. Empty, insufficiently short, all-cloudy, or stale observations return `cannot_assess` without invoking the model. Values outside `[-0.1, 1.0]` and duplicate dates are rejected by validation. Missing dates are not fabricated as zero-valued observations; acceptable gaps are handled only by documented alignment/gating rules. | APPROVED — frozen |
| C5 | Synthetic sanity fixtures | Every synthetic input/output is marked `is_synthetic=true`. Healthy-curve, single-day-dip, and noise-only fixtures produce no `alert`. Across controlled persistent-drop fixtures, a larger drop must not lower the applicable pipeline alert/rank score or produce a less severe risk. Any model score remains a model score and is not relabeled as stress confidence or a risk probability. Synthetic outcomes are not accuracy evidence. | APPROVED — frozen |
| C6 | Perturbation robustness | Use a recorded fixed seed and 100 variants per fixture per perturbation: NDVI noise within ±0.01, observation-date shifts within ±3 days, sowing-date shifts within ±7 days, and random removal of 10% of observations while retaining the minimum required by gating. For non-boundary fixtures, risk-class changes must be no more than 5% per perturbation type; report every denominator and boundary fixture separately. | APPROVED — frozen |
| C7 | Held-out metrics and leakage | If labelled held-out data with documented provenance exists, report precision, recall, F1 per class, confusion-matrix counts, and calibration only when outputs are presented as confidence. Same field, area, or year may not occur in both train and test splits. Metrics are descriptive only until the team approves task-specific minimums; no metrics are invented when data is absent. | APPROVED — frozen |
| C8 | Real-data review | If approved real extracted fields exist, produce the requested CSV (15 highest-ranked, 15 random, and all `cannot_assess` fields, including available NDVI series, baseline band, and outputs), one chart per top-15 field, and a list of disagreements with the retained z-score comparator. Record selection seed and counts. No manual-review conclusion is claimed before review. | APPROVED — frozen |
| C9 | Parity | On identical fixtures and configuration, risk, severity, and `drop_start` match exactly. Same-runtime numeric scores differ by at most `1e-6` absolute. If an exported runtime exists, its numeric scores differ by at most `1e-4` absolute while categorical outputs remain exact. | APPROVED — frozen |
| C10 | Performance | Measure in the intended Render native service configuration. Model-load limit: 60 seconds. `/v1/score` p95 limit: 2 seconds; `/v1/score/batch` p95 limit: 10 seconds at the documented maximum batch size. Peak resident memory after load and scoring must remain at or below 80% of the selected service memory limit. For the documented 512 MiB planning limit, this is at most 409.6 MiB peak RSS. Report load time, memory, and p50/p95 exactly as measured. | APPROVED — frozen |
| C11 | Integrity and API security | Checksum tampering is rejected and readiness remains non-ready with `MODEL_MISMATCH`; no model file is loaded from request data or the network. Missing/wrong service keys return the documented 401 response; oversized payloads return 413; rate-limited requests return 429; `/ready` remains 503 until a verified model is loaded. Logs contain no credentials, request bodies, or secret values. | APPROVED — frozen |

## Pre-test inventory and constraints

- The maintained `models/` directory currently contains only `.gitkeep`;
  `pipeline/model_runtime/` is absent.
- `docs/MODEL_DECISION.md` says the selected serving route is ONNX, but no ONNX
  adapter or export/parity evidence is available. It explicitly rejects
  `.joblib`, `.pkl`, and `.pickle` artifacts in the service.
- The audit and decision records identify unresolved data/model provenance,
  licence, attribution, feature compatibility, and task-fit gates. The audited
  crop-type classifier and per-row Isolation Forest are not approved as
  crop-stress risk detectors.
- Therefore model-load, checksum, true model inference, and production-model
  parity tests are currently blocked unless a reviewed, supported artifact and
  runtime are present in maintained paths. No unsafe deserialization will be
  attempted to make a smoke test pass.
- `pipeline/data/raw/` and `pipeline/data/processed/` contain only `.gitkeep`.
  There are no extracted fields or labelled samples to evaluate.
- No native target service was run during that evaluation. Model and target
  service measurements could not be performed without a maintained artifact.
- The `cropshield-ai/` protected source tree was not read or executed during
  this test task. The approved safe-runtime policy and absence of a maintained
  artifact make executing its pickle/joblib model an unsafe and non-compliant
  substitute.

## Results by layer

| Layer | Status | Result |
|---|---|---|
| Criteria approval | PASS | User approved the frozen criteria before testing. |
| Smoke / load / checksum / card | FAIL / NOT RUN | No maintained model version or complete card exists. A checksum-correct dummy ONNX fixture is rejected as `MODEL_FORMAT_UNSUPPORTED`; the real model was not loaded. |
| Repeatability / output contract | NOT RUN | No real estimator/runtime is available. Mock estimator coverage is not model repeatability evidence. |
| Input validation | FAIL | `-0.5` NDVI is accepted although the frozen lower bound is `-0.1`; an empty observation list is rejected with `ValidationError` rather than returning the frozen `cannot_assess` response. Non-finite values, `1.01`, duplicate dates, and a missing date were rejected. |
| Quality gating | PASS (test-only estimator) | Too-short, all-cloudy, and stale probes returned `cannot_assess`; the estimator spy recorded zero prediction calls. Core quality tests also passed. |
| Synthetic sanity fixtures | NOT RUN for integrated model | The pipeline test suite passed, but no approved model is integrated and the complete frozen fixture matrix was not run. |
| Perturbation robustness | NOT RUN | No integrated model or perturbation run. |
| Held-out metrics / leakage | NOT RUN | No labelled dataset or split is present; no metrics are available. |
| Real-data review | NOT RUN | Raw/processed data directories contain placeholders only. |
| Pipeline / service / export parity | NOT RUN for a real model | Existing parity test passed with a deterministic test-only estimator and the baseline pipeline path; it is not production model parity. |
| Performance | NOT RUN | No approved model to load or score in a native target service. |
| Integrity / API contract | PASS (unit/fixture level) | ML-service tests passed, including checksum mismatch, fail-closed loader, auth, request size, rate limiting, and readiness. No production model or deployed service was exercised. |

### Input/gating evidence

- Request-schema probe results: `NaN` and `Inf` → `ValidationError`;
  `NDVI=1.01` → `ValidationError`; `NDVI=-0.1` → accepted (inclusive
  boundary); `NDVI=-0.5` → **accepted, criterion failure**; duplicate dates,
  empty observations, and missing dates → `ValidationError`. Under the frozen
  criterion, empty observations are also a failure because they must produce a
  `cannot_assess` response rather than a validation rejection.
- Instrumented `score_field()` probe with a test-only estimator:
  - one clear observation → `cannot_assess`, reason
    `too_few_clear_observations`, zero prediction calls;
  - two all-cloudy observations → `cannot_assess`, reason
    `too_few_clear_observations`, zero prediction calls;
  - two stale observations → `cannot_assess`, reason `stale_observation`,
    zero prediction calls.
- Existing core tests passed for NaN/invalid fractions not counting as clear,
  stale boundaries, and evidence gaps. These are quality-gate checks, not a
  real-model inference test.

### Integrity/parity evidence

- A temporary, non-model ONNX-shaped file with a matching SHA-256 was not
  loaded; `load_model()` returned `ready=False`,
  `error_code=MODEL_FORMAT_UNSUPPORTED`. This demonstrates the current loader
  has no ONNX runtime, not that a model artifact failed validation.
- A deliberately mismatched expected checksum returned
  `MODEL_MISMATCH` and `ready=False`.
- Existing `test_parity.py` passed with a deterministic estimator and mock
  model store. It asserted matching risk, severity, and `drop_start`, and score
  within `1e-6`; no ONNX/exported candidate was involved.

## Failures and suspected causes

No pytest assertion failed in the suites run. The frozen input-handling
criteria failed in two observed cases: request validation accepted
`NDVI=-0.5`, and an empty observation list was rejected instead of returning
`cannot_assess`. The model smoke criterion also cannot pass with the current
maintained tree and loader.

**Failure and suspected cause — NDVI lower bound:** `ml-service/app/schemas/scoring.py`
allows `-1.0` for `SpectralIndices.NDVI` and `Observation.ndvi`, while the shared
core configuration declares `min_valid_ndvi=-0.1`. The scorer's quality gate
will not count `-0.5` as clear, but schema validation still accepts the request.
**Proposed fix:** use the shared configured NDVI bounds in both schema fields
(or an equivalent shared validator) and add tests for `-0.100001` rejection,
`-0.1` acceptance, and matching `indices.NDVI`; do not change the frozen range.

**Failure and suspected cause — empty series:** `ScoreRequest.observations`
has `min_length=1`, so the request stops at schema validation and never reaches
the quality gate. The scorer's current insufficient-evidence path also assumes
there is a latest observation. **Proposed fix:** define a safe no-observation
response path that returns `cannot_assess` with empty evidence and a stable
reason without consulting the model, then add an endpoint-level regression
test. Keep malformed observation objects and invalid dates rejected.

**Blocked smoke test — model/runtime absent:** `models/` contains no candidate
version and the service loader currently has no ONNX session implementation.
**Proposed fix:** after provenance/licence and feature-compatibility approval,
place a reviewed ONNX artifact, complete model card, and implemented
checksum-first runtime in maintained paths, then rerun the frozen smoke and
parity criteria. Do not restore pickle/joblib loading.

## Limitations

The accepted criteria are frozen, but most model-specific gates remain
unmeasured because there is no maintained candidate or data. Passing unit tests
does not establish model loadability, predictive performance, robustness,
latency, memory fit, or real-field suitability. Synthetic results, if later
collected, will not establish real-world accuracy. The audited model's crop
type and per-row anomaly tasks are not approved as crop-stress detection.

## What to fix first

1. Fix the NDVI request lower-bound validation without changing the approved
   `[-0.1, 1.0]` limits, and implement an empty-series `cannot_assess` path;
   add boundary and endpoint regression tests.
2. Resolve model provenance, licence, feature compatibility, and task fit.
3. Implement the approved ONNX runtime and provide a versioned,
   checksum-verifiable artifact and complete model card in maintained paths.
4. Identify approved labelled held-out data and real extracted fields if
   metrics or real-data review are expected.
5. Rerun the frozen model smoke, fixture, parity, API, and performance checks
   in the target native service; do not treat test doubles as model evidence.

## Commands run

All commands below ran after criteria approval. No model code or weights were
modified.

| Command / probe | Result |
|---|---|
| `& .venv\Scripts\python.exe -m pytest packages\cropshield_core\tests; exit $LASTEXITCODE` (repository root) | 15 passed in 0.05s. |
| `$env:PYTHONPATH = (Resolve-Path .).Path; Push-Location ml-service; & ..\.venv\Scripts\python.exe -m pytest tests; $testExit = $LASTEXITCODE; Pop-Location; exit $testExit` | 39 passed in 2.04s; one Starlette deprecation warning about `httpx` with `starlette.testclient`. |
| `& .venv\Scripts\python.exe -m pytest pipeline\tests; exit $LASTEXITCODE` (repository root) | 37 passed in 12.44s. |
| Native Render target build/start | Not run during this model evaluation; no maintained model artifact exists. |
| `Get-ChildItem pipeline\data -File -Recurse` | Only `pipeline\data\raw\.gitkeep` and `pipeline\data\processed\.gitkeep`; no dataset. |
| Static source search in `ml-service\app` for `eval`, `exec`, `subprocess`, `pickle`, `joblib`, `urlopen`, HTTP fetch calls, and `download` | Only the explicit unsafe-suffix rejection constant matched; no `eval`, `exec`, subprocess, or request-time artifact/network loader found. |
| Pylance selected-interpreter temporary artifact probe: matching checksum on dummy `.onnx` bytes | `ready=False`, `MODEL_FORMAT_UNSUPPORTED`; not an ONNX parsing or model-load test. |
| Pylance selected-interpreter temporary artifact probe: incorrect expected checksum | `ready=False`, `MODEL_MISMATCH`. |
| Pylance selected-interpreter `score_field()` probe with test-only estimator spy | One-observation, all-cloudy, and stale cases gated as `cannot_assess`; `predict_calls=0`. |
| Pylance selected-interpreter schema probes | `NaN`, `Inf`, `1.01`, duplicate dates, empty series, and missing date rejected; `-0.5` accepted (criterion failure); `-0.1` accepted. |
| `rg` static search for unsafe execution/deserialization/network loaders in `ml-service\app` | One expected match: unsafe serialized suffixes are enumerated for rejection. |

### Commands not run and why

- Render's native build/start commands: not run during this model evaluation;
  no maintained model artifact exists.
- A `pipeline.run_pipeline` invocation: not run because raw/processed data
  directories contain no NDVI or rainfall CSVs, and the pipeline has no
  integrated model adapter.
- Live model-backed `POST /v1/score` and `/v1/score/batch`: not run because
  there is no maintained model version and the ONNX runtime is unimplemented.
  The passing route tests use a deterministic test-only estimator.
- Real-model determinism, complete model-card validation, full synthetic
  fixture and perturbation matrices, exported-runtime parity, held-out
  metrics/leakage checks, and real-data export/charts: not run because the
  required model, exported runtime, labels, and extracted fields are absent.
- Target native-service load time, memory, and p50/p95 latency: not run because
  no loadable model artifact is available. No proxy or
  test-double measurements are reported as production-model metrics.
