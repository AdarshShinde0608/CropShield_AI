# Deployment guide

**Status:** operational instructions only; no service has been deployed. The
React frontend is intended for Vercel, the FastAPI backend and optional ML
service use Render's native Python runtime, and MongoDB Atlas provides
persistent data.

## Render Blueprint and platform fields

The root `render.yaml` defines two `type: web` services in `oregon`, both on
the Free plan unless measurements justify a different plan. It deliberately
omits `rootDir`, so build and start commands run from the repository root.
The Blueprint uses Render's documented `runtime`, `region`, `plan`,
`buildCommand`, `startCommand`, `healthCheckPath`, and `envVars` fields.
`PYTHON_VERSION=3.11.11` is configured as the documented environment variable
and matches `.python-version`. See Render's
[Blueprint specification](https://render.com/docs/blueprint-spec) and
[Python version guidance](https://render.com/docs/python-version).

The ML service build command is:

```sh
pip install -r ml-service/requirements.txt && python scripts/fetch_model.py
```

Its start command is:

```sh
uvicorn --app-dir ml-service app.main:app --host 0.0.0.0 --port $PORT
```

The backend build command is:

```sh
pip install -r backend/requirements.txt
```

Its start command is:

```sh
uvicorn --app-dir backend app.main:app --host 0.0.0.0 --port $PORT
```

The native ML service runs from the repository root and uses `MODEL_DIR=models`.
Its requirements install `packages/cropshield_core` from that same root.
Backend requirements intentionally do not install the shared core, pipeline,
or model runtime. Render's documented field names do not appear uncertain;
availability of the selected Python patch version and plan features should
still be confirmed in the target Render account before creating services.

## Prepare MongoDB Atlas

1. Create an Atlas project and dedicated database users; use distinct
   credentials for backend writes and ML metadata reads.
2. Create a cluster in the same region as the Render services where possible.
3. Restrict Atlas Network Access to the service's required outbound access.
   Do not use an unrestricted production allow-list.
4. Store the Atlas URI as `MONGODB_URI` in each Render service's secret
   environment. Store the database name in `MONGODB_DB`. Never put a MongoDB
   URI in source control or a `VITE_*` variable.
5. Grant the ML service read-only access to `model_artifacts` only. This
   privilege boundary still requires verification against a live Atlas role.

## Model files and build-time retrieval

There is currently no approved model artifact under maintained `models/`, no
implemented ONNX adapter, and no production model load. Therefore a clean
native service build without model settings leaves the ML service running but
unready; `/ready` must remain `503`. Do not deploy it as an inference service
or invent an artifact URL, checksum, licence, attribution, or metric.

For a future reviewed artifact, prefer committing `models/<version>/` only
when every file is within repository hosting limits and its provenance and
redistribution terms are approved. Otherwise publish an immutable HTTPS ZIP
archive whose root contains `model_card.json`, the listed model files, and the
referenced licence/attribution files. Set `MODEL_VERSION`,
`MODEL_ARTIFACT_URL`, and `MODEL_ARTIFACT_SHA256` in Render's ML service
environment; keep the URL secret if it contains a temporary download token.
The fetch script runs only during the build. It verifies the archive SHA-256,
rejects unsafe archive paths, verifies each checksum listed in the model card,
and installs files under `models/<version>`. A mismatch fails the build.
With all three artifact settings absent, the script explicitly skips retrieval
and the service stays unready. No request-time or startup download is allowed.

Do not rely on Git LFS until its artifact availability in the selected Render
build workflow is verified. Build filesystems are not a persistent artifact
store: an instance restart or new build must not rely on a model downloaded
only at runtime. The service verifies metadata and local checksums at startup
before it can become ready.

## Deployment order and verification

1. Confirm Atlas credentials, service keys, CORS origin, reviewed model rights,
   artifact checksums, and the current release gates.
2. Create the ML service from the repository-root Blueprint. Provide
   `MONGODB_URI`, `ML_SERVICE_API_KEY`, and model artifact settings only when
   an approved artifact is available. Verify `/health`; expect `/ready` to
   return `503` until the active metadata and local artifact match.
3. Create the backend service. Set its `MONGODB_URI`, `JWT_SECRET`,
   `ML_SERVICE_API_KEY` (identical to the ML service's active key),
   `ML_SERVICE_URL`, and exact `CORS_ORIGINS` values. Verify `/api/health`.
4. Deploy the frontend to Vercel with only `VITE_API_BASE_URL` set to the
   backend HTTPS API prefix. The browser must never receive MongoDB, JWT, or
   ML service credentials.
5. When a model has passed all gates, verify authenticated
   `/v1/model-info`, `/ready`, backend `/api/ml/status`, persisted dashboard
   data, and non-persistent preview behavior. Record the exact deployed
   revision and actual run output; do not infer performance from synthetic
   tests.

Render services do not have private networking between each other; configure
the backend with the ML service's public HTTPS URL and rely on TLS, the service
key, request limits, and timeouts. Model files and generated local files on a
service instance are ephemeral and must be reproducible from the reviewed
source/build process. Free instances may sleep and cold-start; the backend
must keep serving precomputed results when live scoring is waking or
unavailable.

The model store logs startup time, model load time, and process RSS when
available. These values have not been measured for a verified native model
load. Treat 512 MiB as the requested Free-plan planning limit, not established
capacity. The model's previously inspected 337.28 MiB disk footprint does not
predict resident memory. Do not claim the model fits a Free service. If a
reviewed runtime does not fit with headroom, select one of the measured
alternatives: a lighter runtime or ONNX export with parity tests, a paid
instance, or batch-only serving with persisted results. Do not claim a
deployment until these measurements and live checks exist.

## Publishing and rolling back a model version

1. Run `pipeline/evaluate.py` against approved held-out data and inspect the
   JSON report, leakage checks, limitations, provenance, rights, and parity.
2. Run `pipeline/export_model.py --version <version> --dry-run`, then export
   only after the gates and rights are satisfied. Confirm the model card's
   `artifact_checksums`, `artifact_files`, `license_file`, and
   `attribution_file` before making an immutable build archive.
3. Use the existing activation gate to activate only a matching, complete
   non-synthetic evaluation with verified checksums and a filled licence.
   Verify the active `model_artifacts` record contains metadata only.
4. Upload the exact package to its approved immutable HTTPS location, record
   its SHA-256, then set `MODEL_VERSION`, `MODEL_ARTIFACT_URL`, and
   `MODEL_ARTIFACT_SHA256` for the ML build.
5. Verify the new service's `/health`, `/ready`, and authenticated
   `/v1/model-info` before sending any live preview traffic. If checks fail,
   keep the old revision active, restore the previous model metadata/version,
   and redeploy the last known-good build. Confirm readiness and backend
   degradation behavior after rollback.

## Service-key rotation

The ML service accepts a current `ML_SERVICE_API_KEY` and, during a rotation,
an optional `ML_SERVICE_API_KEY_PREVIOUS`. Use a plan that supports overlapping
deployments and at least two healthy instances if uninterrupted service is
required; the Free plan's restart/sleep behavior does not provide a
zero-downtime guarantee.

1. Generate a new key outside the repository. Add it to the ML service as
   `ML_SERVICE_API_KEY_PREVIOUS`, retaining the current key as
   `ML_SERVICE_API_KEY`; deploy the overlap configuration.
2. Verify the ML service accepts both keys without logging either. Update the
   backend `ML_SERVICE_API_KEY` to the new value and deploy the backend using
   Render's zero-downtime deployment capability, if available on the chosen
   plan.
3. Verify `/api/ml/status` and an authenticated preview. Remove the old key
   from `ML_SERVICE_API_KEY_PREVIOUS` and redeploy the ML service.
4. Verify the old key now receives `401 SERVICE_KEY_INVALID`, the new key is
   still accepted, and no key value appears in logs.

If the service plan cannot maintain overlapping instances, a brief ML
preview interruption is expected. Do not describe that rotation as
zero-downtime; precomputed backend views remain available by design.
