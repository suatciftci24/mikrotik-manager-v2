"""Filesystem/secret behavior of the one-shot operator helper; no DB/network."""
import importlib.util
import os
from pathlib import Path
import tempfile
import subprocess
import errno
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot'
spec = importlib.util.spec_from_file_location('office_completion', PACKAGE / 'complete-office.py')
office = importlib.util.module_from_spec(spec)
spec.loader.exec_module(office)


class AdminCompletionSafetyTests(unittest.TestCase):
    def setUp(self):
        # Every export test is offline, including the socket capability preflight.
        self.socket_patch = patch.object(office, 'require_tcp_socket')
        self.socket_patch.start()
        self.addCleanup(self.socket_patch.stop)

    def test_private_file_rejects_symlink_hardlink_and_public_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'secret'
            path.write_text('synthetic')
            path.chmod(0o600)
            office.private(path)
            link = Path(temp) / 'link'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                office.private(link)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(RuntimeError):
                office.private(path)
            link.unlink()
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                office.private(path)

    def test_export_passfile_is_private_no_password_argv_and_removed_on_failure(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.local').mkdir()
            os.chdir(root)
            url = 'postgresql+psycopg://v2_local:SYNTHETIC%3Apassword@127.0.0.1:55432/mikrotik_manager_v2'
            checked = []
            def failed_psql(args, env):
                checked.append(True)
                self.assertNotIn('SYNTHETIC', ' '.join(args))
                self.assertNotIn('PGPASSWORD', env)
                self.assertNotIn('PGSERVICE', env)
                path = Path(env['PGPASSFILE'])
                office.private(path)
                self.assertIn('SYNTHETIC\\:password', path.read_text())
                raise RuntimeError('synthetic failure')
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run', failed_psql), patch.object(
                        office.Path, 'home', return_value=root), patch.dict(
                        os.environ, {'V2_DATABASE_URL': url, 'PGPASSWORD': 'ignored', 'PGSERVICE': 'ignored'}, clear=True):
                    with self.assertRaises(RuntimeError):
                        office.export()
                self.assertEqual(checked, [True])
                self.assertEqual(list((root / '.local/admin-transfer').iterdir()), [])
            finally:
                os.chdir(before)

    def test_foreign_database_rejected_before_export(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.chdir(root)
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run') as command, patch.dict(
                        os.environ, {'V2_DATABASE_URL': 'postgresql+psycopg://v2_local:x@127.0.0.1:5432/v1'}):
                    with self.assertRaisesRegex(office.SafeFailure, '^V2_EXPORT_TARGET_REJECTED$'):
                        office.export()
                    command.assert_not_called()
            finally:
                os.chdir(before)

    def test_psql_failures_print_only_fixed_codes(self):
        cases = (
            (b'could not create socket: Operation not permitted', 'V2_EXPORT_SOCKET_EPERM'),
            (b'connection refused', 'V2_EXPORT_CONNECTION_REFUSED'),
            (b'FATAL: password authentication failed', 'V2_EXPORT_DB_AUTH_FAILED'),
            (b'fe_sendauth: no password supplied', 'V2_EXPORT_PGPASS_NO_MATCH'),
            (b'ERROR: relation "synthetic" does not exist', 'V2_EXPORT_SOURCE_SCHEMA_MISSING'),
            (b'psql:source:33: ERROR:  V2_ADMIN_SOURCE_ACCOUNT_NOT_FOUND', 'V2_EXPORT_SOURCE_ACCOUNT_NOT_FOUND'),
            (b'psql:source:33: ERROR:  V2_ADMIN_SOURCE_SEAL_REJECTED', 'V2_EXPORT_SOURCE_SEAL_REJECTED'),
            (b'unknown server error', 'V2_EXPORT_CONNECTION_FAILED'),
        )
        for message, expected in cases:
            with self.subTest(expected=expected):
                result = subprocess.CompletedProcess(['psql'], 2, stdout=b'SYNTHETIC_SECRET',
                    stderr=message + b' DSN=SYNTHETIC_SECRET password_hash=SYNTHETIC_SECRET')
                with patch.object(office.subprocess, 'run', return_value=result):
                    with self.assertRaises(office.SafeFailure) as error:
                        office.run(['/usr/lib/postgresql/16/bin/psql'])
                self.assertEqual(office.failure_code(error.exception), expected)
                self.assertNotIn('SYNTHETIC_SECRET', str(error.exception))

    def test_socket_denial_classified_without_server_connection(self):
        # Bypass setUp's stub to exercise the real capability check, no socket is opened.
        spec2 = importlib.util.spec_from_file_location('office_socket_check', PACKAGE / 'complete-office.py')
        module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(module)
        for number, expected in ((errno.EPERM, 'V2_EXPORT_SOCKET_EPERM'), (errno.EACCES, 'V2_EXPORT_SOCKET_DENIED')):
            with patch.object(module.socket, 'socket', side_effect=OSError(number, 'SYNTHETIC_SECRET')):
                with self.assertRaises(module.SafeFailure) as error:
                    module.require_tcp_socket()
                self.assertEqual(module.failure_code(error.exception), expected)

    def test_socket_preflight_stops_before_psql_and_secret_artifact_creation(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.local').mkdir()
            os.chdir(root)
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run') as command, patch.dict(
                        os.environ, {'V2_DATABASE_URL': 'postgresql+psycopg://v2_local@127.0.0.1:55432/mikrotik_manager_v2'}, clear=True), patch.object(
                        office, 'require_tcp_socket', side_effect=office.SafeFailure('V2_EXPORT_SOCKET_EPERM')):
                    with self.assertRaisesRegex(office.SafeFailure, '^V2_EXPORT_SOCKET_EPERM$'):
                        office.export()
                    command.assert_not_called()
                self.assertEqual(list((root / '.local/admin-transfer').iterdir()), [])
            finally:
                os.chdir(before)

    def test_existing_passfile_without_url_password_is_preserved(self):
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '.local').mkdir()
            passfile = root / '.pgpass'
            passfile.write_text('synthetic-private-passfile')
            passfile.chmod(0o600)
            os.chdir(root)
            def failed_psql(args, env):
                self.assertEqual(env['PGPASSFILE'], str(passfile))
                self.assertEqual(env['LC_ALL'], 'C')
                self.assertIn('default_transaction_read_only=on', env['PGOPTIONS'])
                raise office.SafeFailure('V2_EXPORT_DB_AUTH_FAILED')
            try:
                with patch.object(office, 'ROOT', root), patch.object(office, 'run', failed_psql), patch.dict(
                        os.environ, {'V2_DATABASE_URL': 'postgresql+psycopg://v2_local@127.0.0.1:55432/mikrotik_manager_v2',
                                     'PGPASSFILE': str(passfile)}, clear=True):
                    with self.assertRaisesRegex(office.SafeFailure, '^V2_EXPORT_DB_AUTH_FAILED$'):
                        office.export()
                self.assertEqual(passfile.read_text(), 'synthetic-private-passfile')
                self.assertEqual(list((root / '.local/admin-transfer').iterdir()), [])
            finally:
                os.chdir(before)


if __name__ == '__main__':
    unittest.main()
