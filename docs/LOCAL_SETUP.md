# Local development setup

CropShield AI runs as three local application processes: the FastAPI backend,
the optional ML service, and the Vite frontend. The analysis pipeline runs
separately as an offline command. MongoDB is provided either by a local
installation or a dedicated development database in MongoDB Atlas.

## Prerequisites

- Python 3.11.11 (the version in `.python-version`).
- Node.js and npm compatible with the versions in `frontend/package-lock.json`.
- A local MongoDB server, or a separate Atlas development database and URI.
- Git.

Never use a production MongoDB URI for local development or tests. Do not put
credentials in frontend environment variables.

## Python environments and frontend dependencies

Create an independent virtual environment for each Python component. Run
dependency installation from the repository root because the ML-service lock
installs the shared core by its repository-root path.

### Windows PowerShell

```powershell
py -3.11 -m venv backend\.venv
py -3.11 -m venv ml-service\.venv
py -3.11 -m venv pipeline\.venv
backend\.venv\Scripts\python.exe -m pip install --require-hashes -r backend\requirements.txt
ml-service\.venv\Scripts\python.exe -m pip install -r ml-service\requirements.txt
pipeline\.venv\Scripts\python.exe -m pip install --require-hashes -r pipeline\requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

### macOS or Linux

```sh
python3.11 -m venv backend/.venv
python3.11 -m venv ml-service/.venv
python3.11 -m venv pipeline/.venv
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements.txt
ml-service/.venv/bin/python -m pip install -r ml-service/requirements.txt
pipeline/.venv/bin/python -m pip install --require-hashes -r pipeline/requirements.txt
(cd frontend && npm ci)
```

The lock files are pinned for Python 3.11. Recompile them from the adjacent
`.in` input files only when intentionally changing dependencies, then review
the complete lock diff and rerun component tests.

## MongoDB configuration

For local MongoDB, install and start MongoDB Community Server for your
operating system, then confirm it listens at `mongodb://localhost:27017`.
Alternatively, create a separate Atlas development database and add only your
current development IP to its access list.

Copy each applicable `.env.example` to `.env` in its component directory:

- `backend/.env`: set `MONGODB_URI`, a development-only `MONGODB_DB`, a unique
  `JWT_SECRET` of at least 32 bytes, and local `CORS_ORIGINS`.
- `ml-service/.env`: use the same development database URI/name, a local-only
  ML API key of at least 32 bytes, and `MODEL_DIR=../models`.
- `frontend/.env`: set `VITE_API_BASE_URL=http://localhost:8000/api`.
- `pipeline/.env`: configure Earth Engine and MongoDB only if running the
  offline pipeline.

Set the same local-only ML API key in the backend and ML service `.env` files.
Do not reuse any production secret. The current checkout has no approved model
artifact; the ML service can start, but `/ready` and live model scoring remain
unavailable until a verified supported artifact is supplied.

## Start and test the local processes

After environment setup, from the repository root run:

```powershell
.\scripts\dev.ps1
```

or:

```sh
sh ./scripts/dev.sh
```

The scripts start backend on `http://127.0.0.1:8000`, ML service on
`http://127.0.0.1:8001`, and Vite on `http://127.0.0.1:5173`. Stop the
processes started by the shell script with Ctrl+C. The PowerShell script opens
separate process windows; close those windows to stop them. Playwright starts
Vite itself; start the API and ML service separately before running
end-to-end tests.

## Test database isolation

Unit and route tests use in-memory MongoDB doubles by default. Any test that
needs a real MongoDB server must use `MONGODB_TEST_URI` and a unique
`cropshield_test_<random-id>` database, never `MONGODB_URI` or the configured
application database. The backend's `mongodb_test_database` fixture skips
with a clear message when `MONGODB_TEST_URI` is unset and drops only its
uniquely named test database when finished. Keep the URI in the test process
environment, not in a committed file.

## Offline pipeline

Run pipeline tests from the repository root with
`pipeline/.venv/Scripts/python.exe -m pytest pipeline/tests` on Windows or
`pipeline/.venv/bin/python -m pytest pipeline/tests` on macOS/Linux. Activate
`pipeline/.venv` and run pipeline jobs only against deliberate input data and a
non-production database. Earth Engine credentials must remain outside Git and
outside the backend/ML service. Synthetic seed data must remain marked
`is_synthetic=true`; it is not validation evidence.
