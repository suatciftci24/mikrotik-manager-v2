#!/usr/bin/env bash
# Explicit local V2 migration + isolated PostgreSQL acceptance. Never device IO.
set -euo pipefail
V2_REGISTRY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_REGISTRY_ROOT"
export PYTHONPATH="$V2_REGISTRY_ROOT/backend"
.venv/bin/python - <<'PY'
from app.demo_repair import socket_permission, preflight
from app.core.database import engine
preflight(engine)
socket_permission()
PY
./dev-db.sh
.venv/bin/python -m app.local_router_registry --apply
V2_RUN_REGISTRY_PG_TESTS=1 .venv/bin/python -m unittest discover -s backend/tests -p 'test_router_registry_postgres.py' -v
