#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backend="$repo_root/backend"
ml_service="$repo_root/ml-service"
frontend="$repo_root/frontend"

for python in "$backend/.venv/bin/python" "$ml_service/.venv/bin/python"; do
    if [ ! -x "$python" ]; then
        printf 'Missing component virtual environment interpreter: %s\nFollow docs/LOCAL_SETUP.md first.\n' "$python" >&2
        exit 1
    fi
done
if [ ! -d "$frontend/node_modules" ]; then
    printf 'Missing frontend dependencies. Run npm ci in frontend/ first.\n' >&2
    exit 1
fi

export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"
children=""
stop_children() {
    for pid in $children; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap stop_children EXIT INT TERM

(cd "$backend" && .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
children="$children $!"
(cd "$ml_service" && .venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001) &
children="$children $!"
(cd "$frontend" && npm run dev -- --host 127.0.0.1) &
children="$children $!"

printf 'Backend: http://127.0.0.1:8000\nML service: http://127.0.0.1:8001\nFrontend: http://127.0.0.1:5173\n'
wait
