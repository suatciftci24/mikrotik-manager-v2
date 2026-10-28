#!/usr/bin/env bash
# Acceptance only: never starts/stops services, prepares schemas or seeds old demo data.
set -euo pipefail
V2_ACCEPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_ACCEPT_ROOT"
export PYTHONPATH="$V2_ACCEPT_ROOT/backend"
exec .venv/bin/python -m app.demo_acceptance "$@"
