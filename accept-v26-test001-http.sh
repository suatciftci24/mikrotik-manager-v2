#!/usr/bin/env bash
# Ev WSL terminal only. No sudo, dotenv, existing DB, service management or devices.
set -euo pipefail
V26_ACCEPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V26_ACCEPT_ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo 'BLOCKED: repo .venv/bin/python missing; install local backend dependencies'
  exit 1
fi
export PYTHONPATH="$V26_ACCEPT_ROOT:$V26_ACCEPT_ROOT/backend:$V26_ACCEPT_ROOT/backend/tests"
export PYTHONNOUSERSITE=1
exec .venv/bin/python -m backend.tests.v26_test001_http --run
