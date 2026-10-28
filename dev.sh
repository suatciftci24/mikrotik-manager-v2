#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Explicit acceptance bootstrap: no install, schema/seed or UI startup required.
if [[ "${1:-}" == '--accept-demo' ]]; then
  [[ -x .venv/bin/python ]] || { printf 'BLOCKED: V2 .venv eksik.\n' >&2; exit 1; }
  export PYTHONPATH="$PROJECT_ROOT/backend"
  shift
  exec .venv/bin/python -m app.demo_api_runner "$@"
fi

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
  PYTHONPATH=backend .venv/bin/python -m app.demo_storage init --examples
  exit 0
fi
if [[ -L "$PROJECT_ROOT/.local" || -L "$PROJECT_ROOT/.local/runtime" ]]; then
  printf 'BLOCKED: V2 log yolu symlink olamaz.\n' >&2
  exit 1
fi
mkdir -p "$PROJECT_ROOT/.local/runtime"
RUNTIME_DIR="$(mktemp -d "$PROJECT_ROOT/.local/runtime/dev.XXXXXX")"
API_PID=""
WEB_PID=""
cleanup() {
  [[ -z "$WEB_PID" ]] || kill "$WEB_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
  [[ -z "$WEB_PID" ]] || wait "$WEB_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || wait "$API_PID" 2>/dev/null || true
  printf "V2 başlangıç logları korundu: %s\n" "$RUNTIME_DIR" >&2
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 >"$RUNTIME_DIR/api.log" 2>&1 &
API_PID=$!
npm --prefix frontend run dev -- --host 127.0.0.1 >"$RUNTIME_DIR/web.log" 2>&1 &
WEB_PID=$!
if ! PYTHONPATH=backend .venv/bin/python -m app.demo_readiness --wait --pid "$API_PID"; then
  printf 'V2 API hazır değil. Log: %s/api.log; UI logu: %s/web.log\n' "$RUNTIME_DIR" "$RUNTIME_DIR" >&2
  exit 1
fi
if ! kill -0 "$WEB_PID" 2>/dev/null; then
  printf 'V2 UI başlatılamadı; API bu dev.sh oturumu ile durdurulacak. Log: %s/web.log\n' "$RUNTIME_DIR" >&2
  exit 1
fi
printf '\nMikroTik Manager V2 local demo\n  UI:      http://127.0.0.1:5173\n  API:     http://127.0.0.1:8000/api/docs\n  Login:   demo / demo-only\n  Stop:    Ctrl+C\n\nOnly local synthetic data is enabled; demo persistence uses isolated local V2 PostgreSQL. No router, RADIUS, or V1 connection is started.\n\n'
if wait -n "$API_PID" "$WEB_PID"; then
  printf 'Bir V2 geliştirme süreci kapandı; bu oturumun diğer süreci durduruluyor. Log: %s\n' "$RUNTIME_DIR" >&2
else
  status=$?
  printf 'V2 süreç başlangıç/çalışma hatası (kod %s). Loglar: %s\n' "$status" "$RUNTIME_DIR" >&2
  exit "$status"
fi
