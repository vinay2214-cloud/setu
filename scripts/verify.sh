#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR/backend"
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts
LLM_PROVIDER=mock .venv/bin/python -m pytest -q
.venv/bin/python ../seed/rules/reference_engine.py
LLM_PROVIDER=mock .venv/bin/python scripts/eval_intents.py
.venv/bin/python scripts/export_openapi.py
cd "$ROOT_DIR/frontend"
npm run openapi:types
npx tsc --noEmit
npm run lint
npm run build
