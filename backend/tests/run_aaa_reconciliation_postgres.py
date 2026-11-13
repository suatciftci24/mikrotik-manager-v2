"""New isolated PGDATA only, no existing fixture/demo fallback."""
import os
from pathlib import Path
import unittest
from uuid import uuid4
from backend.tests import run_aaa_postgres_wsl as provision
from backend.tests.run_v26_http_acceptance_wsl import _isolated_runtime

ROOT = Path('/tmp/mikrotik-v26-reconciliation-'+uuid4().hex)


def acceptance(cluster_id):
    from backend.tests.test_aaa_reconciliation_postgres import ReconciliationPostgresAcceptance
    class FreshAcceptance(ReconciliationPostgresAcceptance):
        expected_cluster_id = cluster_id
        fixture_root = ROOT
    names = ('test_timeout_reconciliation_and_runtime_rls', 'test_partial_reconciliation_and_runtime_rls')
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(FreshAcceptance(n) for n in names))
    if not result.wasSuccessful() or result.testsRun != 2 or result.skipped:
        raise RuntimeError('RECONCILIATION_ACCEPTANCE_NOT_PASSED')


def main(*, bridge_acceptance=acceptance):
    provision.home_guard()
    if os.path.lexists(ROOT):
        raise RuntimeError('ACCEPTANCE_ROOT_ALREADY_EXISTS')
    distro = os.environ['WSL_DISTRO_NAME']
    with _isolated_runtime():
        os.environ['WSL_DISTRO_NAME'] = distro
        os.environ['V2_AAA_EXISTING_PG_TESTS'] = '1'
        provision.prepare(root=ROOT,bridge_acceptance=bridge_acceptance,bootstrap_only=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('BLOCKED: FRESH_RECONCILIATION_' + type(error).__name__)
        raise SystemExit(1) from None
