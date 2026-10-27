#!/usr/bin/env bash
# Explicit V2 development-cluster setup. Never manages system PostgreSQL services.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
V2_PG_BIN="/usr/lib/postgresql/16/bin"
V2_PG_DATA="$PROJECT_ROOT/.local/postgres-v2-demo"
V2_PG_SOCKET="$PROJECT_ROOT/.local/postgres-v2-socket"
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
# Maintenance access is only to the new, repo-owned development cluster above.
if ! PGPASSWORD=v2_local "$V2_PG_BIN/psql" -h 127.0.0.1 -p 55432 -U v2_local -d mikrotik_manager_v2 -c 'SELECT 1' >/dev/null 2>&1; then
  PGPASSWORD=v2_local "$V2_PG_BIN/createdb" -h 127.0.0.1 -p 55432 -U v2_local --maintenance-db=postgres mikrotik_manager_v2
fi
printf 'V2 development database ready; apply the explicit demo schema setup separately.\n'
