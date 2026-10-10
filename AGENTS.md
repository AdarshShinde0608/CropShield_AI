# CropShield AI: Agent Instructions
## Project
Crop-stress early warning from Sentinel-2. Offline pipeline computes field-level NDVI anomalies and writes to MongoDB; FastAPI serves them; React shows them. Three separate parts: frontend/, backend/, pipeline/.
## Hard rules
- Source of truth: docs/TECHNICAL_ARCHITECTURE.md (structure, API contract, collections, constants, risk vocabulary). Do not rename fields or endpoints without updating that doc.
- Backend never imports from pipeline/ and never calls Earth Engine. Frontend never holds secrets.
- Earth Engine uses a service account JSON key, read from env vars. Never commit keys, .env files or secrets/.
- Shared pipeline thresholds and tunable constants live in packages/cropshield_core/config.py; pipeline/config.py re-exports them for compatibility. The effective configuration is stored with each analysis run. Do not hardcode thresholds elsewhere. Pipeline-only synthetic fixture constants may remain in pipeline/config.py.
- Risk vocabulary: risk in {normal, watch, alert, cannot_assess}; severity in {moderate, high} only for alert; confidence_label in {high, medium, low}.
- Never claim crop failure or a diagnosis. Alerts mean "unusual vegetation behaviour, inspect". Advice text uses "inspect/check", never "pest attack" or "drought confirmed".
- Synthetic data must always carry is_synthetic=true and the UI must show a visible banner.
- Never invent metrics. Validation numbers come only from pipeline/validate.py output.
## Backend
- Python 3.11, FastAPI, Pydantic v2, Motor, PyJWT, bcrypt. Async endpoints. Layers: routes -> services -> database. Type hints everywhere.
- JWT bearer auth (HS256, 60 min). bcrypt password hashing. CORS origins from CORS_ORIGINS env var, never "*" in production.
- Error body: {"detail": str, "code": str}.
- Tests with pytest and httpx; every route needs at least one test.
## Pipeline
- Python, pandas, numpy, scikit-learn. Pure functions, unit-tested with synthetic fixtures. NaN is never treated as 0.
- Earth Engine code only in pipeline/ee_extract.py.
- Model fitting and training happen only in the root `pipeline/` environment (and any training code belongs under `pipeline/train/`). The protected `cropshield-ai/` tree is read-only; its legacy training scripts are not a training surface for this project.
## Model service boundaries
- `ml-service/` performs inference only: it never trains or fits models, calls Earth Engine, or writes to MongoDB.
- The ML service loads model files only from its own built image after verifying the expected SHA-256 checksum. Never load model files from user input, request payloads, or the network at request time. Never store weights in MongoDB.
- Any batch inference worker that loads the same model artifacts must also load them only from a reviewed image after checksum verification.
- The backend never imports model code, `pipeline/`, or `ml-service/`; any ML-service communication is HTTP only. The browser never calls the ML service, and the service has no browser-facing CORS.
- Every ML-dependent feature must degrade gracefully when the service, model, or optional output is unavailable. Precomputed dashboard, map, and chart results must remain usable without request-time inference.
- Never describe the nested crop-type classifier or its per-row Isolation Forest as crop-stress detection. Until a replacement stress model passes the documented validation gates, the existing pipeline stress detector remains the risk decision source.
- The UI must never say "probability of crop failure." A model score is not a confidence estimate unless calibrated and validated as such; label uncalibrated values explicitly as a model score.
- State no metric unless it came from an actual recorded run. Unknown or unmeasured values remain explicitly unknown.
## Frontend
- React + Vite + TypeScript (strict), Tailwind, React Router, TanStack Query, Axios, react-leaflet, Recharts, i18next (en, mr, hi).
- No hardcoded UI strings: use i18n keys. Risk is never conveyed by colour alone (always icon + label).
- Every data view has loading, empty and error states. API types in src/types/api.ts mirror the API contract.
- Devanagari text must render (use Noto Sans Devanagari fallback).
## Workflow
- Small commits, one feature per commit. Run tests before saying a task is done. Do not add features that were not requested.
- Docker is not used anywhere: no Dockerfile, docker-compose, .dockerignore, container images, devcontainers, container-based CI services or docker commands in code, docs, scripts or prompts. Backend and ML service use Render's native Python runtime (runtime: python, buildCommand, startCommand, $PORT, healthCheckPath, PYTHON_VERSION). Any older instruction mentioning Docker is overridden by the native equivalent.

## Protected paths
- `cropshield-ai/` is a protected reference/model folder. Do not delete, move, rename, clean, prune, or otherwise modify anything in this folder, including generated files and artifacts, until the user explicitly confirms that its migration is verified.
- Cleanup procedures and audits must treat the entire `cropshield-ai/` tree as out of scope. This protection overrides any earlier cleanup candidate list or instruction to remove nested/reference projects.
