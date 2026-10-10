# Repository cleanup report

## P37 — protected model-folder rule (supersedes earlier cleanup candidates)

`cropshield-ai/` is now a protected path under `AGENTS.md`. No task may delete,
move, rename, clean, prune, or otherwise modify any part of that folder,
including local/generated artifacts, until the user explicitly confirms that
the model migration is verified. This later rule supersedes the earlier P33
audit dispositions and cleanup scope for the nested reference project. Do not
use the historical Batch 1 entry below as authorization for additional
changes. This P37 audit inspected the folder read-only.

## Stage 1 — audit only

**Checkpoint:** The project state was committed before this audit as
`5a05e1c` (`Checkpoint CropShield AI before cleanup`). Unrelated pending work in
sibling directories of the parent Git repository was not included in that
commit.

No files or directories have been removed in Stage 1.

### Nested and reference projects

| Candidate | Evidence and reason | Disposition |
|---|---|---|
| `cropshield-ai/` | Nested reference implementation contains its own backend, frontend, ML model, scripts, legacy local setup, and dependencies; it is not one of this project's three runtime components. | P37 protection supersedes the former removal disposition: preserve the entire folder until migration verification is explicitly confirmed by the user. See `docs/MODEL_AUDIT.md`. |
| `cropshield-ai.zip` | Packaged duplicate of the nested reference project; the unpacked directory is present too. | Removed. |
| `01_architecture_and_file_structure.md` | Standalone architecture document at project root. | Keep: documents are explicitly out of cleanup scope. |

### Generated or local artifacts

| Candidate | Evidence and reason | Disposition |
|---|---|---|
| Root `.venv/`, frontend `node_modules/` | Local Python and Node environments required to run the requested test matrix in this workspace. | Kept locally; ignored by Git. |
| `frontend/dist/`, pytest caches, Python bytecode | Generated as part of build/test verification. | Ignored by Git; the frontend build regenerates `dist/` and tests may regenerate caches. |
| Nested reference `backend/venv/`, `ml/venv/`, `__pycache__/` directories | Local environments/caches belonging only to the removed reference implementation. | Removed in Stage 2. |
| `frontend/tsconfig.tsbuildinfo` | Tracked TypeScript incremental-build metadata (confirmed by `git ls-files`). | Removed from version control in Stage 2; build may regenerate it locally, now covered by `*.tsbuildinfo`. |
| `*.pyc`, `__pycache__/`, `.DS_Store`, `*.log`, `.ruff_cache/`, `build/`, `coverage/`, `playwright-report/`, `test-results/` | Generated/local artifact classes requested for audit. | Added/confirmed ignore rules in Stage 3. |
| Root `package-lock.json` | Empty lockfile with no root `package.json`. | Keep: lockfiles are explicitly protected. |

### Unused source and dependencies

No source files, exports, API modules, schemas, services, routes, UI components,
hooks, or locale entries were proven unused, so none are proposed for removal.
The backend and pipeline import scan found their implementation modules wired
into route/service/orchestration code and tests. The frontend is strict
TypeScript with `noUnusedLocals` and `noUnusedParameters`; its production build
and locale-key parity check passed before this audit. The English, Marathi, and
Hindi locale files each contain 174 matching keys. Every declared runtime npm
dependency has corresponding imports in `frontend/src`; Python runtime packages
are referenced by the pipeline or backend imports. These checks are conservative:
absence of a textual match alone is not treated as proof of dead code.

**Disposition:** keep source and dependencies; do not infer unused files or
dependencies from names alone.

### Dead code, placeholders, duplicate scripts, and empty files

| Candidate | Evidence and reason | Disposition |
|---|---|---|
| Legacy placeholder scoring in `pipeline/seed_demo.py` | Search for `TODO`, `FIXME`, `placeholder_rule`, and placeholder scoring found no placeholder scorer in the seeder. The only `placeholder_rule` occurrence is a test assertion checking it is absent. | Keep `seed_demo.py` and its regression assertion. |
| Commented-out blocks / TODO placeholders in maintained source | The targeted Python/TypeScript source search found no such blocks or actionable TODO placeholders. | No proven dead-code removal candidate. |
| Duplicate scripts | No duplicate maintained project script was proven by name or use. The nested reference has its own scripts, which are part of the non-protected reference implementation candidate above. | Do not remove maintained scripts. |
| Empty tracked files | A zero-byte check over tracked project files found none. | None. |

### Stale pipeline data

`pipeline/data/raw/` and `pipeline/data/processed/` exist as directory structure;
the audit found no files within them and no tracked data outputs. CSV, JSON, or
GeoJSON run outputs, if created later, are regenerable and should not be
committed. Keep the two directories represented by `.gitkeep` files.

### Raw design exports

There is no `frontend/design/` directory. The root `Frontend_Reference/`
directory contains seven PNG image exports and no design notes. These are
retained visual references, not runtime assets imported by the frontend.

**Disposition:** moved all seven PNGs unchanged to `docs/design/`, preserving
their filenames. No existing documentation was removed.

### Validation baseline and blockers

- Initial backend baseline: 49 passed, 2 failed; both failures were seeded
  document serialization/risk-mix regressions.
- Initial pipeline baseline: 19 passed, 5 failed; failures covered confidence,
  severity threshold precision, interpolated gaps, current-season observation
  generation, and non-finite rainfall features.
- The declared pipeline requirements were installed in the workspace `.venv`;
  the failures were repaired without changing tests. Repairs include BSON-safe
  date serialization, the current-season observation variable-shadowing fix,
  null normalization for non-finite rainfall, confidence/assessability fixes,
  threshold precision handling, and an interpolated-gap scoring fix. The
  deterministic synthetic seed was adjusted to preserve the existing expected
  risk mix.
- A local MongoDB-backed end-to-end run was not available because no local
  MongoDB listener was present; use the documented native process launcher and
  isolated test database for a future run.

After these repairs, the complete required validation matrix passed before
cleanup began: backend pytest 51 passed, pipeline pytest 24 passed, frontend
typecheck passed, locale parity passed with 174 keys per language, and frontend
build passed.

## Stage 2 — removal log

| Batch | Candidate changes | Backend pytest | Pipeline pytest | Frontend typecheck | i18n | Frontend build | Outcome |
|---|---|---|---|---|---|---|---|
| Baseline after repairs | None | 51 passed | 24 passed | Passed | Passed (174 keys) | Passed | Clean baseline established |
| Batch 1 (historical P33 record; superseded for future work) | Earlier cleanup record proposed/removes non-protected files from `cropshield-ai/` and `cropshield-ai.zip`; moved seven PNGs to `docs/design/` | 51 passed | 24 passed | Passed | Passed (174 keys) | Passed | Historical only; P37 forbids further changes within `cropshield-ai/` |
| Batch 2 | Removed tracked `frontend/tsconfig.tsbuildinfo` and seven nested reference venv/cache directories; expanded build-artifact ignore rules | 51 passed | 24 passed | Passed | Passed (174 keys) | Passed | Retained |

The current reference/model tree is protected in its entirety by P37. The
separate archive is not inside that folder; no archive operation is part of P37.
The local ignored `cropshield-ai/backend/.env` was not read, deleted, or
modified. Root `.venv/` and frontend `node_modules/` were kept locally to
support the required test matrix. Build and test commands can recreate ignored
artifacts.

## Stage 3 — final inventory and secret scan

Updated `.gitignore` for OS metadata, logs, Python/Node environments and
caches, test/build outputs, all TypeScript build metadata, and regenerable
raw/processed pipeline data. Added `pipeline/data/raw/.gitkeep` and
`pipeline/data/processed/.gitkeep` to preserve the empty data directory
structure. The obsolete tracked TypeScript build-info file was removed.

Secret scan findings (paths/categories only; values were not printed):

- The Git history scan found no committed non-example `.env` path and no
  `secrets/*.json` key/credential filenames.
- No Atlas credential URI or private-key PEM marker was found in history or in
  the current project-tree pattern scan. `JWT_SECRET` pattern hits are variable,
  documentation/example, configuration, or test-fixture references across
  `01_architecture_and_file_structure.md`, `backend/.env.example`,
  `backend/app/core/config.py`, `backend/tests/test_app.py`, and
  `docs/TECHNICAL_ARCHITECTURE.md`; no production credential value was printed
  or identified by the scan.
- The local ignored `cropshield-ai/backend/.env` remains present. Its contents
  were not displayed or changed; the limited pattern scan did not match Atlas
  credentials, private-key markers, or a literal `JWT_SECRET` assignment.
- This scan covered the available Git history and known working tree, using the
  specified credential patterns. It is not proof that credentials never
  existed outside that history or under an unscanned format.

## P54 release audit addendum

The user confirmed authorization to remove the protected model source only
after migration verification. The current maintained-path inventory does not
meet that condition: `models/` contains only `.gitkeep`, and no
`pipeline/model_runtime/` files are present. Required model weights, runtime,
licence, and attribution were therefore not verified in maintained paths.
`cropshield-ai/` was not inspected or modified and remains untouched. No
deletion batch was made in this release task; no source was proven unused.

Validation after the P53 test changes:

- Backend: 63 passed.
- ML service/parity: 39 passed; parity uses a test-only estimator.
- Shared core: 15 passed.
- Pipeline: 37 passed.
- Frontend typecheck and production build passed; locale parity passed with 208
  keys in each of en, mr, and hi.
- Focused mocked ML UI Playwright file: 10 passed.
- Full Playwright suite: 10 passed, 1 failed at the live registration step
  because backend validation rejected the reserved `.test` email domain. The
  fixture was changed to `.com`, the Marathi action/menu selectors were
  narrowed, and the live journey then passed alone. The combined suite was not
  rerun after these fixes. The local `/api/health` probe returned HTTP 200, but
  MongoDB was not listening on local port 27017.
- The diagnostic live journey created several generated user records and at
  least two inspection actions in the API's configured database. Its target was
  not verified and those records were not deleted; check the configured
  disposable database before the next live run.
- The local database-backed launch was not completed; no database service was
  listening on the expected local port.
  The local port 27017 check returned false.

The current working-tree/history secret-pattern scan excluded the protected
reference tree, dependency/build outputs, and binary files. It found no
private-key marker, AWS/GitHub token format, or credentialed MongoDB URI. A
broad literal-assignment heuristic flagged two lines in backend test files;
values were not printed, and the scan did not classify them as production
credentials. This pattern scan is limited and is not proof that no secret has
ever existed.

Disposition: preserve protected and ambiguous paths. Revisit model-source
cleanup only after the required model/runtime/licence/attribution migration is
actually present and verified.

One pipeline test symbolically constructs the protected path to assert that
the exporter refuses protected model sources; it does not load or read model
files from that tree. No tested runtime imports or loads from the protected
path.
