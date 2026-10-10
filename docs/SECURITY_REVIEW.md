# Security and resilience review

**Review date:** 2026-10-10  
**Scope:** `backend/`, `ml-service/`, `pipeline/`, shared package and runtime
integration, deployment configuration, and the project dependency manifests.
The protected `cropshield-ai/` tree was not inspected or modified.

## Summary

No confirmed exploitable vulnerability was identified in the reviewed
application code. The ML service has no approved active model in the reviewed
checkout and fails closed when it cannot load a supported checksum-verified
ONNX artifact. This review is not a penetration test, and deployment
configuration, Atlas permissions, and model operation have not been verified
in a live environment.

## Findings and actions

| # | Severity | Finding | Status / action |
|---|---|---|---|
| 1 | 🟡 MEDIUM | Python dependency vulnerability status is unknown: `backend/requirements.txt` uses unpinned packages and `pipeline/requirements.txt` uses lower bounds. `pip-audit` was not available in the review environment, so these dependencies have not been checked against current advisories. | Not changed: exact versions cannot safely be inferred without a reviewed lock/resolution and compatibility test. Generate and review lock files, pin deployment dependencies, then run `pip-audit` for each resolved environment before release. |
| 2 | ⚪ LOW | Least-privilege MongoDB permissions cannot be established by source inspection. The ML service's code performs metadata reads only, but the effective permissions of its configured `MONGODB_URI` are deployment-owned. | Deployment guidance now requires a dedicated Atlas credential with read-only access to `model_artifacts`; verify its role in Atlas before deployment. |
| 3 | ⚪ LOW | Integrated model provenance, redistribution rights, and licence/attribution are unknown and unapproved; no model artifact is present in the reviewed `models/` tree. | Model remains disabled and the service is unready without an approved checksum-verified model. Do not package or activate it until provenance and licence terms are reviewed and documented. |

No source-code security fix was needed based on the reviewed evidence.
Deployment guidance was updated to require a read-only ML metadata account and
to preserve model licence/checksum gates.

## Dependency audit evidence

- `npm audit --prefix frontend --json`: **0 vulnerabilities** across 243
  reported dependency entries.
- `npm audit --package-lock-only --json`: **0 vulnerabilities**; the repository
  root has no dependency entries. The frontend audit is the relevant UI
  dependency result.
- `pip-audit -r backend/requirements.txt`,
  `pip-audit -r ml-service/requirements.txt`, and
  `pip-audit -r pipeline/requirements.txt`: **not run successfully** because
  `pip-audit` is not installed or available on `PATH`. No Python CVE-free
  claim is made.
- `ml-service/requirements.txt` pins its direct third-party requirements to
  exact versions. Backend and pipeline requirements are not fully pinned.

## Controls reviewed

### Secrets and authentication

- No production secret values were found in the reviewed application source
  or environment examples.
- The ML service reads `X-Service-Key`, rejects absent or invalid keys using
  `hmac.compare_digest`, and requires at least 32 bytes in production
  (`ml-service/app/core/security.py`, lines 8-14;
  `ml-service/app/core/config.py`, lines 64-65).
- Backend-to-service requests send the service key in a header and map
  upstream failures to stable error codes. No key material is included in the
  safe client error messages.
- The backend's JWT secret is environment-configured and production settings
  reject the development placeholder or a short value.

### Model artifact loading and integrity

- Model artifacts are expected inside the built image; the model store selects
  the active metadata record and verifies version/checksum structure before
  candidate loading (`ml-service/app/services/model_store.py`, lines 142-203).
- The runtime checks artifact paths and SHA-256 values and rejects pickle and
  joblib suffixes (`ml-service/app/core/model.py`, lines 11-12, 53-102).
- No `eval`, `exec`, or subprocess-based model loading path was identified in
  the ML-service application. The review found no supported ONNX inference
  adapter or active model artifact; readiness and scoring therefore fail
  closed rather than silently returning a model result.

### Database access and failure boundaries

- ML-service application code performs `find_one` metadata reads from
  `model_artifacts`; no database write operations were identified under
  `ml-service/app/`. Actual server-side MongoDB permissions still require
  Atlas-side verification.
- Normal dashboard and map behavior is based on precomputed pipeline results.
  The optional live inference path is separate and reports unavailable/waking
  errors rather than fabricating a successful score.
- Model metadata lookup or model verification failure leaves readiness false.
  Existing loaded-model refresh failures do not replace the last good runtime.

### Input and error handling

- ML requests have configured body-size and timeout bounds, in-memory
  per-instance rate limiting, a batch-size cap, and an observations-per-field
  cap (`ml-service/app/main.py`, lines 93-157;
  `ml-service/app/routes/scoring.py`, lines 80-120).
- Input schemas strictly validate dates, finite numeric values, NDVI ranges,
  and unknown fields (`ml-service/app/schemas/scoring.py`).
- Public errors use stable error codes and do not expose request bodies,
  secrets, or stack traces. Structured service logs propagate request IDs and
  avoid request payload logging.

## Remaining operational risks

- Python dependency advisories remain unknown until the dependency sets are
  locked and successfully audited.
- Configure a distinct read-only Atlas user for `ml-service`; do not reuse a
  write-capable backend or pipeline credential.
- Do not deploy the model inference path as production-ready until the model's
  task, provenance, licence, evaluation gates, ONNX parity, installed
  dependency size, memory, cold-start time, and inference latency are verified
  with real artifacts.
- Render native deployment and production credential behavior were not tested
  by this source review. Keep the ML API key identical on backend and ML
  service, protect it as a secret, and keep it out of browser configuration.

## Release verification update

The release test matrix passed the backend (63 tests), ML service/parity
(39 tests), shared core (15 tests), and pipeline (37 tests). The ML-service
parity test uses a deterministic fixture and does not prove production-model
parity. Frontend typecheck, locale parity (208 keys in each locale), and
production build passed. Ten mocked ML UI Playwright scenarios passed. The
first complete Playwright run had 10 passes and one failure because the
journey's `.test` email domain was rejected by backend validation. The test
fixture and its ambiguous action/menu locators were corrected; the live
journey subsequently passed alone. The combined suite was not rerun after the
fixes because the configured database target was not verified and the test
writes account/action records. Several generated accounts and at least two
actions from diagnostic runs remain in that configured database.

The prior verification did not establish a complete local service journey:
MongoDB was not listening on port 27017, and a prior registration journey
failed without an established cause. The local `/api/health` response alone
does not establish database or end-to-end readiness.
The active model directory contains only its placeholder; no artifact was
loaded, packaged, or deployed.

A current first-party text/history scan excluded dependency/build directories
and the protected `cropshield-ai/` tree, consistent with the cleanup boundary.
It found no private-key marker, AWS/GitHub token format, or credentialed
MongoDB URI. A broad literal-secret heuristic matched two lines in backend
test files; values were withheld and those matches are not classified as
production credentials by this scan. The scan is pattern-limited and does not
cover the protected tree or binary artifacts. Do not treat it as proof that
secrets never existed.
