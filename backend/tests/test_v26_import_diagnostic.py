"""Socketless import/dependency diagnostics; no acceptance fixture is started."""
import io
from contextlib import redirect_stdout
import importlib
import sys
import unittest
from unittest.mock import Mock, patch

from backend.tests import v26_http_acceptance as harness
from backend.tests import v26_import_diagnostic as diagnostic


class ImportDiagnosticTests(unittest.TestCase):
    def test_missing_pillow_is_detected_by_preflight_before_resources(self):
        def load(name):
            if name == 'PIL':
                raise ModuleNotFoundError('private password DSN', name='PIL')
            return Mock()
        with patch.object(diagnostic.importlib, 'import_module', side_effect=load), \
             patch.object(harness.os.path, 'lexists', return_value=False), \
             patch.object(harness.os, 'access', return_value=True), \
             patch('socket.socket') as sockets, patch('subprocess.Popen') as process:
            with self.assertRaisesRegex(harness.AcceptanceBlocked, 'dependency=Pillow') as caught:
                harness.preflight()
            self.assertNotIn('private', str(caught.exception))
            sockets.assert_not_called()
            process.assert_not_called()

    def test_pillow_binary_extension_is_checked(self):
        def load(name):
            if name == 'PIL.Image':
                raise ImportError('private /home/user/path')
            return Mock()
        with patch.object(diagnostic.importlib, 'import_module', side_effect=load):
            with self.assertRaisesRegex(diagnostic.DependencyUnavailable, 'dependency=Pillow') as caught:
                diagnostic.check_dependencies()
        self.assertNotIn('/home', str(caught.exception))
        self.assertIn('error_class=ImportError', str(caught.exception))

    def test_real_import_failure_metadata_survives_unittest_wrapping(self):
        previous = diagnostic.LAST_IMPORT_FAILURE
        self.addCleanup(setattr, diagnostic, 'LAST_IMPORT_FAILURE', previous)
        try:
            with diagnostic.capture_import_failure():
                raise ModuleNotFoundError('secret postgresql://user:password', name='PIL')
        except ModuleNotFoundError:
            pass
        with patch.object(harness, 'ACTIVE_ACCEPTANCE_CLASS', Mock(stage='ISOLATED_ENGINE_AND_APP_IMPORT')):
            result = Mock(errors=[(Mock(stage=None), 'private traceback')], failures=[])
            message = harness.failed_acceptance_diagnostic(result)
        self.assertIn('missing_dependency=Pillow', message)
        self.assertIn('error_class=ModuleNotFoundError', message)
        self.assertNotIn('secret', message)
        self.assertNotIn('password', message)
        self.assertNotIn('/home/', message)

    def test_unknown_missing_module_and_dynamic_error_class_are_not_echoed(self):
        message = diagnostic.details(ModuleNotFoundError('secret', name='secret_module'))
        self.assertNotIn('secret', message)
        message = diagnostic.details(type('SecretPassword', (Exception,), {})('private'))
        self.assertEqual(message, 'error_class=OtherError')

    def test_import_only_failure_does_not_invoke_acceptance_or_preflight(self):
        output = io.StringIO()
        failure = diagnostic.DependencyUnavailable('Pillow', ModuleNotFoundError('private', name='PIL'))
        with patch.dict(sys.modules):
            sys.modules.pop('app.main', None)
            with patch.object(diagnostic, 'check_dependencies', side_effect=failure), \
                 patch.object(harness, 'preflight') as preflight, \
                 patch.object(harness, 'acceptance_suite') as suite, redirect_stdout(output):
                self.assertEqual(harness.main(['--import-only']), 1)
        self.assertIn('dependency=Pillow', output.getvalue())
        self.assertNotIn('private', output.getvalue())
        preflight.assert_not_called()
        suite.assert_not_called()

    def test_import_only_blocks_socket_database_and_process_creation(self):
        import socket
        import subprocess
        import psycopg
        from sqlalchemy.engine import Engine
        attempts = []
        def load():
            for operation in (lambda: socket.socket(),
                              lambda: Engine.connect(Mock()),
                              lambda: psycopg.connect('secret'),
                              lambda: subprocess.Popen(['not-a-real-command'])):
                with self.assertRaises(harness.AcceptanceBlocked):
                    operation()
                attempts.append(True)
        output = io.StringIO()
        previous = diagnostic.LAST_IMPORT_FAILURE
        self.addCleanup(setattr, diagnostic, 'LAST_IMPORT_FAILURE', previous)
        with patch.dict(sys.modules):
            sys.modules.pop('app.main', None)
            with patch.object(diagnostic, 'check_dependencies'), \
                 patch.object(diagnostic, 'import_application_graph', side_effect=load), \
                 redirect_stdout(output):
                self.assertEqual(harness.main(['--import-only']), 0)
        self.assertEqual(len(attempts), 4)
        self.assertIn('imports only', output.getvalue())
