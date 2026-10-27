#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi, sqlalchemy, psycopg, uvicorn' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
if [[ ! -x frontend/node_modules/.bin/vite ]]; then
  npm --prefix frontend install
fi

export V2_DATABASE_URL="${V2_DATABASE_URL:-postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2}"
# Explicit maintenance mode; normal UI/API startup never applies migrations.
if [[ "${1:-}" == '--prepare-demo' ]]; then
  ./dev-db.sh
  PYTHONPATH=backend .venv/bin/python -m app.demo_storage init
  exit 0
fi
RUNTIME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mikrotik-manager-v2.XXXXXX")"
API_PID=""
WEB_PID=""
cleanup() {
  [[ -z "$WEB_PID" ]] || kill "$WEB_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
  [[ -z "$WEB_PID" ]] || wait "$WEB_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || wait "$API_PID" 2>/dev/null || true
  rm -rf -- "$RUNTIME_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 >"$RUNTIME_DIR/api.log" 2>&1 &
API_PID=$!
npm --prefix frontend run dev -- --host 127.0.0.1 >"$RUNTIME_DIR/web.log" 2>&1 &
WEB_PID=$!
printf '\nMikroTik Manager V2 local demo\n  UI:      http://127.0.0.1:5173\n  API:     http://127.0.0.1:8000/api/docs\n  Login:   demo@local.test / demo-only\n  Stop:    Ctrl+C\n\nOnly local synthetic data is enabled; demo persistence uses isolated local V2 PostgreSQL. No router, RADIUS, or V1 connection is started.\n\n'
wait -n "$API_PID" "$WEB_PID"
