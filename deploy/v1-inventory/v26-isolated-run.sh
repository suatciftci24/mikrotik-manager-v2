#!/usr/bin/env bash
set -euo pipefail

ROOT=/tmp/mikrotik-v26-acceptance
PORT=18996

if [[ "$(pwd -P)" != "$ROOT" ]]; then
  echo "BLOCKED: Wrong working directory"
  exit 1
fi

if [[ -z "${V2_DATABASE_URL:-}" ]]; then
  echo "BLOCKED: Isolated database URL required"
  exit 1
fi

# Fail closed before launching any process.
if [[ -L "$ROOT" ]]; then
  echo "BLOCKED: Symlink root"
  exit 1
fi


if [[ "${V2_DATABASE_URL}" != postgresql+psycopg://v26_acceptance:*@127.0.0.1:55433/mikrotik_v26_acceptance ]]; then
  echo "BLOCKED: Non-isolated database"
  exit 1
fi

export V2_DEPLOYMENT_PROFILE=v26-isolated-acceptance
export V2_ENVIRONMENT=v26-acceptance
export V2_API_HOST=127.0.0.1
export V2_API_PORT="$PORT"
export V2_ROUTER_ONBOARDING_ENABLED=false
export V2_CEBECI_API_SSL_ENABLED=false
export V2_ROUTER_ONBOARDING_OPERATOR_IDS=

PYTHONPATH="$ROOT/backend" python3 - <<'CHECK'
from pathlib import Path
from app.core.v26_acceptance import validate
validate(root=Path.cwd())
print("PASS: Isolated runtime preflight")
CHECK

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting isolated V2.6 acceptance on 127.0.0.1:$PORT"
PYTHONPATH="$ROOT/backend" python3 -m uvicorn app.pilot_panel:create_app \
  --factory --host 127.0.0.1 --port "$PORT" --no-access-log --no-proxy-headers &
SERVER_PID=$!

wait "$SERVER_PID"
