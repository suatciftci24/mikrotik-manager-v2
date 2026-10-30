#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ $# -ne 0 ]]; then
  printf '%s\n' 'BLOCKED: parola veya hesap bilgisi komut argümanı olarak verilmez.' >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  printf '%s\n' 'BLOCKED: mevcut V2 .venv gerekli; servis veya bağımlılık başlatılmadı.' >&2
  exit 1
fi
export PYTHONPATH="$PWD/backend"
exec .venv/bin/python -m app.first_admin --create
