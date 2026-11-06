"""Offline checks for the NEW real-HTTP acceptance harness. No socket or DB setup."""
import io
import os
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.tests import v26_http_acceptance as acceptance


class HttpAcceptanceSafetyTests(TestCase):
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
            socket.return_value.bind.side_effect = PermissionError('synthetic denial')
            try:
                with self.assertRaises(PermissionError):
                    cls.setUpClass()
                socket.return_value.bind.assert_called_once_with(('127.0.0.1', 18996))
                socket.return_value.listen.assert_not_called()
                setup.assert_not_called()
            finally:
                cls.doClassCleanups()
            socket.return_value.close.assert_called_once()

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
