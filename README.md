# CropShield AI

CropShield AI is an early-warning project that uses Sentinel-2 vegetation data to
help users inspect unusual crop-stress patterns. An offline analysis pipeline
computes field-level NDVI anomalies and writes results to MongoDB; a FastAPI
service exposes the data; a React application displays maps, evidence, and
inspection actions.

**Work in progress.** Risk indicators identify unusual vegetation behaviour for
inspection; they do not diagnose its cause or confirm crop failure.

## Architecture

```text
 OFFLINE / scheduled                        ONLINE
┌───────────────────────┐     ┌──────────┐   ┌─────────────────┐
│ pipeline/             │────▶│ MongoDB  │◀──│ backend/        │
│ Sentinel-2 + CHIRPS   │     └──────────┘   │ FastAPI + JWT   │
│ clean, baseline,      │                    └────────┬────────┘
│ score, validate       │                             │ JSON API
└───────────────────────┘                             ▼
                                               ┌─────────────────┐
                                               │ frontend/       │
                                               │ React + Vite    │
                                               └─────────────────┘
```

The optional `ml-service/` is separate from this request path. It is currently
gated: this checkout has no active model in `models/`, so model-backed preview
and production inference are not available. The project has not been deployed.
The audited nested model's provenance, licence, attribution, supported runtime,
and suitability for crop-stress risk remain unresolved; it has **not** been
retrained. Do not present fixture-based UI tests or synthetic demo records as
evidence of model accuracy.

The pipeline is offline; shared analysis configuration lives in
[`packages/cropshield_core/config.py`](./packages/cropshield_core/config.py)
and is re-exported by `pipeline/config.py` for compatibility. The backend never
calls Earth Engine or imports the pipeline; the frontend does not contain
secrets. Refer to
[`docs/TECHNICAL_ARCHITECTURE.md`](./docs/TECHNICAL_ARCHITECTURE.md) for the
collections, API contract, and full design.

## Local setup

Use Python 3.11.11, Node.js/npm, and either a local MongoDB installation or a
separate development database in MongoDB Atlas. Full Windows PowerShell and
macOS/Linux setup steps, environment examples, and test database guidance are
in [docs/LOCAL_SETUP.md](./docs/LOCAL_SETUP.md) and
[docs/MANUAL_SETUP.md](./docs/MANUAL_SETUP.md).

Create separate virtual environments for `backend/`, `ml-service/`, and
`pipeline/`, install their pinned requirements from the repository root, and
run `npm ci` in `frontend/`. Copy the relevant `.env.example` files to ignored
`.env` files; never use production credentials locally or expose secrets to
the browser.

After setup, start the three local services with `.\scripts\dev.ps1` in
PowerShell or `sh ./scripts/dev.sh` on macOS/Linux. Backend health is
`http://127.0.0.1:8000/api/health`; ML liveness is
`http://127.0.0.1:8001/health`; Vite is at `http://127.0.0.1:5173`.
Playwright starts Vite itself; start the API and ML service before its
end-to-end tests. Real-database tests use only `MONGODB_TEST_URI` and skip
clearly when it is unset.

## Deployment

The frontend is hosted on Vercel, the backend and optional ML service use
Render's native Python runtime, and persistent data uses MongoDB Atlas. See
[docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md). No deployment is claimed.

## Model status

The maintained `models/` path currently contains no approved model artifact.
The ML service remains unready until a reviewed runtime and checksum-verified
artifact are provided. Synthetic fixtures and demo records do not establish
model accuracy.

### Synthetic demo data

Install pipeline dependencies and load the clearly labeled synthetic dataset
into a new, disposable database:

```sh
python -m pip install -r pipeline/requirements.txt
python -m pipeline.seed_demo
```

Set `MONGODB_URI` and `MONGODB_DB` in the environment to select the target. The
seeder refuses to overwrite a database containing other regions; it preserves
existing users and actions and does not fabricate validation metrics. Synthetic
records are flagged, and the application displays a visible synthetic-data
banner.

### Pipeline run

Earth Engine extraction needs a registered Google Cloud project, a service
account, and a key file outside source control. Supply `GEE_PROJECT`,
`GEE_SERVICE_ACCOUNT`, and `GEE_KEY_FILE` through the environment. Earth Engine
code is isolated in `pipeline/ee_extract.py`.

Run extraction and processing using their `--help` options to inspect required
field/data paths and season arguments. To upload an already processed run:

```sh
python -m pipeline.load_to_mongo --data-dir pipeline/data/processed/<run-directory>
```

Review the target MongoDB database and the run's `analysis_run.json` before
loading. See [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) for Atlas deployment.

## Tests and operational guides

- Backend: from `backend/`, run `pytest`.
- Pipeline: from the repository root, run `pytest pipeline/tests`.
- Frontend: from `frontend/`, run `npm run test:i18n`, `npm run typecheck`, and
  `npm run build`.
- ML service: from `ml-service/`, run `python -m pytest tests` with the
  repository root on `PYTHONPATH` for pipeline parity imports.
- Shared core: run `python -m pytest packages/cropshield_core/tests` from the
  repository root.
- End-to-end journey and current environment limitations:
  [`docs/E2E_CHECKLIST.md`](./docs/E2E_CHECKLIST.md).
- Deployment:
  [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).
- Three-minute demo and judge Q&A:
  [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md).
- Model decision and licence gates:
  [`docs/MODEL_DECISION.md`](./docs/MODEL_DECISION.md).
- Security and sustainability:
  [`docs/SECURITY_REVIEW.md`](./docs/SECURITY_REVIEW.md) and
  [`docs/SUSTAINABILITY.md`](./docs/SUSTAINABILITY.md).
- Current release evidence and go/no-go gates:
  [`docs/FINAL_STATUS.md`](./docs/FINAL_STATUS.md) and
  [`docs/RELEASE_CHECKLIST.md`](./docs/RELEASE_CHECKLIST.md).

## Screenshots

Add verified product screenshots here; do not use screenshots containing
unlabeled or real personal/field data.

| View | Screenshot |
|---|---|
| Dashboard and synthetic banner | `docs/screenshots/dashboard.png` (placeholder) |
| Field detail and evidence chart | `docs/screenshots/field-detail.png` (placeholder) |
| Marathi interface | `docs/screenshots/marathi.png` (placeholder) |
