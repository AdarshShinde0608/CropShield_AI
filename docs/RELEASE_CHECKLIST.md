# Release checklist

**Decision: NO-GO.** Reassess only after the blocking gates below have evidence.

## Blocking gates

- [ ] Verify that the model source, weights, licence, and attribution have
      migrated to reviewed maintained paths, and that tests do not load code or
      data from `cropshield-ai/`. The exporter guard test currently uses a
      symbolic path to assert that protected sources are rejected. Until
      migration is independently verified, preserve the protected directory.
- [ ] Resolve model provenance, training-data terms, attribution, and
      redistribution permission; approve the intended task and input mapping.
- [ ] Implement/verify an approved model runtime and artifact checksums in the
      native Render build; demonstrate readiness fails closed on a checksum
      mismatch.
- [ ] Run held-out evaluation and required robustness/parity checks with a
      documented dataset and leakage-safe split. Keep the model marked **not
      retrained** until actual training occurs.
- [ ] Measure clean native dependency installation, cold startup, model load
      duration, post-load memory, and p95 score latency on the intended Render
      service. Select a plan only from recorded measurements.
- [ ] Run the local processes using the documented scripts, with a disposable
      MongoDB test database, and pass the live registration, field evidence,
      queue, action persistence, Marathi, ML waking/recovery, wrong-key, and
      checksum-mismatch journeys.
- [ ] Lock and audit Python dependencies; review the remaining security
      findings and verify a dedicated read-only Atlas role for ML metadata.
- [ ] Complete local field validation with approved data and experts before
      representing model results as crop-stress evidence.
- [ ] Deploy only after all gates pass; verify health/readiness, CORS,
      credential handling, rollback, and smoke checks. Do not claim deployment
      before these checks occur.

## Verified in this workspace

- Backend: 63 tests passed.
- ML service/parity: 39 tests passed with a deterministic test-only estimator.
- Shared core: 15 tests passed.
- Pipeline: 37 tests passed.
- Frontend typecheck, locale-key parity (208 keys per language), and production
  build passed.
- Ten mocked ML UI Playwright tests passed. The first complete Playwright run
  had one failure because backend validation rejected the test's reserved
  `.test` email domain. After changing the test email and tightening its
  action/menu selectors, the live journey passed alone; the combined suite was
  not rerun to avoid creating more records in an unverified database.
- The last recorded local MongoDB port 27017 check returned `False`. A local
  `/api/health` probe returned HTTP 200, which did not establish end-to-end
  readiness. No native Render service build/start has been verified.
- Diagnostic live-journey runs wrote generated account/action data to the
  API's configured database. That target was not verified and records were not
  deleted; use/inspect a disposable database before further runs.

## Release operator sign-off

- [ ] Product owner approves model/licence and limitations.
- [ ] Security owner verifies credentials, dependency findings, Atlas roles,
      monitoring, and incident/rollback procedures.
- [ ] Engineering owner attaches exact test and measurement run outputs.
- [ ] Deployment owner records service URLs, health/readiness checks, and
      deployment revision without exposing secrets.
