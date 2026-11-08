"""Fail-closed, manually invoked synthetic V2.6 browser acceptance for Home WSL."""
from __future__ import annotations

import os
import argparse
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from backend.tests import run_v26_http_acceptance_wsl as http_runner

REPO = Path(__file__).resolve().parents[2]
EXPECTED_REPO = Path('/home/suat/Codex-Projects/mikrotik-manager-v2')
EXPECTED_HOST = 'DESKTOP-MT2JS7H'
EXPECTED_BRANCH = 'main-guncel'
PLAYWRIGHT = REPO / 'frontend/node_modules/playwright-core/index.mjs'
ESBUILD = REPO / 'frontend/node_modules/esbuild/package.json'
NODE_TESTS = (
    'tests/runtimeProfile.test.mjs',
    'tests/v26AcceptanceProfile.test.mjs',
    'tests/userManagement.test.mjs',
    'tests/subscriberPhotos.test.mjs',
    'tests/alarmCenter.test.mjs',
    'tests/auditCenter.test.mjs',
    'tests/routerCenter.test.mjs',
    'tests/subscriberCenter.test.mjs',
    'tests/dashboardOverview.test.mjs',
    'tests/operationsDashboard.test.mjs',
)


def blocked_precondition(*, repo: Path, cwd: Path, hostname: str, wsl: bool,
                         uid: int, owner_uid: int, branch: str, clean: bool,
                         node_path: str | None, playwright_exists: bool,
                         esbuild_exists: bool) -> str | None:
    """Pure gates with fixed diagnostics; no ports, subprocesses, or browser used."""
    if repo != EXPECTED_REPO or cwd != EXPECTED_REPO:
        return 'REPOSITORY_PATH_REJECTED'
    if hostname != EXPECTED_HOST or not wsl:
        return 'HOME_WSL_IDENTITY_REJECTED'
    if uid <= 0 or owner_uid != uid:
        return 'REPOSITORY_OWNER_REJECTED'
    if branch != EXPECTED_BRANCH:
        return 'BRANCH_REJECTED'
    if not clean:
        return 'DIRTY_WORKTREE_REJECTED'
    if not node_path or not playwright_exists or not esbuild_exists:
        return 'LOCAL_BROWSER_TOOLCHAIN_UNAVAILABLE'
    return None


def _git(*args: str) -> str:
    result = subprocess.run(
        ['git', '-C', str(REPO), *args], check=True, capture_output=True,
        text=True, timeout=5, env={
            'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'HOME': os.environ.get('HOME', '/home/suat'),
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0',
        },
    )
    return result.stdout


def safe_environment(values: dict[str, str] | None = None) -> dict[str, str]:
    # No V2/PG/Playwright overrides, Python injection or dynamic loader settings.
    values = os.environ if values is None else values
    safe = {key: values[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ')
            if values.get(key)}
    return safe


def preflight() -> str | None:
    """Read-only host/repository/tool and disposable HTTP fixture checks."""
    try:
        proc_version = Path('/proc/version').read_text(encoding='utf-8')
        wsl = bool(os.environ.get('WSL_DISTRO_NAME')) and 'microsoft' in proc_version.lower()
        state = blocked_precondition(
            repo=REPO, cwd=Path.cwd().resolve(), hostname=platform.node(), wsl=wsl,
            uid=os.getuid(), owner_uid=REPO.stat().st_uid,
            branch=_git('branch', '--show-current').strip(),
            clean=not bool(_git('status', '--porcelain=v1', '--untracked-files=normal')),
            node_path=shutil.which('node'), playwright_exists=PLAYWRIGHT.is_file(),
            esbuild_exists=ESBUILD.is_file(),
        )
        if state:
            return state
        http_state = http_runner.preflight()
        if http_state:
            return 'HTTP_' + http_state
        return None
    except Exception:
        return 'PREFLIGHT_UNAVAILABLE'


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
    try:
        return subprocess.run(command, cwd=cwd, env=env, check=False).returncode
    except Exception:
        print('BLOCKED: HOME_WSL_TEST_PROCESS_UNAVAILABLE', file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser-only-diagnostic', action='store_true',
                        help='skip contract and HTTP business suites; run browser against fresh owned PG and verified loopback readiness only')
    args = parser.parse_args(argv)
    blocked = preflight()
    if blocked:
        print('BLOCKED: HOME_WSL_' + blocked)
        return 1

    node = shutil.which('node')
    assert node is not None
    env = safe_environment()
    frontend = REPO / 'frontend'
    preflight_result = _run([node, 'tests/v26BrowserPreflight.mjs'], cwd=frontend, env=env)
    if preflight_result:
        print('BLOCKED: HOME_WSL_LOCAL_BROWSER_PREFLIGHT')
        return preflight_result or 1

    if not args.browser_only_diagnostic:
        tests = _run([node, '--experimental-transform-types', '--test', *NODE_TESTS],
                     cwd=frontend, env=env)
        if tests:
            print('FAIL: V2.6 socketless frontend contract suite')
            return tests

    def run_browser_while_disposable_http_and_postgres_are_alive():
        browser = _run([node, 'tests/managementCenters.browser.mjs'], cwd=frontend, env=env)
        if browser:
            raise http_runner.acceptance.AcceptanceBlocked('BROWSER_ACCEPTANCE_DID_NOT_COMPLETE')

    # The HTTP harness owns both fixed loopback listeners, its fresh PG16 cluster,
    # app lifetime, and cleanup. Browser runs inside its live verified profile.
    result = http_runner.main(
        during_acceptance=run_browser_while_disposable_http_and_postgres_are_alive,
        browser_only=args.browser_only_diagnostic,
    )
    if result:
        return result
    if args.browser_only_diagnostic:
        print('PASS: V2.6 disposable PostgreSQL + verified-profile browser diagnostic; cleanup complete')
    else:
        print('PASS: V2.6 synthetic PostgreSQL + loopback HTTP + verified-profile Chromium acceptance; cleanup complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
