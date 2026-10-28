#!/usr/bin/env bash
# Browser acceptance delegates API ownership to the existing Stage 9 manager.
set -euo pipefail
V2_BROWSER_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_BROWSER_ROOT"
export PYTHONPATH="$V2_BROWSER_ROOT/backend"
if [[ ! -x .venv/bin/python ]]; then
  printf 'BROWSER BLOCKED: V2 .venv eksik; servis/veri değiştirilmedi.\n' >&2
  exit 1
fi
# The internal worker never owns an API process; it runs inside ManagedAPI.
if [[ "${1:-}" != '--with-ready-api' ]]; then
  exec .venv/bin/python -m app.demo_api_runner --browser "$@"
fi
shift
if [[ $# -ne 0 ]]; then
  printf 'BROWSER BLOCKED: beklenmeyen worker argümanı.\n' >&2
  exit 1
fi
.venv/bin/python -m app.demo_readiness
.venv/bin/python - <<'PY'
from urllib.request import build_opener, ProxyHandler
from app.demo_readiness import NoRedirect
try:
    with build_opener(ProxyHandler({}),NoRedirect()).open('http://127.0.0.1:5173',timeout=3) as response:
        if b'MikroTik Manager V2' not in response.read():raise ValueError('V2 UI identity')
except Exception:
    raise SystemExit('BROWSER BLOCKED: yerel V2 UI 127.0.0.1:5173 erişilemiyor; UI servisi başlatılmadı.')
PY
V2_BROWSER_TOOLS="$V2_BROWSER_ROOT/.local/browser-tools"
if [[ -L .local || -L "$V2_BROWSER_TOOLS" ]]; then
  printf 'BLOCKED: test araç yolu symlink olamaz.\n' >&2
  exit 1
fi
mkdir -p "$V2_BROWSER_TOOLS"
export PLAYWRIGHT_BROWSERS_PATH="$V2_BROWSER_TOOLS/browsers"
if [[ ! -f "$V2_BROWSER_TOOLS/node_modules/playwright/index.mjs" ]]; then
  printf 'Yalnız .local/browser-tools içine Playwright test aracı indiriliyor.\n'
  if ! npm --prefix "$V2_BROWSER_TOOLS" install --no-save --no-package-lock playwright; then
    printf "BROWSER BLOCKED: yerel test aracı indirilemedi; veri değiştirilmedi.\n" >&2; exit 1
  fi
fi
if ! node "$V2_BROWSER_TOOLS/node_modules/playwright/cli.js" install chromium; then
  printf "BROWSER BLOCKED: Chromium hazırlanamadı; veri değiştirilmedi.\n" >&2; exit 1
fi
exec node frontend/tests/detailCenter.browser.mjs
