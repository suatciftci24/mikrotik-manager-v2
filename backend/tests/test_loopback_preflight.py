"""Focused coverage of the early local HTTP gate without real sockets or processes."""
from contextlib import redirect_stdout, redirect_stderr
import errno
import os
from io import StringIO
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app import demo_api_runner, loopback_preflight
from backend.tests import v26_http_acceptance


class LoopbackPreflightTests(TestCase):
    def test_permission_failure_blocks_and_fresh_environment_can_proceed(self):
        with patch.object(loopback_preflight.socket, 'socket') as socket_factory, redirect_stderr(StringIO()) as output:
            endpoint = socket_factory.return_value
            socket_factory.side_effect = [PermissionError(errno.EPERM, 'private detail'), endpoint]
            self.assertEqual(loopback_preflight.main(), 1)
            self.assertIn('LOOPBACK_SOCKET_PERMISSION_DENIED', output.getvalue())
            self.assertIn('errno=EPERM', output.getvalue())
            self.assertNotIn('private detail', output.getvalue())
            self.assertEqual(loopback_preflight.main(), 0)
            endpoint.__exit__.assert_called_once()
            endpoint.bind.assert_not_called()
            endpoint.connect.assert_not_called()
            self.assertEqual(socket_factory.call_count, 2)

    def test_new_socket_error_keeps_its_own_diagnostic(self):
        with patch.object(loopback_preflight.socket, 'socket', side_effect=OSError(errno.EMFILE, 'private')):
            blocker = loopback_preflight.socket_blocker()
            self.assertIn('LOOPBACK_SOCKET_ERROR', blocker)
            self.assertIn('errno=EMFILE', blocker)

    def test_browser_gate_blocks_before_managing_api_or_launching_chromium(self):
        with patch.object(demo_api_runner, 'socket_blocker', return_value='LOOPBACK_SOCKET_PERMISSION_DENIED') as probe, \
             patch.object(demo_api_runner, 'ManagedAPI') as api, \
             patch.object(demo_api_runner.subprocess, 'run') as worker, redirect_stderr(StringIO()) as output:
            self.assertEqual(demo_api_runner.main(['--browser']), 1)
            self.assertIn('LOOPBACK_SOCKET_PERMISSION_DENIED', output.getvalue())
            probe.assert_called_once()
            api.assert_not_called()
            worker.assert_not_called()

    def test_isolated_acceptance_stops_before_dependency_or_fixture_setup(self):
        source = Mock(spec=Path)
        source.stat.return_value.st_uid = 1000
        environment = SimpleNamespace(getuid=lambda:1000, geteuid=lambda:1000,
                                      path=os.path, access=lambda *_:True, X_OK=os.X_OK,
                                      pidfd_open=Mock())
        with TemporaryDirectory() as folder, \
             patch.object(v26_http_acceptance, 'ROOT', Path(folder) / 'unused'), \
             patch.object(v26_http_acceptance, 'SOURCE', source), \
             patch.object(Path, 'cwd', return_value=source), \
             patch.object(v26_http_acceptance, 'os', environment), \
             patch.object(loopback_preflight, 'socket_blocker', return_value='LOOPBACK_SOCKET_PERMISSION_DENIED'), \
             patch.object(v26_http_acceptance.import_diagnostic, 'check_dependencies') as dependencies, \
             patch.object(v26_http_acceptance, 'acceptance_suite') as suite, redirect_stdout(StringIO()) as output:
            self.assertEqual(v26_http_acceptance.main(['--run']), 1)
            self.assertIn('LOOPBACK_SOCKET_PERMISSION_DENIED', output.getvalue())
            dependencies.assert_not_called()
            suite.assert_not_called()

    def test_dev_gate_stops_before_bootstrap(self):
        source = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copyfile(source / 'dev.sh', root / 'dev.sh')
            (root / 'tools').mkdir()
            (root / 'tools/local-terminal-target.sh').write_text('require_local_terminal_target() { return 0; }\nrequire_local_demo_environment() { return 0; }\n')
            for name, script in {
                'python3': 'test "$*" = "-B -m app.loopback_preflight" || exit 97; echo "BLOCKED: errno=EPERM" >&2; exit 1',
            }.items():
                tool = root / name
                tool.write_text(f'#!/bin/sh\n{script}\n')
                tool.chmod(0o700)
            result = subprocess.run(['/bin/bash', 'dev.sh'], cwd=root,
                                    env={'PATH': f'{root}:/usr/bin:/bin'},
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertIn('BLOCKED: errno=EPERM', result.stderr)
            self.assertFalse((root / '.venv').exists())
            self.assertFalse((root / '.local').exists())
