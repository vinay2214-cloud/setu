#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
if [ ! -x backend/.venv/bin/python ]; then
  PYTHON_BIN="${PYTHON_BIN:-python3.11}"
  "$PYTHON_BIN" -m venv backend/.venv
  backend/.venv/bin/python -m pip install -r backend/requirements.lock
fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm ci); fi
export DEMO_AUTO_SEED="${DEMO_AUTO_SEED:-true}"
(cd backend && exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!
(cd frontend && exec npm run dev -- --hostname 127.0.0.1 --port 3000) &
WEB_PID=$!
trap 'kill "$API_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
for attempt in $(seq 1 90); do
  if curl --silent --fail http://127.0.0.1:8000/health >/dev/null; then break; fi
  if ! kill -0 "$API_PID" 2>/dev/null; then printf 'API startup failed. Check the output above.\n' >&2; exit 1; fi
  sleep 1
done
if ! curl --silent --fail http://127.0.0.1:8000/health >/dev/null; then printf 'API did not become ready within 90 seconds.\n' >&2; exit 1; fi
printf 'Setu: http://localhost:3000 · demo account dr.anitha@demo.setu / demo123\n'
wait "$API_PID" "$WEB_PID"
