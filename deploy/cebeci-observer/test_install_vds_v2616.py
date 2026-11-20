"""Offline checks for deploy diagnostics and recovery gates."""
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
import io
from pathlib import Path
import ssl
from unittest import TestCase
from unittest.mock import Mock, patch

spec = spec_from_file_location('v2616_installer', Path(__file__).with_name('install-vds-v2616.py'))
installer = module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(TestCase):
    def test_read_only_diagnosis_has_no_install_or_secret_access(self):
        out = io.StringIO()
        with patch.object(installer, 'verify_baseline', return_value=(installer.NEW, 'build')), \
             patch.object(installer, 'head_matches_api', return_value='GIT_HEAD_TREE_DIFFERS_FROM_API'), \
             patch.object(installer, 'run', side_effect=AssertionError), \
             patch.object(installer, 'installation_credentials', side_effect=AssertionError), redirect_stdout(out):
            self.assertEqual(installer.preflight_only(), 0)
        self.assertIn('GIT_HEAD_TARGET · GIT_HEAD_TREE_DIFFERS_FROM_API', out.getvalue())
        self.assertIn('DEFERRED', out.getvalue())

    def test_preflight_reports_specific_safe_failure(self):
        out = io.StringIO()
        with patch.object(installer.os, 'geteuid', return_value=0), \
             patch.object(installer, 'command', return_value=b'[{"addr_info": []}]'), redirect_stderr(out):
            self.assertEqual(installer.preflight_only(), 1)
        self.assertEqual(out.getvalue().strip(), 'BLOCKED — VDS_IPV4_NOT_ASSIGNED')

        with patch.object(installer, 'request', side_effect=ssl.SSLError('PRIVATE_CANARY')):
            with self.assertRaisesRegex(installer.CheckRejected, '^API_READY_REQUEST_TLS$'):
                installer.health_json('/api/ready', 'API_READY')

    def test_service_start_hook_has_its_own_code(self):
        values = {'LoadState':'loaded', 'NeedDaemonReload':'no', 'ExecStartPre':'PRIVATE_CANARY'}
        with patch.object(installer, 'prop', side_effect=lambda unit, field: values.get(field, '')):
            with self.assertRaisesRegex(installer.CheckRejected, '^API_UNIT_EXEC_START_PRE_PRESENT$'):
                installer.verify_unit(installer.API, 'API', 'backend')

    def test_recovery_stops_observer_first_and_never_starts_unverified_panel(self):
        calls = Mock()
        with patch.object(installer, 'system', calls.system), \
             patch.object(installer, 'verify_backup_digest', side_effect=OSError('PRIVATE_CANARY')), \
             patch.object(installer, 'restore_swaps', calls.restore), redirect_stderr(io.StringIO()):
            self.assertFalse(installer.rollback(Path('/fixture/backup'), Path('/fixture/stage'),
                                                [], [], True, True, 'build', None))
        self.assertEqual([call.args for call in calls.system.call_args_list],
                         [('stop', installer.OBSERVER), ('disable', installer.OBSERVER),
                          ('stop', installer.WEB, installer.API), ('daemon-reload',)])
        calls.restore.assert_not_called()

    def test_recovery_checks_all_swap_identities_before_any_exchange(self):
        switched = [('backend/app', (1, 10), (1, 11)), ('release.json', (1, 20), (1, 21))]
        with patch.object(installer, 'identity', side_effect=[(1, 11), (1, 10), (1, 99)]), \
             patch.object(installer, 'exchange') as exchange:
            with self.assertRaisesRegex(installer.CheckRejected, '^ROLLBACK_TARGET_DRIFT$'):
                installer.restore_swaps(Path('/fixture/stage'), switched)
        exchange.assert_not_called()

    def test_recovery_restarts_only_after_archive_comparison_and_checks_original_build(self):
        calls = Mock()
        backup = Path('/fixture/backup')
        staged = Path('/fixture/stage')
        with patch.object(installer, 'system', calls.system), \
             patch.object(installer, 'verify_backup_digest', calls.digest), \
             patch.object(installer, 'restore_swaps', calls.restore), \
             patch.object(installer, 'verify_backup', calls.compare), \
             patch.object(installer, 'health', calls.health), \
             patch.object(installer, 'checkout_head', return_value=installer.OLD):
            self.assertTrue(installer.rollback(backup, staged, [], [], True, False, 'build', installer.OLD))
        self.assertEqual([(call[0], call.args, call.kwargs) for call in calls.mock_calls], [
            ('system', ('stop', installer.WEB, installer.API), {}),
            ('digest', (backup,), {}),
            ('restore', (staged, []), {}),
            ('system', ('daemon-reload',), {}),
            ('compare', (backup,), {}),
            ('system', ('start', installer.API, installer.WEB), {}),
            ('health', ('2.6.13',), {'expected_build':'build'}),
        ])
