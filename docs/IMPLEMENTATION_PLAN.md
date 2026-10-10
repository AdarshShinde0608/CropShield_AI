# CropShield AI — 24-Hour Hackathon Implementation Plan

**Status:** Proposed plan only; this document does not claim any task is complete.  
**Team:** Four members — A (data/remote sensing), B (ML), C (frontend), D (backend/integration/pitch).  
**Execution rule:** Execute prompts P6–P32 one at a time, strictly in order. Before each prompt, attach `#file:AGENTS.md` and `#file:docs/TECHNICAL_ARCHITECTURE.md` as context. Run that prompt's acceptance check; then `git commit` only after it passes. Do not start the next prompt while the current step is broken. Keep every change within those source documents and the active prompt.

## 1. Preparation and sequencing

Before P6, complete Phase 0:

1. Confirm `AGENTS.md` is at the repository root.
2. Copy `01_architecture_and_file_structure.md` to `docs/TECHNICAL_ARCHITECTURE.md` as the architecture baseline, retaining its existing sections unchanged.
3. Confirm the API, data model, risk vocabulary, and constants in that document are readable and consistent with `AGENTS.md`.
4. Record the exported UXPilot design location for Phase 5; do not invent a replacement design if the export is unavailable.
5. Create and use the requested local MongoDB environment without committing secrets.

For each numbered prompt, stop on a failing acceptance check, fix only the active prompt's issues, rerun its check, then commit. The hour assignments below are timeboxes, not completion claims. A passing checkpoint is required before the sequence advances.

## 2. Member ownership and parallel work

Only one prompt is active at any time. Parallel work means the other members can review/test the active prompt's interface or contribute within its bounded scope; it does not mean beginning the next P prompt early.

| Member | Primary responsibility | Cross-support |
|---|---|---|
| A — Data/remote sensing | P13 synthetic data; P14 extraction/config; input-data and field-boundary readiness. | Review pipeline data assumptions and synthetic labelling during active prompts. |
| B — ML | P15–P21 cleaning through validation/orchestration. | Review risk/quality edge cases and define acceptance fixtures for the active task. |
| C — Frontend | P22–P29, importing the UXPilot design before implementation. | Review API response needs and localization/accessibility as they arise. |
| D — Backend/integration/pitch | P6–P12; coordinate P30–P32 integration, deployment, demo and pitch. | Maintain route contract, local stack readiness, and integration checklist. |

The active prompt owner leads; the other members review that prompt's bounded change, test evidence, and compatibility with `AGENTS.md`/architecture. No stream may modify unrelated features.

## 3. Dependencies

```text
Phase 0 architecture + agent instructions
  → P6 backend scaffold
  → P7 auth → P8 schemas → P9 region/field reads → P10 actions/methodology
  → P11 route tests → P12 hardening
  → P13 synthetic seed (40 fields; API-visible risk mix)
  → P14 config/extraction → P15 clean/time alignment → P16 baseline/grouping
  → P17 scoring/persistence/onset → P18 rain/confidence/advice
  → P19 optional Isolation Forest → P20 validation → P21 orchestration/load
  → UXPilot design import → P22 frontend scaffold → P23 API/auth → P24 i18n
  → P25 shell/dashboard → P26 map → P27 detail → P28 queue/methodology
  → P29 read-aloud/accessibility → P30 E2E → P31 deployment → P32 demo/docs
```

- P13 depends on the collection/schema contract and the region/field read endpoint. The planned hour-8 seed makes a repeatable API fixture available well before frontend implementation and integration, unblocking backend/frontend data work without waiting on live Earth Engine.
- P11 uses an isolated test database and its own fixtures; it must not depend on P13's demo database.
- P14 is the only Earth Engine integration step. It requires credentials and a project configured outside Git. The prompt refers to an existing `ee_extract.py` to adapt; if no source is provided, do not fabricate its contents—confirm scope and implement only the architecture-approved extractor interface.
- P16 must exclude current-season observations from the baseline. P17 depends on the baseline output. P18 depends on scores and available CHIRPS data. P20 depends on pipeline outputs; P21 wires the completed stages.
- P22 requires the separately designed UXPilot export/screens. P23 depends on the P8 API schemas and P7 auth routes; P25–P28 depend on P9/P10 endpoints and P13 seed data.
- P30 requires the whole local stack, test credentials, and data. P31 follows a passing local integration check. P32 may include only numbers emitted by real validation/test runs; all unavailable values stay placeholders.

## 4. Hour-by-hour schedule

The schedule budgets prompts sequentially and uses within-prompt role pairing. At each checkpoint, the team makes a go/no-go decision. If a prompt fails acceptance, pause the clock's sequence and use contingency time/scope cuts rather than proceeding on a broken step.

| Hour | Active prompt / milestone | A — Data/remote sensing | B — ML | C — Frontend | D — Backend/integration/pitch |
|---:|---|---|---|---|---|
| 0 | Phase 0 | Confirm region/source inputs. | Review constants and validation rules. | Confirm UXPilot export availability/location. | Confirm repository docs, MongoDB, and clean local run instructions. |
| 1 | P6 — Backend scaffold | Review collection/index assumptions. | Review health/error test cases. | Check frontend origin/CORS contract. | Implement app, settings, Motor lifecycle, health, CORS, requirements, and native service commands. |
| 2 | P7 — Auth | Review user fields and locales. | Review token expiry/security cases. | Confirm login response/UI needs. | Implement password/JWT services, routes, dependency, focused tests. |
| 3 | P8 — Schemas; checkpoint at H4 | Review field/season representations. | Review risk/confidence Literal values. | Check schemas match frontend needs. | Implement Pydantic v2 request/response schemas/examples; run schema checks. |
| 4 | P9 — Region/field reads | Review geometry and seedable records. | Define empty/stale-result edge cases. | Verify endpoint response shapes for map/detail. | Implement services, routes, projections, GeoJSON, queue, time series. |
| 5 | P10 — Actions/methodology | Check data ownership assumptions. | Check risk/methodology output. | Verify action/methodology UI response needs. | Implement endpoints and ownership validation. |
| 6 | P11 — Backend tests | Review fixture data validity. | Review pipeline-shaped fixtures. | Confirm frontend's expected error/empty behavior. | Add isolated async fixtures and route/action tests; run pytest. |
| 7 | P12 — Hardening; checkpoint at H8 | Review no-secret logging requirement. | Review rate-limit test boundaries. | Check CORS/error/401 client behavior. | Add structured request logs, login rate limit, error codes, demo-user script; acceptance. |
| 8 | P13 — Synthetic seed data | Lead 40-field synthetic geometry/NDVI/rainfall data and explicit flags. | Review synthetic stress mix and assessability. | Verify all needed UI states are represented. | Verify Mongo load and P9 fields endpoint returns expected feature count/risk mix. |
| 9 | P14 — Config/EE extraction; P15 — cleaning/time alignment (sequential within hour) | Lead config and extractor interface; keep secrets external. | Review cleaning fixtures and gap/spike cases. | Check synthetic/current fields for renderable quality flags. | Verify CLI/environment boundaries and acceptance commands. |
| 10 | P16 — Baseline/grouping; checkpoint at H12 | Review season/source alignment. | Lead leakage test, MAD/sigma floor, cluster fallback. | Confirm baseline fields match chart contract. | Review configuration provenance and stored parameter shape. |
| 11 | P17 — Scoring/persistence/onset | Review current-season observation selection. | Lead threshold/persistence/onset tests. | Review user-readable state mapping, no diagnosis language. | Check contract fields and error/no-data behavior. |
| 12 | P18 — Rain/confidence/advice | Check rainfall data availability/meaning. | Lead confidence/rain-context/advice rules and tests. | Check translation keys for advice and confidence. | Confirm outputs are compatible with API methodology. |
| 13 | P19 — Optional IF; P20 — validation (sequential) | Review baseline-only training input. | Lead optional cross-check, then validation procedures and report schema. | Check synthetic validation label in intended UI copy. | Confirm `validate.py` output is the sole source of metric values. |
| 14 | P21 — Orchestration/loading; checkpoint at H16 | Verify source files, field GeoJSON, run loading. | Verify real pipeline stages replace placeholder rules; run seeded fixture. | Confirm seeded API data will support planned pages. | Check idempotent load, latest successful run, skip-validation CLI. |
| 15 | P22 — Frontend scaffold | Review sample data/field rendering needs. | Verify risk vocabulary consistency. | Lead Vite/React/TypeScript/Tailwind/router/dependencies and design import. | Verify API base URL and local service ports. |
| 16 | P23 — API client/auth; P24 — i18n (sequential); checkpoint at H16 | Review `is_synthetic` propagation. | Review key coverage for risk states. | Lead client, auth context, locale resources and completeness test. | Verify auth/API integration and 401 handling. |
| 17 | P25 — App shell/dashboard | Verify labels/latest date. | Check risk totals and no fabricated KPIs. | Lead shell, dashboard queries, states, banner, top-fields panel. | Validate summary/queue endpoint fit. |
| 18 | P26 — Risk map | Review polygons and synthetic boundaries. | Check cannot-assess treatment. | Lead GeoJSON rendering, icon+label, legend, map interaction. | Verify seeded endpoint and map load timing method. |
| 19 | P27 — Field detail; P28 — queue/methodology; P29 — read-aloud/polish (sequential) | Check chart data availability/quality flags. | Check confidence/evidence interpretation. | Lead details, responsive queue, methodology, read-aloud/accessibility; D supports acceptance. |
| 20 | Feature freeze; P30 — end-to-end test begins | Freeze data behavior; provide reproducible seed/run ID. | Freeze scoring; supply measured validation output only. | Freeze UI scope; resolve only integration defects. | Lead E2E checklist/Playwright if feasible; checkpoint and feature freeze. |
| 21 | P30 complete; P31 — deployment | Verify load-to-Atlas instructions. | Review production configuration against analysis parameters. | Verify SPA route fallback/build config. | Complete E2E acceptance; add deployment files/docs and secrets scan. |
| 22 | P31 complete; P32 — demo/final docs | Confirm synthetic/real demo mode. | Provide validated numbers or explicit placeholders. | Verify Marathi read-aloud and fallback. | Draft demo script, Q&A, README updates, fallback plan. |
| 23 | P32 complete; rehearsal and contingency buffer | Rehearse data/run-status explanation. | Verify metrics shown exactly match output. | Rehearse user journey on target viewport. | Check commits, local stack, demo handoff, and record remaining issues. |

### Checkpoints

- **Hour 4:** P6–P8 acceptance passes; API boots, health/docs and CORS preflight work, auth/schema boundaries are testable.
- **Hour 8:** P9–P12 acceptance passes; protected reads/actions/methodology and route tests work; hardening does not break routes.
- **Hour 12:** P13–P16 accepted; synthetic data is clearly flagged; cleaning and baseline pass data-leakage/quality tests.
- **Hour 16:** P17–P21 accepted; scoring, context/confidence, validation, and orchestration run on seeded input; only emitted metrics are used.
- **Hour 20:** P22–P29 core acceptance passes; integration work starts and **feature freeze** begins. After this, implement no new features; fix release-blocking defects only.

## 5. Feature-freeze and scope-cut ladder

At Hour 20, no new product scope may be added. P30–P32 are integration, deployment, demo, and documentation; they may correct defects in the frozen scope but must not introduce new features.

If behind schedule, cut/defer in this order:

1. **Voice input** — already outside the planned MVP unless spare time remains.
2. **Hindi expansion/polish** — defer nonessential wording polish or additional Hindi coverage. **Do not remove the required Hindi locale, core labels, or essential safety copy**; `AGENTS.md` and P24 require `en`, `mr`, and `hi`.
3. **Isolation Forest** — skip optional cross-check; rule-based risk remains authoritative.
4. **K-means** — defer clustering if the required baseline and a safe assessability fallback still work; never silently substitute or fabricate baseline values.
5. **Rainfall context** — omit optional context when data are unavailable or time is short; identify it as unavailable, not zero.
6. **Login polish** — retain secure auth and acceptance tests; cut only visual refinements, not password/token security or auth routes.

The ladder does not permit cutting synthetic-data disclosure, `cannot_assess`, NaN handling, core field map/detail/queue, backend route tests, or the no-diagnosis language.

## 6. Definition of done by phase

| Phase | Prompts | Definition of done |
|---|---|---|
| 0 — Source and setup | Preparation | Root `AGENTS.md` and canonical architecture are available, MongoDB is reachable, and design source location is known. No code phase starts with missing source docs. |
| 1 — Backend | P6–P12 | Server, auth, schemas, required routes, error contract, hardening, and isolated route tests pass. No password hash, `_id`, token, or secret leakage. |
| 2 — Demo data | P13 | MongoDB contains the specified synthetic dataset and API returns 40 field features with risk-state mixture; synthetic marker is end-to-end visible. |
| 3 — Pipeline | P14–P21 | Config, processing stages, tests, validation, orchestration, and idempotent load work on fixtures; seeded injected stress is reproduced as watch/alert by real pipeline functions. |
| 4 — Frontend | P22–P29 | UXPilot design is imported; required routes, API/auth, map, field detail, queue, methodology, i18n, read-aloud fallback, accessibility, and data states are implemented and reviewed. |
| 5 — Integration/delivery | P30–P32 | E2E checklist is run and failures reported; deployment instructions/config are reviewed; no secrets are committed; demo/Q&A/README use only measured outputs or explicit placeholders. |

If any acceptance check fails, the prompt is not done; do not claim phase completion or continue to the next prompt.

## 7. Risk register

| Risk | Likelihood/impact | Mitigation and trigger |
|---|---|---|
| UXPilot design export is not ready at P22. | Medium / High | Confirm in Phase 0; request export/screens. Do not invent a replacement; if blocked, schedule and report the blocker. |
| Earth Engine service account/project or quotas fail. | Medium / High | Validate credentials before P14, keep secrets external, use synthetic fixtures for offline work, and do not claim live data success. |
| The referenced existing `ee_extract.py` is not supplied. | High / Medium | Ask for source before adapting; implement only a documented interface if authorized. |
| Synthetic stress outputs fail to produce required risk mix. | Medium / High | Test seed generation before integration; keep stress labels synthetic; replace P13 placeholder scoring at P21 and recheck API outputs. |
| Baseline leakage or insufficient years cause false assurance. | Medium / High | P16 leakage/fallback tests; include baseline years; use `cannot_assess` where required. |
| Frontend/API field or date mismatches delay integration. | Medium / High | P8 contract first; P13 seed data early; check P30 end-to-end with one shared fixture. |
| The 24-hour task load exceeds capacity. | High / High | Strict checkpoints and scope ladder; protect core safety/data handling; do not skip failed acceptance silently. |
| Feature freeze is violated by late scope requests. | Medium / Medium | Hour 20 freeze; only release-blocking defect fixes after it. |
| Real-world performance or validation is overclaimed. | Medium / High | Measure seeded map time; derive model metrics only from `validate.py`; use placeholders otherwise. |
| Secrets enter Git during local integration/deployment. | Low / Critical | `.gitignore`, environment-only secrets, pre-demo secret scan; stop release on any finding. |
| Local language/read-aloud support is inadequate on demo device. | Medium / Medium | Test target device/voices early; provide readable text fallback; have a human-reviewed Marathi/Hindi script. |

## 8. Pre-demo checklist

### Source and repository

- [ ] `AGENTS.md` and `docs/TECHNICAL_ARCHITECTURE.md` are present and used as context.
- [ ] Scope is frozen; all changes are requested and committed only after checks pass.
- [ ] No `.env`, service-account JSON, JWT secret, or other key is staged or tracked; scan repository/history as specified in P31.

### Data and pipeline

- [ ] Confirm the demo dataset is synthetic or observed; if synthetic, every related run/result is flagged and the UI banner is visible.
- [ ] Record region, season, latest run ID, and latest observation date.
- [ ] `cannot_assess` fields remain distinct from `normal`.
- [ ] Pipeline validation output is available; every displayed metric is copied from the run or remains a placeholder.
- [ ] Earth Engine is not required for the demo fallback; if live data is used, confirm a successful run and credentials are not exposed.

### Application and API

- [ ] MongoDB, backend, and frontend start with documented commands.
- [ ] `/api/health`, `/docs`, login, dashboard, field details, queue, actions, and methodology behave as expected.
- [ ] CORS preflight from the configured frontend origin succeeds.
- [ ] Test main journey: login → map → alert field → evidence chart → Marathi read-aloud → inspection action → methodology.
- [ ] Loading, empty, error, risk icon+label, synthetic banner, and `cannot_assess` states are checked.
- [ ] Mobile layout has no horizontal scrolling; keyboard focus and essential accessible names are checked.
- [ ] E2E results and unresolved failures are stated honestly.

### Demo and recovery

- [ ] Demo script uses placeholders for unmeasured numbers and carries the “unusual vegetation behaviour, inspect” framing.
- [ ] Seeded synthetic data can be reloaded and is labelled visibly.
- [ ] Recorded-video or screenshots fallback is ready if network/services fail.
- [ ] Judge Q&A covers plain NDVI comparison, model choice, clouds, causal limits, validation without ground truth, and limitations.
- [ ] Remaining known issues and deviations are disclosed; no incomplete item is described as completed.