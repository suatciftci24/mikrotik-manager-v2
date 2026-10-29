#!/usr/bin/env bash
# Explicit local-only schema setup + isolated PostgreSQL acceptance. No live adapters.
set -euo pipefail
V2_SUBSCRIBER_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_SUBSCRIBER_ROOT"
export PYTHONPATH="$V2_SUBSCRIBER_ROOT/backend"
.venv/bin/python - <<'PY'
from app.demo_repair import preflight,socket_permission
from app.core.database import engine
preflight(engine)
socket_permission()
PY
./dev-db.sh
.venv/bin/python -m app.local_router_workspace --apply
.venv/bin/python -m app.local_subscriber_workspace --apply
V2_RUN_SUBSCRIBER_PG_TESTS=1 .venv/bin/python -m unittest discover -s backend/tests -p 'test_subscriber_workspace_postgres.py' -v
