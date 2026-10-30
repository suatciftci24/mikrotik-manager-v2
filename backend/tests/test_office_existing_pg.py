"""Only synthetic cluster files and mocked processes/sockets; never start PostgreSQL."""
import contextlib
import errno
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / 'deploy/cebeci-v2-pilot/complete-office.py'
spec = importlib.util.spec_from_file_location('existing_pg_office', SCRIPT)
office = importlib.util.module_from_spec(spec)
spec.loader.exec_module(office)


class ExistingOfficeClusterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / '.local/postgres-v2-demo'
        self.data.mkdir(parents=True, mode=0o700)
        (self.data / 'global').mkdir()
        (self.root / '.local/postgres-v2-socket').mkdir()
        for name in ('PG_VERSION', 'global/pg_control', 'postgresql.conf', 'postgresql.auto.conf', 'pg_hba.conf', 'pg_ident.conf'):
            (self.data / name).write_text('16' if name == 'PG_VERSION' else '')
        before = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, before)
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(office, 'ROOT', self.root))
        self.capability = self.patches.enter_context(patch.object(office, 'require_tcp_socket'))
        self.socket = self.patches.enter_context(patch.object(office.socket, 'socket'))
        self.command = self.patches.enter_context(patch.object(office, 'run', side_effect=self.config_value))
        self.process = self.patches.enter_context(patch.object(office.subprocess, 'run'))

    def config_value(self, args, **kwargs):
        setting = args[-1]
        return {'data_directory': str(self.data), 'hba_file': str(self.data / 'pg_hba.conf'),
                'ident_file': str(self.data / 'pg_ident.conf'), 'archive_mode': 'off'}.get(setting, '').encode()

    def test_stopped_existing_cluster_started_once_on_exact_target(self):
        self.process.side_effect = [subprocess.CompletedProcess([], 3), subprocess.CompletedProcess([], 0)]
        with contextlib.redirect_stdout(io.StringIO()):
            office.start_existing_v2()
        calls = self.process.call_args_list
        self.assertEqual(len(calls), 2)
        start = calls[1].args[0]
        self.assertEqual(start[-1], 'start')
        self.assertEqual(start[start.index('-D') + 1], str(self.data))
        options = start[start.index('-o') + 1]
        self.assertIn('-h 127.0.0.1 -p 55432', options)
        self.assertIn('log_parameter_max_length_on_error=0', options)
        self.assertNotIn('initdb', str(calls))
        self.assertNotIn('systemctl', str(calls))
        self.assertEqual((self.root / '.local/admin-transfer/postgres-start.log').stat().st_mode & 0o777, 0o600)

    def test_running_cluster_is_not_restarted(self):
        (self.data / 'postmaster.pid').write_text('123\nready\n')
        self.process.return_value = subprocess.CompletedProcess([], 0)
        office.start_existing_v2()
        self.assertEqual(self.process.call_count, 1)
        self.socket.assert_not_called()

    def test_socket_eperm_prevents_process_calls_and_log_artifacts(self):
        self.capability.side_effect = office.SafeFailure('V2_EXPORT_SOCKET_EPERM')
        with self.assertRaisesRegex(office.SafeFailure, '^V2_EXPORT_SOCKET_EPERM$'):
            office.start_existing_v2()
        self.command.assert_not_called()
        self.process.assert_not_called()
        self.assertFalse((self.root / '.local/admin-transfer').exists())

    def test_occupied_port_does_not_start_or_stop_any_process(self):
        self.process.return_value = subprocess.CompletedProcess([], 3)
        self.socket.return_value.__enter__.return_value.bind.side_effect = OSError(errno.EADDRINUSE, 'synthetic')
        with self.assertRaisesRegex(office.SafeFailure, '^V2_START_PORT_OCCUPIED$'):
            office.start_existing_v2()
        self.assertEqual(self.process.call_count, 1)

    def test_redirected_data_directory_rejected_before_status_or_start(self):
        self.command.return_value = b'/synthetic/foreign-cluster'
        self.command.side_effect = None
        with self.assertRaisesRegex(office.SafeFailure, '^V2_START_CONFIG_REJECTED$'):
            office.start_existing_v2()
        self.process.assert_not_called()

    def test_symlink_cluster_and_external_includes_rejected(self):
        (self.data / 'postgresql.conf').write_text("include_dir = '/synthetic/foreign'\n")
        with self.assertRaisesRegex(office.SafeFailure, '^V2_START_EXTERNAL_CONFIG_REJECTED$'):
            office.start_existing_v2()
        self.capability.assert_not_called()
        (self.data / 'postgresql.conf').unlink()
        (self.data / 'postgresql.conf').symlink_to(self.data / 'pg_hba.conf')
        with self.assertRaisesRegex(office.SafeFailure, '^V2_START_CLUSTER_FILE_UNSAFE$'):
            office.start_existing_v2()
        self.process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
