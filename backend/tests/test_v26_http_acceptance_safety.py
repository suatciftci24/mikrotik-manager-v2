"""Offline checks for the NEW real-HTTP acceptance harness. No socket or DB setup."""
import io
import errno
import os
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.tests import v26_http_acceptance as acceptance


class HttpAcceptanceSafetyTests(TestCase):
    def test_failed_class_setup_preserves_stage_without_emitting_exception_details(self):
        case = Mock(stage=None)
        result = Mock(errors=[(case, 'private exception text')], failures=[])
        previous = acceptance.ACTIVE_ACCEPTANCE_CLASS
        try:
            acceptance.ACTIVE_ACCEPTANCE_CLASS = Mock(stage='POSTGRES_START')
            self.assertEqual(acceptance.failed_acceptance_stage(result), 'POSTGRES_START')
            case.stage = 'HTTP_LISTENER_BIND'
            self.assertEqual(acceptance.failed_acceptance_stage(result), 'HTTP_LISTENER_BIND')
        finally:
            acceptance.ACTIVE_ACCEPTANCE_CLASS = previous

    def test_listener_diagnostic_reports_only_error_class_and_errno(self):
        previous = acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR
        try:
            acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR = {
                'stage': 'HTTP_LISTENER_BIND', 'error_class': 'PermissionError', 'errno': errno.EPERM,
                'errno_name': 'EPERM', 'syscall': 'bind', 'host': '127.0.0.1', 'port': 18996,
            }
            result = Mock(errors=[(Mock(stage=None), 'private path and credential')], failures=[])
            acceptance.ACTIVE_ACCEPTANCE_CLASS = Mock(stage='HTTP_LISTENER_BIND')
            diagnostic = acceptance.failed_acceptance_diagnostic(result)
            self.assertEqual(diagnostic,
                             'stage=HTTP_LISTENER_BIND error_class=PermissionError errno=1 '
                             'errno_name=EPERM syscall=bind host=127.0.0.1 port=18996')
            self.assertNotIn('private', diagnostic)
        finally:
            acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR = previous
            acceptance.ACTIVE_ACCEPTANCE_CLASS = None

    def test_listener_evidence_survives_unittest_stage_mismatch(self):
        previous = acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR
        try:
            acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR = {
                'stage': 'HTTP_LISTENER_BIND', 'error_class': 'PermissionError', 'errno': errno.EPERM,
                'errno_name': 'EPERM', 'syscall': 'bind', 'host': '127.0.0.1', 'port': 18996,
            }
            result = Mock(errors=[(Mock(stage='HTTP_SERVER_START'), 'private')], failures=[])
            diagnostic = acceptance.failed_acceptance_diagnostic(result)
            self.assertEqual(diagnostic,
                             'stage=HTTP_SERVER_START bind_stage=HTTP_LISTENER_BIND '
                             'bind_error_class=PermissionError bind_errno=1 bind_errno_name=EPERM '
                             'bind_syscall=bind bind_host=127.0.0.1 bind_port=18996')
        finally:
            acceptance.ACTIVE_ACCEPTANCE_BIND_ERROR = previous

    def test_explicit_run_and_existing_root_refuse_before_suite(self):
        with patch.object(acceptance, 'acceptance_suite') as suite, \
             redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                acceptance.main([])
            suite.assert_not_called()
        with TemporaryDirectory(prefix='v26-http-preflight-') as folder:
            for root in (Path(folder), Path(folder) / 'alias'):
                if root.name == 'alias':
                    root.symlink_to(Path(folder) / 'missing')
                with patch.object(acceptance, 'ROOT', root), \
                     patch.object(acceptance, 'acceptance_suite') as suite, \
                     redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(acceptance.main(['--run']), 1)
                    self.assertIn('ACCEPTANCE_ROOT_ALREADY_EXISTS', output.getvalue())
                    suite.assert_not_called()

    def test_inherited_database_and_device_credentials_are_not_reused(self):
        original = dict(V2_DATABASE_URL='forbidden-target', V2_CEBECI_API_SSL_PASSWORD_FILE='private',
                        V2_ROUTER_ONBOARDING_ENABLED='true', V2_SESSION_SECURE='true',
                        V2_UNKNOWN_TARGET='private', PGHOST='remote', PGPASSWORD='private', PATH='/usr/bin')
        environment = acceptance.isolated_environment(original)
        self.assertEqual(original['V2_DATABASE_URL'], 'forbidden-target')
        self.assertEqual(environment['PATH'], '/usr/bin')
        self.assertFalse(any(key.startswith('PG') for key in environment))
        self.assertNotIn('V2_CEBECI_API_SSL_PASSWORD_FILE', environment)
        self.assertNotIn('V2_UNKNOWN_TARGET', environment)
        self.assertEqual(environment['V2_ROUTER_ONBOARDING_ENABLED'], 'false')
        self.assertEqual(environment['V2_CEBECI_API_SSL_ENABLED'], 'false')
        self.assertEqual(environment['V2_ROUTER_ONBOARDING_OPERATOR_IDS'], '')
        from app.core.v26_acceptance import validate, ROOT
        self.assertTrue(validate(environment, ROOT))

    def test_client_fixed_target_cookie_and_redirect_never_followed(self):
        connection = Mock()
        response = connection.getresponse.return_value
        response.status = 302
        response.read.return_value = b'{"ok":true}'
        response.getheader.return_value = 'v2_session=synthetic-cookie; HttpOnly; Path=/api; SameSite=Strict'
        client = acceptance.LoopbackClient()
        with patch.object(acceptance.http.client, 'HTTPConnection', return_value=connection) as factory:
            result = client.post('/api/v1/auth/login', json={'username': 'synthetic'})
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result.json()['ok'])
            factory.assert_called_once_with('127.0.0.1', 18996, timeout=5)
            connection.request.assert_called_once()
            connection.close.assert_called_once()
            self.assertEqual(client.cookies, {'v2_session': 'synthetic-cookie'})
            client.get('/api/v1/auth/me')
            self.assertEqual(connection.request.call_args.kwargs['headers']['Cookie'],
                             'v2_session=synthetic-cookie')
            response.getheader.return_value = 'v2_session=""; Max-Age=0; Path=/api'
            client.post('/api/v1/auth/logout')
            self.assertEqual(client.cookies, {})

    def test_client_rejects_foreign_paths_and_never_retries_uncertain_post(self):
        client = acceptance.LoopbackClient()
        with patch.object(acceptance.http.client, 'HTTPConnection') as factory:
            for path in ('https://remote/api/auth', '//remote/api/auth', '/api/x\r\nheader: value',
                         '/api/x\\remote', '/api/x#fragment'):
                with self.assertRaises(acceptance.AcceptanceBlocked):
                    client.get(path)
            factory.assert_not_called()
            factory.return_value.request.side_effect = TimeoutError('synthetic timeout')
            with self.assertRaises(TimeoutError):
                client.post('/api/v1/subscriber-workspace', json={'request_id': 'synthetic'})
            factory.assert_called_once()
            factory.return_value.request.assert_called_once()
            factory.return_value.close.assert_called_once()

    def test_only_new_scenario_selected_and_bind_failure_precedes_pg_setup(self):
        from backend.tests.test_v26_identity_postgres import V26IdentityPostgres
        suite = acceptance.acceptance_suite()
        self.assertEqual(suite.countTestCases(), 1)
        case = next(iter(suite))
        self.assertEqual(case._testMethodName, 'test_new_real_http_acceptance')
        cls = type(case)
        with patch('socket.socket') as socket, \
             patch.object(V26IdentityPostgres, 'setUpClass') as setup:
            socket.return_value.bind.side_effect = PermissionError(errno.EPERM, 'synthetic private path')
            try:
                with self.assertRaises(PermissionError):
                    cls.setUpClass()
                socket.return_value.bind.assert_called_once_with(('127.0.0.1', 18996))
                socket.return_value.listen.assert_not_called()
                setup.assert_not_called()
                diagnostic = acceptance.failed_acceptance_diagnostic(
                    Mock(errors=[(Mock(stage=None), 'private')], failures=[]))
                self.assertEqual(diagnostic,
                                 'stage=HTTP_LISTENER_BIND error_class=PermissionError errno=1 '
                                 'errno_name=EPERM syscall=bind host=127.0.0.1 port=18996')
            finally:
                cls.doClassCleanups()
            socket.return_value.close.assert_called_once()

    def test_socket_creation_failure_is_captured_with_fixed_loopback_target(self):
        from backend.tests.test_v26_identity_postgres import V26IdentityPostgres
        cls = type(next(iter(acceptance.acceptance_suite())))
        failure = PermissionError(errno.EPERM, 'synthetic socket restriction')
        with patch('socket.socket', side_effect=failure) as socket_factory, \
             patch.object(V26IdentityPostgres, 'setUpClass') as setup:
            try:
                with self.assertRaises(PermissionError):
                    cls.setUpClass()
                socket_factory.assert_called_once()
                setup.assert_not_called()
                diagnostic = acceptance.failed_acceptance_diagnostic(
                    Mock(errors=[(Mock(stage=None), 'private')], failures=[]))
                self.assertEqual(diagnostic,
                                 'stage=HTTP_LISTENER_BIND error_class=PermissionError errno=1 '
                                 'errno_name=EPERM syscall=socket host=127.0.0.1 port=18996')
            finally:
                cls.doClassCleanups()

    def test_database_port_conflict_blocks_before_cluster_setup(self):
        from backend.tests.test_v26_identity_postgres import V26IdentityPostgres
        cls = type(next(iter(acceptance.acceptance_suite())))
        http_socket, database_socket = Mock(), Mock()
        database_socket.bind.side_effect = OSError(errno.EADDRINUSE, 'private service details')
        with patch('socket.socket', side_effect=[http_socket, database_socket]), \
             patch.object(V26IdentityPostgres, 'setUpClass') as setup:
            try:
                with self.assertRaises(OSError):
                    cls.setUpClass()
                http_socket.bind.assert_called_once_with(('127.0.0.1', 18996))
                http_socket.listen.assert_called_once_with(128)
                database_socket.bind.assert_called_once_with(('127.0.0.1', 55433))
                setup.assert_not_called()
                result = Mock(errors=[(Mock(stage=None), 'private')], failures=[])
                self.assertEqual(acceptance.failed_acceptance_diagnostic(result),
                                 'stage=POSTGRES_LISTENER_RESERVE error_class=OSError errno=98 '
                                 'errno_name=EADDRINUSE syscall=bind host=127.0.0.1 port=55433')
            finally:
                cls.doClassCleanups()
        http_socket.close.assert_called_once()
        database_socket.close.assert_called_once()

    def test_preflight_rejects_wrong_cwd_owner_or_missing_tools_without_sockets(self):
        with patch.object(acceptance.Path, 'cwd', return_value=Path('/')), \
             self.assertRaisesRegex(acceptance.AcceptanceBlocked, 'LOCAL_REPO_OWNER_REQUIRED'):
            acceptance.preflight()
        with patch.object(acceptance.os, 'geteuid', return_value=0), \
             self.assertRaisesRegex(acceptance.AcceptanceBlocked, 'LOCAL_REPO_OWNER_REQUIRED'):
            acceptance.preflight()
        with patch.object(acceptance.os.path, 'lexists', return_value=False), \
             patch.object(acceptance.os, 'access', return_value=False), \
             self.assertRaisesRegex(acceptance.AcceptanceBlocked, 'POSTGRESQL16_TOOLS_REQUIRED'):
            acceptance.preflight()

    def test_browser_callback_is_attached_to_the_real_http_acceptance_case(self):
        callback = Mock()
        suite = acceptance.acceptance_suite(during_acceptance=callback)
        self.assertEqual(suite.countTestCases(), 1)
        case = next(iter(suite))
        self.assertIs(type(case).during_acceptance, callback)
        source = Path(acceptance.__file__).read_text()
        verify = source.index('verify_owned_acceptance_database(connection, self.store)')
        browser = source.index('self.during_acceptance()')
        self.assertLess(verify, browser)

    def test_browser_only_suite_selects_readiness_diagnostic_not_http_acceptance(self):
        callback = Mock()
        suite = acceptance.acceptance_suite(during_acceptance=callback, browser_only=True)
        self.assertEqual(suite.countTestCases(), 1)
        case = next(iter(suite))
        self.assertEqual(case._testMethodName, 'test_browser_only_diagnostic')
        self.assertIs(type(case).during_acceptance, callback)
        self.assertTrue(type(case).browser_only)

    def test_browser_start_requires_revalidated_owned_database_and_select_one(self):
        connection, store = Mock(), Mock()
        connection.execute.return_value.scalar_one.return_value = 1
        acceptance.verify_owned_acceptance_database(connection, store)
        store._check.assert_called_once_with(connection)
        self.assertEqual(str(connection.execute.call_args.args[0]), 'SELECT 1')
        connection.execute.return_value.scalar_one.return_value = 0
        with self.assertRaisesRegex(acceptance.AcceptanceBlocked, 'OWN_DISPOSABLE_DATABASE_NOT_READY'):
            acceptance.verify_owned_acceptance_database(connection, store)
