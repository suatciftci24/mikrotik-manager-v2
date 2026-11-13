"""Fresh-only observer/principal PG acceptance; no remote transport or fallback."""
import unittest
from backend.tests import run_aaa_reconciliation_postgres as runner


def acceptance(cluster_id):
    from backend.tests.test_aaa_observer_postgres import ObserverPostgresAcceptance
    class FreshAcceptance(ObserverPostgresAcceptance):
        expected_cluster_id = cluster_id
        fixture_root = runner.ROOT
    names = ('test_observer_evidence_atomicity_and_race','test_authenticated_principal_and_rls_denials')
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(FreshAcceptance(n) for n in names))
    if not result.wasSuccessful() or result.testsRun!=2 or result.skipped:
        raise RuntimeError('OBSERVER_ACCEPTANCE_NOT_PASSED')


if __name__ == '__main__':
    try:
        runner.main(bridge_acceptance=acceptance)
    except Exception as error:
        print('BLOCKED: FRESH_OBSERVER_' + type(error).__name__)
        raise SystemExit(1) from None
