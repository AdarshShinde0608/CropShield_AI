# CropShield AI end-to-end checklist

Use a disposable MongoDB database. The demo seeder refuses to overwrite a database
that already contains regions, so do not point it at production data.
The live browser journey creates a uniquely named user and inspection action;
it does not delete them. Confirm the API is pointed at the disposable database
before running that journey.

## Prerequisites

- MongoDB is reachable at `MONGODB_URI`.
- Backend dependencies are installed and `backend/.env` contains a local JWT secret.
- Frontend dependencies are installed and `frontend/.env` points `VITE_API_BASE_URL`
  at the local API, normally `http://localhost:8000/api`.
- The backend, ML service, and frontend use separate Python/npm environments;
  see `docs/LOCAL_SETUP.md` for their setup.
- The demo dataset is loaded with `python -m pipeline.seed_demo`.
- From the repository root, `.\scripts\dev.ps1` (PowerShell) or
  `sh ./scripts/dev.sh` (macOS/Linux) starts the API, ML service, and Vite
  development process on ports 8000, 8001, and 5173.
- Playwright starts Vite through `frontend/playwright.config.ts`; the API and
  ML service must already be running for non-mocked journeys.
- For automated browser coverage, install Playwright Chromium once with
  `npx playwright install chromium`, then run `npm run test:e2e`.

## Browser journey

- [ ] Open `/register`, register a unique user, and confirm successful navigation
      to the authenticated dashboard.
- [ ] Log out, then sign in with the newly registered credentials.
- [ ] Confirm dashboard KPIs load and the GeoJSON map renders.
- [ ] Confirm the visible synthetic-data banner is present.
- [ ] Open an alert field from the dashboard's top-fields queue.
- [ ] Confirm the field risk is alert and the NDVI chart renders observed values,
      a baseline series, and the uncertainty band.
- [ ] Change the language to Marathi; confirm translated UI and profile language
      are both updated.
- [ ] Create an inspection action with status `done` and a unique note.
- [ ] Refresh the field detail page; confirm the action and its status remain.
- [ ] Log out; confirm the browser lands on `/login` and the protected dashboard
      is no longer accessible without signing in.

## Model and service failure coverage

The automated UI suite mocks the backend responses. It verifies frontend
degradation and is not a substitute for running the real stack or model.

- [ ] With an approved enabled model card, confirm the field model-result card,
      version, optional factors, evidence chart, and evidence-based onset date.
- [ ] If the card supports a decision threshold, confirm the what-if slider
      debounces previews, labels them "Preview only, not saved", and does not
      persist a result. Confirm region counts use the same preview setting.
- [ ] While ML is waking, confirm the countdown/progress state, disabled live
      controls, one warmup request, and continued access to precomputed data.
- [ ] After readiness changes to ready, confirm the waking notice clears and
      eligible live controls become available.
- [ ] With ML stopped, confirm the dashboard map/summary, inspection queue,
      field evidence chart, and Methodology remain accessible; hide live
      controls and show the unavailable notice.
- [ ] For a wrong service key, confirm preview returns a stable unavailable
      response, the UI does not expose the key or raw upstream error, and no
      `X-Service-Key` is sent by the browser.
- [ ] For a checksum mismatch, verify the ML service `/ready` returns 503
      `MODEL_MISMATCH`; then verify the backend/UI degrade to unavailable while
      precomputed views remain usable.
- [ ] Switch to Marathi while ML is unavailable; confirm the status and
      dashboard labels remain translated.

Run the mocked ML UI scenarios with:

```sh
cd frontend
npm run test:e2e -- tests/e2e/ml-features.spec.ts
```

## Failure triage

- API errors or an empty dashboard: check `/api/health`, `MONGODB_URI`, and that
  `python -m pipeline.seed_demo` completed against the same database.
- CORS failures: set `CORS_ORIGINS` to the exact frontend origin, including its
  scheme and port; do not add a path or trailing slash.
- A missing alert in the top-fields list: inspect the seeded `field_results` and
  confirm the current season run is marked current. Do not change the test to
  accept a different risk category.
- Missing chart band: inspect the current-season observations and verify that
  `baseline_median` and `baseline_sigma` are present in the API response.
- Action lost after refresh: inspect the action API response and confirm the
  action belongs to the signed-in user and field.
- Date discrepancies: compare ISO `YYYY-MM-DD` dates at the API boundary and
  verify the current season selected by the newest analysis run.

## Current execution status

**Not a full-stack run:** the last recorded local database probe returned
`False` for port 27017, so MongoDB was not listening locally. A direct local
`/api/health` probe returned HTTP 200 with `status=ok`. The first complete
Playwright run had one registration failure:
the test's `example.test` address was rejected by backend email validation
because `.test` is a reserved special-use domain. The fixture now uses
`example.com`, and the live journey subsequently passed when run alone. The
test also received more precise Marathi action/menu locators. The full combined
suite was not rerun after those fixes to avoid repeating its data-writing
journey against an unverified database. This is not a verified local end-to-end
run.
Earlier diagnostic journey attempts wrote several generated test accounts and
at least two inspection actions to the API's configured database. That database
was not verified, and the records were not removed because the API exposes no
test cleanup route; check the target database before any further live run.

Verified in this workspace:

- `npm run test:e2e -- tests/e2e/ml-features.spec.ts`: 10 passed. These are
  controlled frontend tests with mocked API responses, including waking,
  recovery, unavailable service, simulated wrong-key failure, simulated
  checksum-mismatch degradation, and Marathi.
- `npm run test:e2e` before the final journey-test fixes: 10 passed, 1 failed
  because the test email used the rejected reserved `.test` domain.
- After correcting that fixture and the action/menu selectors,
  `npm run test:e2e -- tests/e2e/journey.spec.ts`: 1 passed.
- The combined Playwright suite was not rerun after these fixes; see the
  disposable-database warning above.
- Backend: 63 passed. ML service and parity: 39 passed. Shared core: 15 passed.
  Pipeline: 37 passed.
- ML-service unit coverage verifies `/ready` returns 503 `MODEL_MISMATCH` on a
  simulated checksum failure; backend unit coverage maps a wrong service key
  to `ML_UNAVAILABLE`.
- Frontend `npm run typecheck`, `npm run test:i18n` (208 locale keys per
  language), and `npm run build` passed.

The application was not deployed. The checkout has no active model under
`models/`; model load, native dependency size, cold start, post-load memory,
and live `/v1/score` p95 remain unmeasured. Re-run the real browser journey
with a disposable `MONGODB_TEST_URI` and approved model artifact before
claiming service readiness or checksum integration.
