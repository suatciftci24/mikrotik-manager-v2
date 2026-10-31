"""Only synthetic file metadata/results; never contact or modify PostgreSQL."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot'
spec = importlib.util.spec_from_file_location('vds_preflight_test', PACKAGE / 'native-admin.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
deploy = native.deploy


class PreflightDiagnosticsTests(unittest.TestCase):
    def test_filesystem_failures_identify_component_and_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config'
            with self.assertRaisesRegex(deploy.Blocked, '^V2_PREFLIGHT_BASE_MISSING$'):
                deploy.safe(path, os.getuid(), 0o600, label='V2_PREFLIGHT_BASE')
            path.write_text('synthetic')
            path.chmod(0o600)
            for uid, mode, reason in ((os.getuid() + 1, 0o600, 'OWNER_MISMATCH'), (os.getuid(), 0o644, 'MODE_MISMATCH')):
                with self.assertRaisesRegex(deploy.Blocked, '^V2_PREFLIGHT_PGDATA_' + reason + '$'):
                    deploy.safe(path, uid, mode, label='V2_PREFLIGHT_PGDATA')
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaisesRegex(deploy.Blocked, '^V2_FILE_TYPE_REJECTED$'):
                deploy.safe(link, os.getuid(), 0o600)
            link.unlink()
            os.link(path, link)
            with self.assertRaisesRegex(deploy.Blocked, '^V2_FILE_HARDLINK_REJECTED$'):
                deploy.safe(path, os.getuid(), 0o600)

    def test_os_account_absence_does_not_leak_lookup_exception(self):
        with patch.object(deploy.pwd, 'getpwnam', side_effect=KeyError('SYNTHETIC_SECRET')):
            with self.assertRaises(deploy.Blocked) as error:
                deploy.account('synthetic', 'V2_PREFLIGHT_DB_OS_USER_MISSING')
        self.assertEqual(deploy.failure_code(error.exception), 'V2_PREFLIGHT_DB_OS_USER_MISSING')
        self.assertNotIn('SYNTHETIC_SECRET', str(error.exception))

    def test_sql_failures_separate_identity_state_connectivity_schema_and_permissions(self):
        cases = (
            (b'ERROR:  V2_NATIVE_EXISTING_ADMIN_STOP', 'V2_NATIVE_EXISTING_ADMIN_STOP'),
            (b'ERROR:  V2_NATIVE_OTHER_USERS_STOP', 'V2_NATIVE_OTHER_USERS_STOP'),
            (b'ERROR:  V2_NATIVE_SETUP_CLOSED_STOP', 'V2_NATIVE_SETUP_CLOSED_STOP'),
            (b'ERROR:  V2_NATIVE_SEAL_PRESENT_STOP', 'V2_NATIVE_SEAL_PRESENT_STOP'),
            (b'ERROR:  V2_NATIVE_AUDIT_PRESENT_STOP', 'V2_NATIVE_AUDIT_PRESENT_STOP'),
            (b'ERROR:  V2_NATIVE_SETUP_STATE_REJECTED', 'V2_NATIVE_SETUP_STATE_REJECTED'),
            (b'ERROR:  V2_CLUSTER_REJECTED', 'V2_CLUSTER_REJECTED'),
            (b'connection refused', 'V2_DB_CONNECTION_REFUSED'),
            (b'No such file or directory', 'V2_DB_SOCKET_UNAVAILABLE'),
            (b'Peer authentication failed', 'V2_DB_PEER_AUTH_FAILED'),
            (b'permission denied to set parameter', 'V2_DB_MAINTENANCE_PERMISSION_DENIED'),
            (b'permission denied for table', 'V2_DB_PERMISSION_DENIED'),
            (b'role "synthetic" does not exist', 'V2_DB_ROLE_MISSING'),
            (b'database "synthetic" does not exist', 'V2_DATABASE_MISSING'),
            (b'relation "synthetic" does not exist', 'V2_DB_SCHEMA_MISSING'),
        )
        for message, expected in cases:
            with self.subTest(expected=expected):
                result = subprocess.CompletedProcess([], 3, stdout=b'SYNTHETIC_SECRET', stderr=message + b' SYNTHETIC_SECRET')
                self.assertEqual(deploy.classify_sql(result), expected)
        unknown = subprocess.CompletedProcess([], 3, stderr=b'SYNTHETIC_SECRET')
        self.assertEqual(deploy.classify_sql(unknown), 'V2_DB_SQL_FAILED')

    def test_sql_runner_classifies_instead_of_exposing_server_output(self):
        result = subprocess.CompletedProcess([], 3, stdout=b'SYNTHETIC_SECRET', stderr=b'ERROR:  V2_NATIVE_OTHER_USERS_STOP')
        with patch.object(deploy, 'run', return_value=result) as command:
            with self.assertRaisesRegex(deploy.Blocked, '^V2_NATIVE_OTHER_USERS_STOP$'):
                deploy.sql('SELECT 1 /* SYNTHETIC_SECRET */')
        self.assertFalse(command.call_args.kwargs['check'])
        self.assertEqual(command.call_args.kwargs['env']['LC_ALL'], 'C')
        self.assertNotIn('SYNTHETIC_SECRET', ' '.join(command.call_args.args[0]))

    def test_preflight_only_finishes_before_any_app_dependency_or_account_changes(self):
        old_umask = os.umask(0o077)
        try:
            with patch.object(deploy.os, 'geteuid', return_value=0), patch.object(
                    deploy.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1001, pw_gid=1001)), patch.object(
                    deploy, 'safe'), patch.object(deploy, 'sql', return_value=subprocess.CompletedProcess([], 0, stdout=b'f\n')), patch.object(
                    deploy, 'run') as command, patch.object(native, 'provision') as create, patch.object(
                    Path, 'read_bytes', side_effect=AssertionError('source must not be read')), patch('builtins.print') as output:
                deploy.main(Path('/home/mikadmin/v2-complete.synthetic'), native=native, preflight_only=True)
                command.assert_not_called()
                create.assert_not_called()
                output.assert_called_once_with('PASS: V2_NATIVE_PREFLIGHT_READY_NO_USERS_SETUP_OPEN', flush=True)
        finally:
            os.umask(old_umask)

    def test_user_presence_guard_keeps_distinct_stop_codes_and_never_repairs_records(self):
        for code in ('EXISTING_ADMIN', 'OTHER_USERS', 'SETUP_CLOSED', 'SEAL_PRESENT', 'AUDIT_PRESENT'):
            self.assertIn('V2_NATIVE_' + code + '_STOP', native.EMPTY_GUARD)
        self.assertNotIn('DELETE', native.EMPTY_GUARD)
        self.assertNotIn('UPDATE', native.EMPTY_GUARD)
        self.assertNotIn('INSERT', native.EMPTY_GUARD)


if __name__ == '__main__':
    unittest.main()
