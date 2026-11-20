"""Offline checks for deploy diagnostics and recovery gates."""
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import ssl
from unittest import TestCase
from unittest.mock import Mock, patch

spec = spec_from_file_location('v2616_installer', Path(__file__).with_name('install-vds-v2616.py'))
installer = module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(TestCase):
    def test_read_only_diagnosis_has_no_install_or_secret_access(self):
        out = io.StringIO()
        with patch.object(installer, 'verify_baseline', return_value=(installer.NEW, 'build', True)), \
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
             patch.object(installer, 'verify_npm_web_unit', calls.verify_web), \
             patch.object(installer, 'verify_backup_digest', calls.digest), \
             patch.object(installer, 'restore_swaps', calls.restore), \
             patch.object(installer, 'verify_backup', calls.compare), \
             patch.object(installer, 'health', calls.health), \
             patch.object(installer, 'checkout_head', return_value=installer.OLD):
            self.assertTrue(installer.rollback(backup, staged, [], [], True, False, 'build', installer.OLD, npm_preview=True))
        self.assertEqual([(call[0], call.args, call.kwargs) for call in calls.mock_calls], [
            ('system', ('stop', installer.WEB, installer.API), {}),
            ('digest', (backup,), {}),
            ('restore', (staged, []), {}),
            ('system', ('daemon-reload',), {}),
            ('compare', (backup,), {}),
            ('verify_web', (), {'running':False}),
            ('system', ('start', installer.API, installer.WEB), {}),
            ('health', ('2.6.13',), {'expected_build':'build', 'npm_preview':True}),
        ])


    def test_only_pinned_npm_preview_layout_is_accepted(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root/'frontend/node_modules'
            (modules/'.bin').mkdir(parents=True)
            entry = modules/'vite/bin/vite.js'
            entry.parent.mkdir(parents=True)
            entry.touch(mode=0o755)
            shim = modules/'.bin/vite'
            shim.symlink_to('../vite/bin/vite.js')
            values = {
                'LoadState':'loaded', 'NeedDaemonReload':'no', 'MainPID':'73',
                'ExecStart':('{ path=/usr/bin/npm ; argv[]=/usr/bin/npm exec -- vite preview '
                             '--host 127.0.0.1 --port 15173 --strictPort ; ignore_errors=no ; }'),
                'WorkingDirectory':str(root/'frontend'), 'User':'mikadmin',
                'FragmentPath':'/etc/systemd/system/mikrotik-v26-web.service', 'KillMode':'control-group',
            }
            with patch.object(installer, 'ROOT', root), \
                 patch.object(installer, 'prop', side_effect=lambda unit, field: values.get(field, '')), \
                 patch.object(installer.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)), \
                 patch.object(installer.os, 'readlink', side_effect=installer.os.readlink) as readlink:
                real_readlink = readlink.side_effect
                readlink.side_effect = lambda path, *args, **kwargs: (
                    str(root/'frontend') if path == '/proc/73/cwd' else real_readlink(path, *args, **kwargs))
                installer.verify_npm_web_unit()
                for field, alternate, code in (
                    ('ExecStart', values['ExecStart'].replace('127.0.0.1', '0.0.0.0'), 'WEB_UNIT_EXEC_START_UNSUPPORTED'),
                    ('ExecStart', values['ExecStart'].replace('--strictPort', ''), 'WEB_UNIT_EXEC_START_UNSUPPORTED'),
                    ('ExecStart', values['ExecStart'].replace('15173', '15174'), 'WEB_UNIT_EXEC_START_UNSUPPORTED'),
                    ('User', 'root', 'WEB_NPM_USER_MISMATCH'),
                    ('WorkingDirectory', str(root), 'WEB_NPM_WORKING_DIRECTORY_MISMATCH'),
                    ('FragmentPath', '/other/mikrotik-v26-web.service', 'WEB_NPM_FRAGMENT_MISMATCH'),
                    ('KillMode', 'process', 'WEB_NPM_KILL_MODE_MISMATCH'),
                ):
                    with self.subTest(field=field, code=code), patch.dict(values, {field:alternate}):
                        with self.assertRaisesRegex(installer.CheckRejected, f'^{code}$'):
                            installer.verify_npm_web_unit(running=False)
                shim.unlink()
                with self.assertRaisesRegex(installer.CheckRejected, '^WEB_NPM_LOCAL_VITE_UNREADABLE$'):
                    installer.verify_npm_web_unit(running=False)

    def test_loopback_preview_checks_served_bytes_and_refuses_credentials(self):
        with patch.object(installer, 'request', return_value=(b'previous dist', {})) as request:
            with self.assertRaisesRegex(installer.CheckRejected, '^WEB_LOOPBACK_INDEX_DISK_MISMATCH$'):
                installer.verify_preview_response('/', b'prepared dist', 'WEB_LOOPBACK_INDEX')
            request.assert_called_once_with('/', code='WEB_LOOPBACK_INDEX', loopback=True)
        with patch.object(installer.http.client, 'HTTPConnection', side_effect=AssertionError):
            with self.assertRaisesRegex(installer.CheckRejected, '^WEB_LOOPBACK_PUBLIC_GET_ONLY$'):
                installer.request('/', credentials=('user', 'fixture'), loopback=True)
