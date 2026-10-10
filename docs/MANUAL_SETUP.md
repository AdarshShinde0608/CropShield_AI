# Manual setup

Use this checklist when setting up CropShield AI without the helper scripts.
For full commands, see [LOCAL_SETUP.md](./LOCAL_SETUP.md).

1. Install Python 3.11.11, Node.js/npm, Git, and either local MongoDB or create
   a dedicated non-production MongoDB Atlas database.
2. From the repository root, create `backend/.venv`, `ml-service/.venv`, and
   `pipeline/.venv`; install each component's pinned requirements file using
   its own interpreter.
3. Run `npm ci` in `frontend/`.
4. Copy each required `.env.example` to the same component's ignored `.env`.
   Configure separate development credentials and make the backend and
   optional ML service use the same local-only ML key.
5. Start backend, ML service, and frontend in separate terminals, using the
   component working directories and commands in `LOCAL_SETUP.md`.
6. Confirm backend `/api/health` and ML `/health`. ML `/ready` is expected to
   remain unavailable unless a verified supported model artifact is present.
7. For tests requiring real MongoDB, provide a disposable `MONGODB_TEST_URI`.
   Those tests use a unique test database and skip clearly when it is unset.
8. Run the frontend's typecheck, locale tests, build, and Playwright checks
   from `frontend/`; run Python tests from each component directory.

Never configure production Atlas credentials in a local `.env`, use a
production database for tests, or place secrets in frontend variables.
