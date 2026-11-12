#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $# -ne 0 || ! -x .venv/bin/python ]]; then
  printf '%s\n' 'BLOCKED: mevcut V2 .venv gerekli; hesap/parola argümanı kabul edilmez.' >&2
  exit 1
fi
# Fixed existing office demo DB via Settings defaults, no inherited profile/DSN.
# Owner, DB name/role/port, PGDATA, schema marker and setup seal are verified by CLI.
# Never initializes a DB/schema, runs migrations or resets an existing account.
exec env -i PATH=/usr/bin:/bin HOME="$HOME" LANG=C.UTF-8 PYTHONPATH="$PWD/backend" \
  "$PWD/.venv/bin/python" -s -m app.first_admin --create-existing-schema
