#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# One Vite entrypoint shared by normal dev and the browser acceptance manager.
if [[ "${1:-}" == '--ui-only' ]]; then
  [[ $# -eq 1 && -f frontend/node_modules/vite/bin/vite.js ]] || { printf 'UI BLOCKED: Vite eksik veya argüman geçersiz.\n' >&2; exit 1; }
  cd "$PROJECT_ROOT/frontend"
  # exec Node directly so the owned PID is Vite, not an npm wrapper with an orphan child.
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1
fi

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
if [[ "${1:-}" == '--refresh-owned' ]]; then
  [[ $# -eq 1 ]] || { printf 'Geçersiz refresh argümanı.\n' >&2; exit 1; }
  PYTHONPATH=backend .venv/bin/python -m app.local_refresh
elif [[ $# -ne 0 ]]; then
  printf 'Geçersiz dev.sh argümanı.\n' >&2; exit 1
fi
# Normal dev and acceptance share the same ownership/readiness/log lifecycle.
export PYTHONPATH="$PROJECT_ROOT/backend"
exec .venv/bin/python -m app.demo_api_runner --dev
