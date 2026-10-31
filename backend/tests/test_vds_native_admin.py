"""Native VDS setup safety boundaries; synthetic records, no PostgreSQL or network."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import unittest
import os
import pty
from types import SimpleNamespace
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot'
spec = importlib.util.spec_from_file_location('native_admin_test', PACKAGE / 'native-admin.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeAdminTests(unittest.TestCase):
    def test_tty_wrapper_supports_nonseekable_terminal_without_echo_fallback(self):
        master, slave = pty.openpty()
        try:
            with patch.object(native.os, 'open', return_value=os.dup(slave)):
                with native.open_tty() as terminal:
                    self.assertTrue(terminal.isatty())
                    self.assertFalse(terminal.seekable())
                    terminal.write('SYNTHETIC_PROMPT')
                    self.assertEqual(os.read(master, 1024), b'SYNTHETIC_PROMPT')
        finally:
            os.close(master)
            os.close(slave)

    def test_full_completion_with_existing_admin_stops_before_source_or_dependencies(self):
        old_umask = os.umask(0o077)
        try:
            with patch.object(native.deploy.os, 'geteuid', return_value=0), patch.object(
                    native.deploy.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1001, pw_gid=1001)), patch.object(
                    native.deploy, 'safe'), patch.object(native.deploy, 'sql', return_value=subprocess.CompletedProcess([], 0, stdout=b't\n')) as sql, patch.object(
                    native.deploy, 'run') as command, patch.object(Path, 'read_bytes', side_effect=AssertionError('source must not be read')):
                with self.assertRaises(RuntimeError):
                    native.deploy.main(Path('/home/mikadmin/v2-complete.synthetic'), native=native)
                self.assertEqual(sql.call_count, 2)
                command.assert_not_called()
                self.assertEqual(native.deploy.STEP, 'native-existing-admin-stop-no-changes')
        finally:
            os.umask(old_umask)

    def test_existing_admin_stops_read_only_without_second_query_or_writes(self):
        with patch.object(native.deploy, 'sql', return_value=subprocess.CompletedProcess([], 0, stdout=b't\n')) as query:
            with self.assertRaises(RuntimeError):
                native.require_empty()
        self.assertEqual(query.call_count, 1)
        self.assertIn('BEGIN READ ONLY', query.call_args.args[0])
        self.assertNotIn('INSERT', query.call_args.args[0])
        self.assertEqual(native.deploy.STEP, 'native-existing-admin-stop-no-changes')

    def test_no_admin_requires_empty_unsealed_store_read_only(self):
        with patch.object(native.deploy, 'sql', return_value=subprocess.CompletedProcess([], 0, stdout=b'f\n')) as query:
            native.require_empty()
        self.assertEqual(query.call_count, 2)
        self.assertTrue(all(call.args[0].startswith('BEGIN READ ONLY') for call in query.call_args_list))
        self.assertIn('NOT first_admin_initialized', query.call_args.args[0])

    def test_atomic_creation_rechecks_under_lock_and_does_not_audit_hash(self):
        record = dict(id='v2-user-synthetic', username='suatciftci', name="Synthetic '$$ Name", email='fixture@example.test',
            password_hash='SYNTHETIC_HASH_CANARY', permissions={'demo-router-001': {'can_view': True}},
            active=True, account_origin='LOCAL', role='ADMIN', revision=0)
        sql = native.creation_sql(record, 1000)
        self.assertLess(sql.index('pg_advisory_xact_lock'), sql.index('FOR UPDATE'))
        self.assertLess(sql.index('V2_NATIVE_EXISTING_ADMIN_STOP'), sql.index('INSERT INTO v2_demo.users'))
        self.assertNotIn('SYNTHETIC_HASH_CANARY', sql.split('INSERT INTO v2_demo.user_audit')[1])
        self.assertIn("Synthetic ''$$ Name", sql)
        self.assertTrue(sql.endswith('COMMIT;'))
        self.assertNotIn('CREATE TABLE', sql)
        self.assertNotIn('UPDATE v2_demo.users', sql)

    def test_login_secret_cleared_even_if_http_verification_fails(self):
        native._login_password = 'SYNTHETIC_SECRET_CANARY'
        with patch('urllib.request.OpenerDirector.open', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                native.verify_login()
        self.assertIsNone(native._login_password)

    def test_installer_launcher_python_is_valid_and_contains_no_office_export(self):
        spec = importlib.util.spec_from_file_location('native_builder_test', PACKAGE / 'build-native-installer.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        body = builder.LAUNCHER.split("<<'V2_PYTHON'\n", 1)[1].split('\nV2_PYTHON\n', 1)[0]
        ast.parse(body)
        self.assertNotIn('export-admin', body)
        self.assertNotIn('admin-transfer.jsonl', body)


if __name__ == '__main__':
    unittest.main()
