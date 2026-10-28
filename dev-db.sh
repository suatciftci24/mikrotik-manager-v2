#!/usr/bin/env bash
# Explicit V2 development-cluster setup. Never manages system PostgreSQL services.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
V2_PG_BIN="/usr/lib/postgresql/16/bin"
V2_PG_DATA="$PROJECT_ROOT/.local/postgres-v2-demo"
V2_PG_SOCKET="$PROJECT_ROOT/.local/postgres-v2-socket"
# Validate the same strict destination and repo ownership before cluster setup.
PYTHONPATH="$PROJECT_ROOT/backend" "$PROJECT_ROOT/.venv/bin/python" - <<'PYVALIDATE'
from app.demo_repair import preflight
from app.core.database import engine
preflight(engine)
PYVALIDATE
mkdir -p "$PROJECT_ROOT/.local" "$V2_PG_SOCKET"
if "$V2_PG_BIN/pg_ctl" -D "$V2_PG_DATA" status >/dev/null 2>&1; then
  printf 'V2 development PostgreSQL already running on 127.0.0.1:55432.\n'
else
if "$V2_PG_BIN/pg_isready" -h 127.0.0.1 -p 55432 -t 2 >/dev/null 2>&1; then
  printf 'Port 55432 is occupied; no existing server was changed.\n' >&2
  exit 1
fi
if [[ ! -f "$V2_PG_DATA/PG_VERSION" ]]; then
  V2_PASSWORD_FILE="$(mktemp)"
  trap 'rm -f -- "$V2_PASSWORD_FILE"' EXIT
  printf 'v2_local\n' > "$V2_PASSWORD_FILE"
  "$V2_PG_BIN/initdb" -D "$V2_PG_DATA" -U v2_local --auth-local=scram-sha-256 --auth-host=scram-sha-256 --pwfile="$V2_PASSWORD_FILE" >/dev/null
fi
"$V2_PG_BIN/pg_ctl" -D "$V2_PG_DATA" -l "$PROJECT_ROOT/.local/postgres-v2.log" -o "-h 127.0.0.1 -p 55432 -k $V2_PG_SOCKET" -w start
fi
# A failed application login is not evidence that the DB is absent.
# Check the owned server directory first; never change roles/passwords or another cluster.
PYTHONPATH="$PROJECT_ROOT/backend" "$PROJECT_ROOT/.venv/bin/python" - <<'PYDATABASE'
from pathlib import Path
from sqlalchemy import create_engine, text
from app.core.database import engine
from app.demo_repair import ROOT, require
maintenance = create_engine(engine.url.set(database='postgres'), isolation_level='AUTOCOMMIT',
                            connect_args={'connect_timeout':3, 'options':'-c statement_timeout=5000'})
try:
    with maintenance.connect() as connection:
        directory=connection.execute(text('SHOW data_directory')).scalar_one()
        require(Path(directory).resolve()==(ROOT/'.local/postgres-v2-demo').resolve(),
                'Port 55432 bu deponun V2 kümesine ait değil; DB oluşturulmadı.')
        exists=connection.execute(text('SELECT 1 FROM pg_database WHERE datname=:name'),
                                  {'name':'mikrotik_manager_v2'}).scalar_one_or_none()
        if exists is None:
            connection.execute(text('CREATE DATABASE mikrotik_manager_v2 OWNER v2_local'))
finally:
    maintenance.dispose()
PYDATABASE
printf 'V2 development database ready; apply the explicit demo schema setup separately.\n'
