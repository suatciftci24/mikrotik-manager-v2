"""Offline response-contract and diagnostic regressions. Never open sockets or a DB."""
import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend.tests import v26_http_acceptance as transport
from backend.tests import v26_test001_http as acceptance


class Test001HttpSafety(unittest.TestCase):
    def response(self):
        connection = Mock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b'{"password":"never-print-body"}'
        connection.getresponse.return_value.getheader.return_value = ''
        with patch.object(transport.http.client, 'HTTPConnection', return_value=connection):
            return transport.LoopbackClient().post('/api/v1/subscriber-workspace/management/execute')

    def action_contract(self, response):
        # Execute the original four subtest prefixes through their HTTP-status assertion.
        # All fixture/DB/network inputs are inert doubles; no application import needed.
        path = Path(__file__).with_name('test_v26_test001_acceptance.py')
        tree = ast.parse(path.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Test001Workspace')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and
                      n.name == 'test_four_actions_api_database_detail_audit_and_replay')
        loop = next(n for n in method.body if isinstance(n, ast.For))
        subtest = next(n for n in loop.body if isinstance(n, ast.With))
        index = next(i for i, n in enumerate(subtest.body) if isinstance(n, ast.Expr) and
                     isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and
                     n.value.func.attr == 'assertEqual')
        subtest.body = subtest.body[:index + 1]
        module = ast.Module(body=[method], type_ignores=[])
        namespace = {}
        exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
        class ContractCase(unittest.TestCase):
            stage = 'ACTION_CONTRACT'
            test_actions = namespace[method.name]
            def prepare(self):
                self.item = {'id': 'synthetic-id'}
                self.workspace = SimpleNamespace(detail=lambda _: SimpleNamespace(item=None))
                self.path = '/api/v1/subscriber-workspace/management/execute'
                self.headers = {}
                self.client = SimpleNamespace(post=lambda *a, **k: response)
            def snapshot(self):
                return None
            def payload(self, *a, **k):
                return {}
        case = ContractCase('test_actions')
        result = acceptance.DiagnosticResult(ContractCase)
        case.run(result)
        return result

    def test_original_missing_text_reproduces_exactly_four_errors_with_actual_causes(self):
        result = self.action_contract(SimpleNamespace(status_code=200))
        self.assertEqual(len(result.errors), 4)
        self.assertEqual(len(result.diagnostics), 4)
        for diagnostic, operation in zip(result.diagnostics, ('EXTEND', 'PLAN', 'STATUS', 'STATUS')):
            self.assertIn('AttributeError', diagnostic)
            self.assertIn("attribute 'text'", diagnostic)
            self.assertIn('stage=TEST001_' + operation, diagnostic)
            self.assertIn('operation=', diagnostic)
            self.assertIn('test_v26_test001_acceptance.py:', diagnostic)
            self.assertNotIn('FIXTURE_OR_SCENARIO', diagnostic)

    def test_real_transport_response_satisfies_all_four_existing_assertions(self):
        response = self.response()
        self.assertEqual(response.json(), {'password': 'never-print-body'})
        self.assertIn('HTTP status=200', response.text)
        self.assertNotIn('never-print-body', response.text)
        result = self.action_contract(response)
        self.assertTrue(result.wasSuccessful(), result.diagnostics)
        self.assertEqual(result.diagnostics, [])

    def test_postgresql16_discovery_accepts_ubuntu_packaging_suffix_without_running_tools(self):
        with patch.object(acceptance.shutil, 'which', side_effect=lambda name: '/tmp/bin/initdb' if name == 'initdb' else None), \
             patch.object(acceptance.Path, 'glob', return_value=[]), \
             patch.object(acceptance.os, 'access', return_value=True), \
             patch.object(acceptance.subprocess, 'run', return_value=SimpleNamespace(
                 returncode=0, stdout='postgres (PostgreSQL) 16.10 (Ubuntu 16.10-1.pgdg24.04+1)')) as run:
            self.assertEqual(acceptance.discover_pg(), Path('/tmp/bin'))
            run.assert_called_once()
            run.return_value.stdout = 'postgres (PostgreSQL) 17.6 (Ubuntu build)'
            with self.assertRaises(transport.AcceptanceBlocked):
                acceptance.discover_pg()

    def test_fixture_and_cleanup_holders_keep_exception_and_stage(self):
        result = acceptance.DiagnosticResult(SimpleNamespace(stage='POSTGRES_CONNECT_AND_DEMO_SCHEMA'))
        try:
            raise OSError(13, 'Permission denied')
        except OSError as error:
            import sys
            result.addError(unittest.suite._ErrorHolder('setUpClass'), sys.exc_info())
        self.assertIn('POSTGRES_CONNECT_AND_DEMO_SCHEMA', result.diagnostics[0])
        self.assertIn('Permission denied', result.diagnostics[0])
        self.assertIn('PermissionError', result.diagnostics[0])

    def test_diagnostics_redact_credentials_urls_cookies_and_sql_parameters(self):
        cls = SimpleNamespace(password='private-pg-secret', client=SimpleNamespace(cookies={'v2_session': 'cookie-value'}))
        error = RuntimeError('password=private-pg-secret token=private-token cookie-value '
                             'postgresql+psycopg://user:private-pass@127.0.0.1/db')
        message = acceptance.safe_diagnostic(error, cls)
        for value in ('private-pg-secret', 'private-token', 'cookie-value', 'private-pass'):
            self.assertNotIn(value, message)
        sql = RuntimeError('statement and parameters containing private-pass')
        sql.orig = SimpleNamespace(sqlstate='42P01', diag=SimpleNamespace(
            message_primary='relation does not exist', schema_name='v2_subscriber_workspace',
            table_name='events', constraint_name=None))
        message = acceptance.safe_diagnostic(sql, cls)
        self.assertIn('42P01', message)
        self.assertIn('relation does not exist', message)
        self.assertIn('events', message)
        self.assertNotIn('private-pass', message)
        connection_error = RuntimeError('SQL and parameters withheld')
        connection_error.orig = OSError(111, 'Connection refused')
        self.assertIn('Connection refused', acceptance.safe_diagnostic(connection_error, cls))
        command_error = subprocess.CalledProcessError(1, ['/private/bin/initdb', '--pwfile=hidden'],
                                                      stderr='initdb: error: permission denied')
        message = acceptance.safe_diagnostic(command_error, cls)
        self.assertIn('initdb exit=1', message)
        self.assertIn('permission denied', message)
        self.assertNotIn('--pwfile', message)


if __name__ == '__main__':
    unittest.main()
