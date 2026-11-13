"""Home WSL: NEW disposable PostgreSQL only; no existing database fallback."""
import os
import unittest
from backend.tests import run_aaa_postgres_wsl as provision
from backend.tests.run_v26_http_acceptance_wsl import _isolated_runtime


def acceptance(cluster_id):
    from backend.tests.test_aaa_combined_postgres import CombinedPostgresAcceptance
    class FreshAcceptance(CombinedPostgresAcceptance):
        expected_cluster_id = cluster_id
    names = ('test_combined_lifecycle_and_expire', 'test_combined_denials_atomicity_and_races')
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(FreshAcceptance(n) for n in names))
    if not result.wasSuccessful() or result.testsRun != len(names) or result.skipped:
        raise RuntimeError('COMBINED_ACCEPTANCE_NOT_PASSED')


def main():
    provision.home_guard()
    # Refuse reuse before startup or any connection. prepare repeats this check.
    if os.path.lexists(provision.ROOT):
        raise RuntimeError('ACCEPTANCE_ROOT_ALREADY_EXISTS')
    distro = os.environ['WSL_DISTRO_NAME']
    with _isolated_runtime():
        os.environ['WSL_DISTRO_NAME'] = distro
        os.environ['V2_AAA_EXISTING_PG_TESTS'] = '1'
        provision.prepare(bridge_acceptance=acceptance, bootstrap_only=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not print SQL, DSNs, parameters or generated authentication material.
        code = str(error) if type(error) is RuntimeError and str(error) in (
            'ACCEPTANCE_ROOT_ALREADY_EXISTS', 'HOME_WSL_IDENTITY_REJECTED',
            'COMBINED_ACCEPTANCE_NOT_PASSED') else type(error).__name__
        print('BLOCKED: FRESH_AAA_POSTGRES_' + code)
        raise SystemExit(1) from None
