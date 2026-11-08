"""Fail-closed, manually invoked V2.6 HTTP acceptance entry point for Home WSL."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import platform
import subprocess
import sys
from unittest.mock import patch

from backend.tests import v26_http_acceptance as acceptance


REPO = Path(__file__).resolve().parents[2]
EXPECTED_REPO = Path('/home/suat/Codex-Projects/mikrotik-manager-v2')
EXPECTED_HOST = 'DESKTOP-MT2JS7H'
EXPECTED_BRANCH = 'main-guncel'
EXPECTED_PYTHON = EXPECTED_REPO / 'backend/.venv/bin/python'


def blocked_precondition(*, repo: Path, cwd: Path, hostname: str, wsl: bool,
                         uid: int, owner_uid: int, branch: str, clean: bool,
                         acceptance_root_exists: bool, python_path: Path) -> str | None:
    """Pure policy checks; return a fixed code, never an OS path or secret."""
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
    if acceptance_root_exists:
        return 'ACCEPTANCE_ROOT_ALREADY_EXISTS'
    if python_path != EXPECTED_PYTHON:
        return 'REPOSITORY_VENV_REQUIRED'
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


def runtime_environment(values: dict[str, str] | None = None) -> dict[str, str]:
    values = os.environ if values is None else values
    safe = {key: values[key] for key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ')
            if values.get(key)}
    safe.update(
        PYTHONNOUSERSITE='1',
        PYTHONPATH=f'{REPO}:{REPO / "backend"}:{REPO / "backend/tests"}',
    )
    return safe


@contextmanager
def _isolated_runtime():
    with patch.dict(os.environ, runtime_environment(), clear=True):
        yield


def preflight() -> str | None:
    """Read-only local checks; acceptance harness owns all later resources."""
    try:
        proc_version = Path('/proc/version').read_text(encoding='utf-8')
        wsl = bool(os.environ.get('WSL_DISTRO_NAME')) and 'microsoft' in proc_version.lower()
        state = blocked_precondition(
            repo=REPO, cwd=Path.cwd().resolve(), hostname=platform.node(), wsl=wsl,
            uid=os.getuid(), owner_uid=REPO.stat().st_uid,
            branch=_git('branch', '--show-current').strip(),
            clean=not bool(_git('status', '--porcelain=v1', '--untracked-files=normal')),
            acceptance_root_exists=os.path.lexists(acceptance.ROOT),
            python_path=Path(sys.executable).absolute(),
        )
        if state:
            return state
        return None
    except acceptance.AcceptanceBlocked as error:
        return str(error)
    except Exception:
        # Keep diagnostics closed: never print host paths, env, subprocess output.
        return 'PREFLIGHT_UNAVAILABLE'


def main(during_acceptance=None, *, browser_only=False) -> int:
    blocked = preflight()
    if blocked:
        print('BLOCKED: HOME_WSL_' + blocked)
        return 1
    # The harness binds and holds only the fixed loopback ports, then owns and
    # cleans up its newly-created PostgreSQL cluster and photo-file namespace.
    with _isolated_runtime():
        return acceptance.main(['--run'], during_acceptance=during_acceptance,
                               browser_only=browser_only)


if __name__ == '__main__':
    raise SystemExit(main())
