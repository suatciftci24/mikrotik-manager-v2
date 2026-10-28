#!/usr/bin/env bash
# Explicit repair of the repo-owned V2 synthetic database; never runs on app startup.
set -euo pipefail
V2_REPAIR_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_REPAIR_ROOT"
if [[ ! -x .venv/bin/python ]]; then
  printf 'BLOCKED: V2 .venv eksik; otomatik paket kurulumu yapılmadı.\n' >&2
  exit 1
fi
export PYTHONPATH="$V2_REPAIR_ROOT/backend"
exec .venv/bin/python -m app.demo_repair "$@"
