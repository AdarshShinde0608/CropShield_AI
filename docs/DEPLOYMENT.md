# Deployment guide

**Status:** operational instructions only; no service has been deployed. The
React frontend is intended for Vercel, the FastAPI backend and optional ML
service use Render's native Python runtime, and MongoDB Atlas provides
persistent data.

## Render Blueprint and platform fields

The root `render.yaml` defines the demo API only as a `type: web` Python
service in `oregon` on the Free plan. It deliberately omits `rootDir`, so the
build and start commands run from the repository root. The default Blueprint
sets `ML_SERVICE_ENABLED=false`: there is no approved stress-model artifact,
so the first deployment must not present live model scoring as available.
When an approved model passes the documented gates, add the ML service as a
separate Render service using the instructions below; do not enable the
feature flag before that service is verified.

The Blueprint uses Render's documented `runtime`, `region`, `plan`,
`buildCommand`, `startCommand`, `healthCheckPath`, and `envVars` fields.
`PYTHON_VERSION=3.11.11` matches `.python-version`. See Render's
[Blueprint specification](https://render.com/docs/blueprint-spec) and
[Python version guidance](https://render.com/docs/python-version). Confirm
that the target account supports the selected runtime and plan before
deploying.

The backend build command is `pip install -r backend/requirements.txt`; its
start command is `uvicorn --app-dir backend app.main:app --host 0.0.0.0
--port $PORT`. Backend requirements do not install the shared core, pipeline,
or model runtime.

Only after a model is approved, deploy the optional ML service from the repo
root with build command
`pip install -r ml-service/requirements.txt && python scripts/fetch_model.py`
and start command
`uvicorn --app-dir ml-service app.main:app --host 0.0.0.0 --port $PORT`.
Its requirements install `packages/cropshield_core` from the repo root. The
service cannot become ready until an approved local artifact passes its
checksum checks.

## Prepare MongoDB Atlas

Create an Atlas project and cluster in a region close to Render's Oregon
service. Create a dedicated database user scoped to the demo database and
grant only the access needed by the API. Use a separate, short-lived
database identity when seeding if practical; revoke it after seeding.

Configure Atlas Network Access using the outbound IP ranges shown for the
chosen Render service/plan. Do not use `0.0.0.0/0` as a production shortcut.
If the plan does not provide egress that can be safely allow-listed, use an
appropriate static-egress plan or stop rather than opening the database to
the entire internet.

The API receives `MONGODB_URI` and `MONGODB_DB` as Render environment
variables. Never put a MongoDB URI in source control or any `VITE_*` variable.
The optional ML service, when approved and deployed, must have a separate
Atlas identity with read-only access to `model_artifacts` only; verify that
custom role against a live Atlas account before enabling the service.

## Step-by-step demo deployment

This path deploys the existing UI and persisted pipeline results with
**clearly labeled synthetic demo data**. It does not deploy an inference
service, claim model accuracy, or use the root `dataset.csv`; that dataset's
rights and production suitability have not been established.

### 0. Rotate exposed credentials first

Credentials pasted into chat, tickets, source files, or shell history must
not be used. Revoke/replace the exposed Atlas database password and Google
Cloud API key before proceeding. Replace the exposed JWT secret with a new
random value. Do not send replacement secrets in chat or commit them.

Generate a new JWT secret locally, then paste it directly into Render's
secret field. In Windows PowerShell:

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 48
$rng.GetBytes($bytes)
[Convert]::ToBase64String($bytes)
$rng.Dispose()
```

On macOS/Linux with OpenSSL:

```sh
openssl rand -base64 48
```

The pipeline's Earth Engine integration requires a registered Earth Engine
Google Cloud project and a **service-account JSON key**, not a browser/API
key. That credential is not needed to deploy the demo. If later running
Earth Engine extraction, keep the service-account key outside Git and use it
only in the pipeline environment; never add it to Vercel, Render's API
service, or frontend variables.

### 1. Create the Vercel project and note its production origin

1. Sign in to Vercel and import `AdarshShinde0608/CropShield_AI`, branch
   `main`.
2. Set Root Directory to `frontend`, Framework Preset to Vite, Build Command
   to `npm run build`, and Output Directory to `dist`. Do not set the repository
   root as the frontend root.
3. Leave `VITE_API_BASE_URL` unset for this first deploy. Vite can build with
   its local default; the API-backed screens will not work until the next
   steps.
4. Deploy once and copy the exact production origin, e.g.
   `https://your-project.vercel.app` (origin only, no path or trailing slash).

Do not add MongoDB, JWT, Earth Engine, or ML-service secrets to Vercel.

### 2. Create and seed a dedicated synthetic demo database

1. In MongoDB Atlas, create a dedicated database named `cropshield_demo`.
   Use a new database user/password (not the credentials pasted into chat).
   Copy the URI from Atlas and replace its database segment with
   `cropshield_demo` if necessary.
2. Allow-list the Render outbound IP ranges for the selected service. If you
   are seeding from your computer, temporarily add your current IP, then remove
   that entry after seeding.
3. From the repository root, install the locked pipeline dependencies if they
   are not already installed:

   ```powershell
   py -3.11 -m venv pipeline\.venv
   & .\pipeline\.venv\Scripts\python.exe -m pip install --require-hashes -r pipeline\requirements.txt
   ```

4. In PowerShell, securely enter the **new demo database URI** and seed only
   the synthetic fixture. The password input is masked and the variable is
   removed after the command:

   ```powershell
   $secureUri = Read-Host "New Atlas demo URI" -AsSecureString
   $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUri)
   try {
       $env:MONGODB_URI = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
       $env:MONGODB_DB = "cropshield_demo"
       & .\pipeline\.venv\Scripts\python.exe -m pipeline.seed_demo
   } finally {
       Remove-Item Env:MONGODB_URI -ErrorAction SilentlyContinue
       Remove-Item Env:MONGODB_DB -ErrorAction SilentlyContinue
       [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
   }
   ```

   On macOS/Linux, use a hidden prompt in Bash instead:

   ```sh
   read -r -s -p "New Atlas demo URI: " MONGODB_URI
   printf '\n'
   export MONGODB_URI MONGODB_DB=cropshield_demo
   pipeline/.venv/bin/python -m pipeline.seed_demo
   unset MONGODB_URI MONGODB_DB
   ```

   The seeder refuses a database containing a non-demo region, but replaces
   its demo-region fixture. Use only this new, dedicated demo database. The
   resulting fields and analysis are synthetic and must remain visibly
   labeled in the UI.

### 3. Deploy the API on Render

1. Sign in to Render and create a Blueprint Instance for this GitHub
   repository, branch `main`. Review `render.yaml` before applying it; the
   default Blueprint should create only `cropshield-api`, with
   `ML_SERVICE_ENABLED=false`.
2. Enter the new secret values when prompted:
   - `MONGODB_URI`: the rotated URI for the dedicated demo database.
   - `MONGODB_DB`: `cropshield_demo`.
   - `JWT_SECRET`: the newly generated secret from step 0.
   - `CORS_ORIGINS`: the exact Vercel production origin from step 1. Multiple
     origins are comma-separated; never use `*`.
3. Keep `APP_ENV=production` and `ML_SERVICE_ENABLED=false`. Do not configure
   an ML-service URL/key or set the feature flag to true for this demo.
4. Wait for the native Python build and deploy. The API lifespan pings Atlas
   and creates required indexes; a failed database connection prevents the
   service from starting.
5. Verify `https://<render-api-host>/api/health` returns `{"status":"ok"}`.
   This only checks the running API process after its database-connected
   startup; it does not prove the model or real data is available.

### 4. Point Vercel at the API

1. In Vercel Project Settings → Environment Variables, set
   `VITE_API_BASE_URL` to `https://<render-api-host>/api` for Production.
   This is a public API URL, not a secret.
2. Redeploy the Vercel production deployment so the Vite build embeds the
   updated value.
3. Check browser devtools/network: the frontend requests must go to the
   Render API origin, and the browser must never receive MongoDB, JWT, or
   service-key values.

### 5. Smoke-test and maintain the demo

1. Open the Vercel production URL. Register a demo account, sign in, and
   confirm the region, field list, field evidence chart, queue, and synthetic
   data banner load. Switch to Marathi and confirm labels render.
2. Confirm the ML notice indicates live analysis is unavailable; that is
   expected because the ML service and model are deliberately disabled.
   Dashboard/map/chart results should continue to use persisted pipeline
   results and must not depend on request-time scoring.
3. Check Render logs for startup or database errors. Never copy log entries
   containing credentials into chat or tickets.
4. Keep the demo Atlas database isolated from real data. To refresh it, run
   the seeder only against `cropshield_demo`; never point it at a production
   field database. Remove temporary developer-IP access when finished.
5. Rotate the JWT secret only with an intentional user-session invalidation
   plan; existing tokens will no longer validate after rotation.

### 6. Add live model inference only after approval

The ML service is deliberately excluded from the default demo Blueprint.
Before adding it as a separate Render native Python service, the model must
pass source/licence and attribution review, held-out evaluation, parity and
robustness tests, checksum verification, and memory/startup/latency tests
against the chosen Render plan. Then configure a dedicated read-only Atlas
identity, a new `ML_SERVICE_API_KEY` of at least 32 bytes in both services,
an immutable model package URL plus verified SHA-256 (or reviewed committed
files), and the backend's HTTPS `ML_SERVICE_URL`. Set
`ML_SERVICE_ENABLED=true` only after `/health`, `/ready`, authenticated
`/v1/model-info`, wrong-key rejection, and backend degradation behavior have
been verified. Until then, do not describe deployment as model-enabled or
production-ready for crop-stress inference.

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
