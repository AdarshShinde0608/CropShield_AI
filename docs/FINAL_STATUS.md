# Release status

## Summary

**No-go for production release.** This checkout is a work-in-progress
prototype. The backend, ML service, shared core, pipeline, and frontend
typecheck/locale/build validations pass. A complete local service journey was
not established because MongoDB is not configured for this run, and there is
no active model artifact. The CropShield UI is available locally at
`http://127.0.0.1:5174/login`; authenticated API features are unavailable
without the backend and its database. Model licence/attribution remain
unresolved, and no deployment occurred.

The protected `cropshield-ai/` directory remains untouched. The required
migrated model files are not present in this checkout (`models/` contains only
`.gitkeep`, and `pipeline/model_runtime/` is absent); migration is therefore
not verified and no removal authorization has been given.

## Verification performed

| Command | Result |
|---|---|
| `npm run test:e2e -- tests/e2e/ml-features.spec.ts` (from `frontend/`) | 10 passed. UI/backend responses were mocked; this is not a live service test. |
| `npm run test:e2e` (from `frontend/`, before final journey fixes) | 10 passed, 1 failed. Backend email validation rejected the test's reserved `.test` domain. |
| `npm run test:e2e -- tests/e2e/journey.spec.ts` (from `frontend/`, after fixes) | 1 passed. The test registers a unique account and inspection action; the configured database was not verified or cleaned. |
| `npm run typecheck` (from `frontend/`) | Passed. |
| `npm run test:i18n` (from `frontend/`) | Passed; 208 matching locale keys in en, mr, and hi. |
| `npm run build` (from `frontend/`) | Passed. |
| `python -m pytest tests -q` (from `backend/`, backend venv; `PYTHONPATH` also included the repo root and pipeline test environment site-packages) | 63 passed. The backend runtime requirements remain separate; the seed API test imports the pipeline package. |
| `python -m pytest tests -q` (from `ml-service/`, ML venv; `PYTHONPATH` included the repo root and pipeline test environment site-packages) | 40 passed, including deterministic test-only parity fixtures. |
| `python -m pytest packages/cropshield_core/tests pipeline/tests -q` (pipeline venv, from repository root) | 56 passed. |
| `npm run dev -- --host 127.0.0.1 --port 5174` and `GET http://127.0.0.1:5174` | Vite started and returned HTTP 200; browser rendered the CropShield sign-in page. This verifies the frontend only, not API connectivity. |
| `Test-NetConnection 127.0.0.1 -Port 27017 -InformationLevel Quiet` | Returned `False`; no local MongoDB listener. |
| `GET http://127.0.0.1:8000/api/health` | HTTP 200, `status=ok`. This health response did not establish database or end-to-end readiness. |

The Playwright suite was not rerun in this native-runtime migration pass. The
previous focused mocked ML suite and corrected live journey passed in separate
runs, but the live journey used a configured database that was not verified.
Earlier diagnostic attempts wrote uniquely generated accounts and inspection
actions to that database; inspect it before another live run.

The isolated journey command was tried five times during diagnosis: four
attempts failed in sequence on the reserved email domain, an overly strict
Marathi label selector, an ambiguous `details` selector, and a hidden-menu
locator. The fifth attempt passed after correcting those test assumptions.

The first backend/ML test attempts from the repository root failed collection
because those packages need their own working directories. Backend tests need
the pipeline test environment on `PYTHONPATH` because
`backend/tests/test_seed_demo_api.py` imports `pipeline.seed_demo`; ML parity
tests need the same environment for pandas-based fixtures. This does not add
pipeline or model dependencies to the backend runtime requirements.

## Model and deployment measurements

No model was retrained, packaged, loaded, activated, or deployed. The model
remains disabled. The passing ML parity test uses a deterministic test
estimator; it does not establish parity with a production model.

| Requested measurement | Result |
|---|---|
| Backend dependency installation | 81.97 seconds; 60,799,073 bytes under a fresh Windows Python 3.11.11 environment. Not a Render build measurement. |
| ML service dependency installation, including shared core and configured artifact-fetch step | 62.28 seconds; 100,694,344 bytes under a fresh Windows Python 3.11.11 environment. No artifact was configured, so fetch correctly skipped. Not a Render build measurement. |
| Native dependency installation size | Not measured for a clean Render build. |
| Native service startup time | Not measured in Render. |
| Production model load time | Not measured; no production artifact was loaded. |
| Process memory after model load | Not measured; no production model was loaded. |
| p95 `/v1/score` latency on synthetic data | Not measured; live model scoring was not run. |
| Held-out model metrics | Not measured; no suitable dataset/split or evaluation run was provided. |
| Real-field validation | Not performed. |
| Deployment state | Not deployed. |

The ML service contract contains prior test-harness telemetry and an audited
on-disk size for nested artifacts. Those are not native service or loaded-model
measurements and are not substituted for the requested values.

## Limitations and open items

- Model task fit, source provenance, licence, attribution, and redistribution
  rights remain unresolved. The model is not retrained.
- The required model code/weights/runtime were not verified in maintained
  paths; do not delete the protected `cropshield-ai/` tree.
- Python dependency vulnerability checks remain unknown because `pip-audit`
  was unavailable. Frontend `npm audit` reported zero vulnerabilities in the
  prior security review; this does not establish Python dependency safety.
- Effective MongoDB least-privilege permissions need live Atlas verification.
- Native Render build/start, real registration/action persistence, model
  checksum mismatch from a build-installed artifact, and production
  cold-start behavior remain unverified.
- No regional field validation or calibrated stress-model evaluation exists.
  Synthetic data and fixture scores are never evidence of accuracy.
- Render/Vercel and Atlas services and credentials have not been deployed or
  checked.

See [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) for the release gates.
