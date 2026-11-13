"""Explicit Office WSL only: provision a NEW private AAA cluster, run existing 11 tests.

Refuses an existing root or occupied port. No application wiring, external DB,
real identity or provider; reuse the existing ownership/cleanup guard unchanged.
"""
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest

from backend.tests import run_aaa_postgres_wsl as provision
from backend.tests.run_v26_http_acceptance_wsl import _isolated_runtime

REPO = Path('/home/suatpc/Codex-Projects/mikrotik-manager-v2')
HOST = 'DESKTOP-VD5T7VG'
PYTHON = REPO / '.venv/bin/python'


def office_guard():
    if (Path.cwd() != REPO or Path(__file__).resolve().parents[2] != REPO
            or platform.node() != HOST or not os.environ.get('WSL_DISTRO_NAME')
            or 'microsoft' not in Path('/proc/version').read_text().lower()
            or os.getuid() <= 0 or os.getuid() != os.geteuid()
            or REPO.stat().st_uid != os.getuid()
            or Path(sys.prefix).resolve() != (REPO / '.venv').resolve()):
        raise RuntimeError('OFFICE_WSL_IDENTITY_REJECTED')
    branch = subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    if branch != 'main-guncel':
        raise RuntimeError('OFFICE_BRANCH_REJECTED')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():
        raise RuntimeError('DIRTY_WORKTREE_REJECTED')


def run_bridge(cluster_id):
    # Cluster ID comes only from provision's verified owned PGDATA connection,
    # never an environment variable, arbitrary DSN or user-supplied override.
    if not isinstance(cluster_id,str) or not cluster_id.isdecimal():
        raise RuntimeError('VERIFIED_CLUSTER_ID_REQUIRED')
    from backend.tests.test_aaa_pg_bridge import PostgresBridgeAcceptance
    class OfficeAcceptance(PostgresBridgeAcceptance):
        expected_cluster_id = cluster_id
        environment_guard = staticmethod(office_guard)
    # Parent opt-in decorator is retained; activate only in this explicit runner.
    if os.environ.get('V2_AAA_EXISTING_PG_TESTS') != '1':
        raise RuntimeError('EXPLICIT_OFFICE_PG_OPT_IN_REQUIRED')
    # The inherited class skip flag was bound at import; the import above must
    # occur only after main's explicit process-local opt-in is installed.
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfficeAcceptance)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful() or result.testsRun != 11 or result.skipped:
        raise RuntimeError('OFFICE_ELEVEN_PG_TESTS_NOT_PASSED')
    print('PASS: Office isolated AAA PostgreSQL 11 scenarios; not production acceptance')


def main():
    office_guard()
    with _isolated_runtime():
        os.environ['V2_AAA_EXISTING_PG_TESTS']='1'
        provision.prepare(bridge_acceptance=run_bridge)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print DSN, secrets, SQL parameters or arbitrary exception messages.
        print('BLOCKED: OFFICE_AAA_POSTGRES_' + type(error).__name__)
        raise SystemExit(1) from None
