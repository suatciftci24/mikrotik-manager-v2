"""Local guard tests. No listeners, connections or external commands."""
from contextlib import redirect_stderr
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from app import demo_api_runner
from app.core.config import DEFAULT_DATABASE_URL, local_demo_blocker
from app import demo_repair


class LocalWorkflowBoundariesTests(TestCase):
    def test_local_defaults_and_existing_local_pgdata_are_allowed(self):
        self.assertIsNone(local_demo_blocker({}))
        self.assertIsNone(local_demo_blocker({
            'V2_DATABASE_URL': DEFAULT_DATABASE_URL,
            'V2_LOCAL_PGDATA': '/existing/demo',
            'V2_API_PORT': '18000',
            'V2_ROUTER_ONBOARDING_ENABLED': 'false',
        }))

    def test_profile_devices_and_database_route_overrides_fail_closed(self):
        for values, blocker in (
            ({'V2_DEPLOYMENT_PROFILE':'v26-isolated-acceptance'}, 'PROFILE_REQUIRED'),
            ({'V2_ENVIRONMENT':'production'}, 'PROFILE_REQUIRED'),
            ({'V2_ROUTER_ONBOARDING_ENABLED':'true'}, 'DEVICE_ACCESS_REJECTED'),
            ({'V2_CEBECI_API_SSL_ENABLED':'true'}, 'DEVICE_ACCESS_REJECTED'),
            ({'V2_V26_CEBECI_READ_ENABLED':'true'}, 'DEVICE_ACCESS_REJECTED'),
            ({'V2_ROUTER_ONBOARDING_OPERATOR_IDS':'fixture'}, 'DEVICE_ACCESS_REJECTED'),
            ({'PGHOSTADDR':'192.0.2.10'}, 'DATABASE_OVERRIDE_REJECTED'),
            ({'PGSERVICE':'other'}, 'DATABASE_OVERRIDE_REJECTED'),
            ({'PGOPTIONS':'-c search_path=other'}, 'DATABASE_OVERRIDE_REJECTED'),
            ({'V2_DATABASE_URL':DEFAULT_DATABASE_URL+'?host=192.0.2.10'}, 'DATABASE_TARGET_REJECTED'),
            ({'V2_DATABASE_URL':DEFAULT_DATABASE_URL.replace('55432','55433')}, 'DATABASE_TARGET_REJECTED'),
        ):
            with self.subTest(keys=list(values)):
                self.assertEqual(local_demo_blocker(values), 'LOCAL_DEMO_'+blocker)

    def test_browser_acceptance_and_demo_db_block_before_access(self):
        with patch.dict('os.environ', {'V2_ROUTER_ONBOARDING_ENABLED':'true'}, clear=True), \
             patch.object(demo_api_runner, 'ManagedAPI') as api, \
             patch.object(demo_api_runner, 'socket_blocker') as probe, \
             patch.object(demo_repair, 'PostgresDemoStore') as store, redirect_stderr(StringIO()) as output:
            self.assertEqual(demo_api_runner.main(['--browser']), 1)
            self.assertIn('LOCAL_DEMO_DEVICE_ACCESS_REJECTED', output.getvalue())
            with self.assertRaisesRegex(demo_repair.RepairBlocked, 'LOCAL_DEMO_DEVICE_ACCESS_REJECTED'):
                demo_repair.preflight(demo_repair.engine)
            api.assert_not_called()
            probe.assert_not_called()
            store.assert_not_called()
