from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
from pathlib import Path
from app.integrations.aaa_runtime_guard import require_fixture_runtime
from app.repositories.aaa_reconciliation import DurableFixtureReconciliation
from app.repositories.aaa_fixture_bridge import PostgresFixtureBridge
from backend.tests.v26_owned_resources import reconciliation_root
from backend.tests import run_aaa_reconciliation_postgres as runner


class ReconciliationSafety(TestCase):
    def test_runtime_flags_scope_and_rls_are_fail_closed(self):
        tenant = uuid4()
        valid = ('runtime','v26_aaa_fixture','mikrotik_v26_acceptance','127.0.0.1',55433,tenant,False,False)
        for index,value in ((0,'foreign'),(1,'v26_acceptance'),(2,'demo'),(3,'192.0.2.1'),
                            (4,5432),(5,uuid4()),(6,True),(7,True)):
            row = list(valid)
            row[index] = value
            c = Mock()
            c.execute.return_value.one.return_value = tuple(row)
            with self.assertRaises(PermissionError): require_fixture_runtime(c,login='runtime',tenant_id=tenant)
        for flags in ((False,True),(True,False),(True,True)):
            c = Mock()
            c.execute.side_effect = [Mock(one=lambda:valid),Mock(all=lambda:[('v2_aaa','attempts',*flags,'runtime' if all(flags) else 'admin')])]
            with self.assertRaises(PermissionError): require_fixture_runtime(c,login='runtime',tenant_id=tenant)

    def test_new_root_only_and_no_fallback(self):
        self.assertTrue(reconciliation_root(Path('/tmp/mikrotik-v26-reconciliation-'+'a'*32)))
        for p in ('/tmp/mikrotik-v26-acceptance','/tmp/mikrotik-v26-reconciliation-../../demo',
                  '/tmp/mikrotik-v26-reconciliation-old','/home/suat/mikrotik-v26-reconciliation-'+'a'*32):
            self.assertFalse(reconciliation_root(Path(p)))
        with patch.object(runner.provision,'home_guard'),patch.object(runner.os.path,'lexists',return_value=True), \
                patch.object(runner.provision,'prepare') as prepare:
            with self.assertRaises(RuntimeError): runner.main()
            prepare.assert_not_called()

    def test_explicit_revisions_required_before_opening_session(self):
        bridge = object.__new__(PostgresFixtureBridge)
        bridge.sessions = Mock(side_effect=AssertionError('DB forbidden'))
        service = DurableFixtureReconciliation(bridge,Mock(),Mock())
        for value in (-1,True,'0'):
            with self.assertRaises(PermissionError):
                service.evaluate(None,None,None,execution_id=uuid4(),evaluation_id=uuid4(),
                    expected_revision=value,owner_revision=1,fence=1)
        bridge.sessions.assert_not_called()
