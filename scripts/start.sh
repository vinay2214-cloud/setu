#!/usr/bin/env bash
set -euo pipefail
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 &
API_PID=$!
cd /app/frontend
PORT="${PORT:-10000}" HOSTNAME=0.0.0.0 node server.js &
WEB_PID=$!
trap 'kill "$API_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
wait -n "$API_PID" "$WEB_PID"
