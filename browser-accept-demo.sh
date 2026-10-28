#!/usr/bin/env bash
# Normal WSL browser acceptance; no app/DB restart, seed or migration.
set -euo pipefail
V2_BROWSER_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$V2_BROWSER_ROOT"
export PYTHONPATH="$V2_BROWSER_ROOT/backend"
.venv/bin/python -m app.demo_readiness
.venv/bin/python - <<'PY'
from urllib.request import build_opener, ProxyHandler
from app.demo_readiness import NoRedirect
try:
    with build_opener(ProxyHandler({}),NoRedirect()).open('http://127.0.0.1:5173',timeout=3) as response:
        if b'MikroTik Manager V2' not in response.read():raise ValueError('V2 UI identity')
except Exception:
    raise SystemExit('BROWSER BLOCKED: yerel V2 UI 127.0.0.1:5173 erişilemiyor; servis başlatılmadı.')
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
