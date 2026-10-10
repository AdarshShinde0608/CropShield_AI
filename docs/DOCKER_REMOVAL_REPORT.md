# Container workflow removal audit

**Status:** audit recorded before any container-specific file deletion.  
**Scope:** active project files outside the protected `cropshield-ai/` tree.
The protected tree and its archive are preserved unchanged.

## Inventory and replacements

| Location | Audit hit | Replacement or disposition |
|---|---|---|
| `.dockerignore` | Build-context ignore file | Remove after native setup and Render configuration are in place. |
| `docker-compose.yml` | Local database and service orchestration | Remove; document local MongoDB or an isolated Atlas development database, and add `scripts/dev.ps1` / `scripts/dev.sh` for the three application processes. |
| `backend/Dockerfile` | Backend image definition | Remove; Render runs the backend with its native Python build and start commands. |
| `ml-service/Dockerfile` | ML service image, health check, and model-copy steps | Remove; Render runs the service natively. Install only its requirements and shared core; fetch a model artifact only during build when a URL and both checksum checks are configured. |
| `render.yaml` | Docker runtimes, image paths/contexts, image-based model directory | Replace with two native Python web services in the same region, explicit Python version, build/start commands, health checks, and secret environment entries. |
| `README.md` | Compose-based MongoDB startup | Replace with native local setup instructions and links to setup/deployment guidance. |
| `01_architecture_and_file_structure.md` | Legacy structure lists Compose and service image files | Update the structure entries to native local setup scripts and Render services. |
| `docs/TECHNICAL_ARCHITECTURE.md` | Legacy tree, image-baked artifact language, and image-footprint planning | Update the repository/deployment model to native Python, build-time artifact verification, and measured runtime limits. |
| `docs/DEPLOYMENT.md` | Image build fields, image deployment procedure, old plan assumptions | Rewrite for Render native Python, Vercel, Atlas, build-time artifact fetching, model activation, rollback, and key rotation. |
| `docs/ML_SERVICE_CONTRACT.md` | Image-owned model paths, Compose profile, image measurements | Rewrite for the native service filesystem and its startup checksum gate; note that the current checkout has no artifact/runtime and remains unready. |
| `docs/E2E_CHECKLIST.md` | Previous full-stack launch command and image measurements | Replace with the PowerShell/shell local-process launcher and exact native-process test limitations. |
| `docs/SUSTAINABILITY.md` | Generic image/runtime measurement references | Use measured native service memory, startup, and latency only; preserve the explicit unknown status. |
| `docs/SECURITY_REVIEW.md` | Prior full-stack launch and image-size language | Update to native build/run controls and preserve the actual unverified status. |
| `docs/FINAL_STATUS.md` | Prior launch command and image-size result | Replace with native setup verification status and explicitly unmeasured native build/start/model metrics. |
| `docs/RELEASE_CHECKLIST.md` | Compose integration gate and image sizing | Replace with native local-process and Render build/start gates. |
| `docs/CLEANUP_REPORT.md` | Historical Compose attempt | Retain the historical result in revised terms; do not remove this document. |
| `docs/MODEL_TEST_REPORT.md` | Frozen performance criterion and prior image-run blockers | Preserve approved criteria and test outcomes, but describe the target as Render's native Python service and update unrun-command wording. |
| `docs/IMPLEMENTATION_PLAN.md` | Historical mention of service image work | Replace the stale task description with native service setup. |
| `frontend/src/styles/index.css` and Playwright E2E specs | Leaflet's `.leaflet-container` CSS class | False positive, not an infrastructure reference; preserve the library selector unchanged. |
| `frontend/package.json`, Playwright configuration, CI configuration | No container configuration found in the audited active files | Keep existing package scripts and Playwright's Vite server. Update E2E documentation to state that the API and ML service must be started separately. No CI service container configuration was found. |
| `cropshield-ai/docker-compose.yml` and other protected legacy content | Protected source tree is excluded from modification and deletion; content search returned no text matches in its files | Preserve unchanged. The filename remains an explicit exception to the active-project removal scope until migration is independently verified. |

## Audit method

Searched first-party source, documentation, configuration, setup, and test
files for container workflow terms and enumerated infrastructure filenames.
Dependency/build directories were not included. The text search also surfaced
the Leaflet CSS class in source and E2E tests; those are UI selectors, not
infrastructure. The protected reference tree was searched read-only and had no
text-content matches; its Compose filename was found during path enumeration.

The initial audit found these active infrastructure filenames: `.dockerignore`,
root `docker-compose.yml`, `backend/Dockerfile`, and `ml-service/Dockerfile`.
The native migration removes only those files after their replacements are
documented and added. It does not remove or alter `cropshield-ai/`, model files,
tests, lockfiles, environment examples, or any document.

## Native runtime constraints

- Render service definitions must use native Python web services in one region,
  no `rootDir`, an explicit `PYTHON_VERSION`, `buildCommand`,
  `startCommand`, and `healthCheckPath`. Both services use the Free plan unless
  measured evidence requires otherwise.
- The backend's requirements do not install the pipeline, shared core, or
  model runtime. The ML service installs the shared core by its repository-root
  package path.
- Build-time model retrieval is permitted only over HTTPS with a pinned
  artifact SHA-256, safe archive extraction, and per-file checksum verification
  against the model card. The service itself never downloads or loads artifacts
  from request data or the network.
- No maintained model artifact is currently present. An unconfigured fetch
  therefore leaves the service unready; no URL, checksum, artifact, or measured
  result is invented to make deployment appear successful.
- A final search must permit this report and the explicitly approved policy
  sentence in `AGENTS.md` to name the removed technology. It must also report
  the protected legacy filename and unrelated Leaflet selector rather than
  changing protected or functional source to eliminate textual matches.
