"""Ev WSL only: explicit disposable PostgreSQL16 / real HTTP single-account acceptance."""
import argparse
import importlib.util
import os
import re
import traceback
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from backend.tests import v26_http_acceptance as harness


def safe_diagnostic(error, cls=None):
    """No locals, SQL statements/parameters, response bodies, DSNs or credentials."""
    secrets = []
    if cls is not None:
        secrets.append(getattr(cls, 'password', ''))
        client = getattr(cls, 'client', None)
        secrets.extend(getattr(client, 'cookies', {}).values())
    if isinstance(error, subprocess.CalledProcessError):
        executable = Path(error.cmd[0]).name
        message = f'{executable} exit={error.returncode}; ' + (error.stderr or 'no tool stderr')
    elif hasattr(error, 'orig'):
        original = error.orig
        message = 'database error; SQL and parameters withheld; SQLSTATE=' + str(
            getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None))
        diagnostic = getattr(original, 'diag', None)
        if not getattr(diagnostic, 'message_primary', None):
            message += '; ' + (str(original).splitlines() or ['no driver detail'])[0]
        for field in ('message_primary', 'schema_name', 'table_name', 'constraint_name'):
            value = getattr(diagnostic, field, None)
            if value:
                message += '; ' + field + '=' + str(value)
    else:
        message = str(error)
    # Both fixture credentials and fixed synthetic login credentials are secret.
    secrets.extend(['SYNTHETIC-test-only-password-91', 'Synthetic-viewer-password-91'])
    for secret in sorted((v for v in secrets if isinstance(v, str) and v), key=len, reverse=True):
        message = message.replace(secret, '[REDACTED]')
    message = re.sub(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\'\"]+', '[URL REDACTED]', message)
    message = re.sub(r'(?i)((?:password|passwd|token|secret|v2_session)[\'\"]?\s*[:=]\s*)[^\s,;}]+',
                     r'\1[REDACTED]', message)
    message = ' '.join(message.split())[:800]
    frames = traceback.extract_tb(error.__traceback__)
    location = ' > '.join(f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in frames[-5:])
    cause = error.__cause__
    cause_name = f'; cause={type(cause).__name__}' if cause is not None else ''
    return f'{type(error).__name__}: {message}{cause_name}; at {location or "no traceback"}'


class DiagnosticResult(unittest.TestResult):
    """Capture each subtest's parent stage at failure time, before it changes."""
    def __init__(self, cls):
        super().__init__()
        self.cls = cls
        self.diagnostics = []

    def capture(self, test, error):
        parent = getattr(test, 'test_case', test)
        stage = getattr(parent, 'stage', getattr(self.cls, 'stage', 'UNKNOWN_FIXTURE'))
        name = test.id() if hasattr(test, 'id') else str(test)
        self.diagnostics.append(f'BLOCKED: stage={stage}; test={name}; ' +
                                safe_diagnostic(error[1], self.cls))

    def addError(self, test, error):
        self.capture(test, error)
        super().addError(test, error)

    def addFailure(self, test, error):
        self.capture(test, error)
        super().addFailure(test, error)

    def addSubTest(self, test, subtest, error):
        if error is not None:
            self.capture(subtest, error)
        super().addSubTest(test, subtest, error)


def discover_pg():
    candidates = []
    config = shutil.which('pg_config')
    if config:
        result = subprocess.run([config, '--bindir'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            candidates.append(Path(result.stdout.strip()))
    initdb = shutil.which('initdb')
    if initdb:
        candidates.append(Path(initdb).resolve().parent)
    candidates.extend(sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True))
    for directory in candidates:
        if all(os.access(directory / n, os.X_OK) for n in ('initdb', 'pg_ctl', 'createdb', 'postgres')):
            version = subprocess.run([str(directory / 'postgres'), '--version'],
                                     capture_output=True, text=True, timeout=5)
            if version.returncode == 0 and re.search(r'\(PostgreSQL\)\s+16(?:\.|\s|$)', version.stdout):
                return directory
    raise harness.AcceptanceBlocked('POSTGRESQL16_SERVER_TOOLS_REQUIRED (install postgresql-16)')


def suite(pg):
    base = type(next(iter(harness.acceptance_suite())))
    from backend.tests.test_v26_test001_acceptance import Test001Workspace

    class Test001Http(base):
        payload = Test001Workspace.payload
        snapshot = Test001Workspace.snapshot
        test_actions = Test001Workspace.test_four_actions_api_database_detail_audit_and_replay

        def prepare(self):
            from app.api.v1 import subscriber_center as routes
            from uuid import uuid4
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            self.stage = 'FIRST_ADMIN_CREATE'
            self.store.create(self.payload_admin, os.getuid())
            self.stage = 'REAL_ADMIN_HTTP_LOGIN'
            self.actor = self.checked(self.login())
            self.assertEqual(self.actor['account_origin'], 'LOCAL')
            self.assertEqual(self.checked(self.client.get('/api/v1/auth/me'))['id'], self.actor['id'])
            self.workspace, self.ops = routes.workspace, routes.operations
            from sqlalchemy.orm import sessionmaker
            self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
            self.headers = {'X-V2-Demo-Action': 'subscriber-workspace'}
            expires = (datetime.now(ZoneInfo('Europe/Istanbul')).date() + timedelta(days=5)).isoformat()
            fields = dict(username='v26-test-001', customer_name='V26 Test 001',
                          router_id=self.router_id, access_type='PPPOE', source='LOCAL',
                          plan='Synthetic 100', status='ACTIVE', expires_on=expires)
            self.stage = 'HTTP_CREATE_TEST001'
            self.item = self.checked(self.client.post('/api/v1/subscriber-workspace', headers=self.headers,
                json=dict(request_id=str(uuid4()), expected_revision=0, confirmed=True, fields=fields)))
            self.path = '/api/v1/subscriber-workspace/management/execute'
            self.acceptance_actions = [('EXTEND', (datetime.fromisoformat(expires).date() + timedelta(days=30)).isoformat(), {'days': 30}),
                                       ('PLAN', 'Demo 500', {}), ('STATUS', 'PAUSED', {}), ('STATUS', 'ACTIVE', {})]
            self.stage = 'TEST001_ACTIONS_API_PERSISTENCE_AUDIT_REPLAY'

        def setUp(self):
            super().setUp()
            # Parent identity fixture calls this attribute payload; actions use a method of that name.
            self.payload_admin = self.__dict__.pop('payload')
            client_get = self.client.get
            def get(path, params=None, **kwargs):
                return client_get(path + ('?' + urlencode(params) if params else ''), **kwargs)
            self.client.get = get

        def login(self, username=None, password=None):
            return self.client.post('/api/v1/auth/login', json=dict(
                username=username or self.payload_admin.username,
                password=password or self.payload_admin.password.get_secret_value()))

        def test_errors(self):
            from uuid import uuid4
            from sqlalchemy.exc import SQLAlchemyError
            from app.services import identity
            self.stage = 'TEST001_REJECTIONS_ATOMIC_ROLLBACK'
            baseline = self.snapshot()
            command = self.payload('STATUS', 'PAUSED')
            self.checked(self.client.post(self.path, json={'entries': [command]}), 403)
            self.assertEqual(self.snapshot(), baseline)
            for changes in ({'confirmed': False}, {'operation': 'INVALID'}, {'expected_source': 'UNKNOWN'}):
                self.checked(self.client.post(self.path, headers=self.headers,
                             json={'entries': [{**command, **changes}]}), 422)
                self.assertEqual(self.snapshot(), baseline)
            with patch.object(self.ops, 'audit', side_effect=SQLAlchemyError('synthetic audit failure')):
                result = self.checked(self.client.post(self.path, headers=self.headers,
                                      json={'entries': [command]}))['results'][0]
            self.assertFalse(result['success']); self.assertFalse(result['recorded'])
            self.assertEqual(self.snapshot(), baseline)
            stale = {**command, 'request_id': str(uuid4()), 'expected_revision': 999}
            result = self.checked(self.client.post(self.path, headers=self.headers,
                                  json={'entries': [stale]}))['results'][0]
            self.assertFalse(result['success']); self.assertTrue(result['recorded'])
            accounts, events = self.snapshot()
            self.assertEqual(accounts, baseline[0]); self.assertEqual(len(events), len(baseline[1]) + 1)
            stable = self.snapshot()
            self.assertEqual(self.checked(self.client.post(self.path, headers=self.headers,
                             json={'entries': [stale]}))['results'][0], result)
            self.assertEqual(self.snapshot(), stable)
            password = 'Synthetic-viewer-password-91'
            identity.save_user(identity.UserCreate(request_id=str(uuid4()), username='synthetic.viewer',
                name='Synthetic Viewer', email='viewer@local.test', password=password, role='VIEWER',
                active=True, permissions={}, expected_revision=0, confirmed=True), self.actor['id'])
            self.checked(self.client.post('/api/v1/auth/logout'))
            self.checked(self.login('synthetic.viewer', password))
            self.checked(self.client.post(self.path, headers=self.headers, json={'entries': [command]}), 403)
            self.assertEqual(self.snapshot(), stable)
            self.checked(self.client.post('/api/v1/auth/logout'))
            self.checked(self.client.get('/api/v1/auth/me'), 401)

    def combined(self):
        self.test_actions()
        self.stage = 'FRESH_CONNECTION_PERSISTENCE'
        before = self.snapshot()
        self.engine.dispose()
        detail = self.checked(self.client.get('/api/v1/subscriber-center/' + self.item['id']))
        self.assertEqual(detail['item']['status'], 'ACTIVE')
        self.assertEqual(detail['item']['plan'], 'Demo 500')
        self.assertEqual(self.snapshot(), before)
        self.test_errors()
    Test001Http.test_combined = combined
    Test001Http.pg = pg
    return Test001Http, unittest.TestSuite([Test001Http('test_combined')])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', required=True)
    parser.parse_args()
    cls = None
    stage = 'PREFLIGHT'
    try:
        if os.getuid() <= 0 or os.getuid() != os.geteuid() or Path.cwd() != harness.SOURCE:
            raise harness.AcceptanceBlocked('LOCAL_REPO_OWNER_REQUIRED')
        if os.path.lexists(harness.ROOT):
            raise harness.AcceptanceBlocked('ACCEPTANCE_ROOT_ALREADY_EXISTS (never removed or reused)')
        pg = discover_pg()
        for name in ('uvicorn', 'psycopg', 'sqlalchemy', 'fastapi'):
            if importlib.util.find_spec(name) is None:
                raise harness.AcceptanceBlocked('DEPENDENCY_MISSING: ' + name)
        # Occupied PG port fails before any cluster or DB client exists. No probe connections.
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 55433))
        def interrupted(signum, frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        with patch.dict(os.environ, harness.isolated_environment(os.environ), clear=True):
            cls, tests = suite(pg)
            stage = 'ACCEPTANCE_RUN'
            result = DiagnosticResult(cls)
            try:
                tests.run(result)
            finally:
                # unittest normally cleans the class; interrupts may leave pending entries.
                if cls._class_cleanups:
                    cls.stage = 'INTERRUPTED_CLASS_CLEANUP'
                    cls.doClassCleanups()
                    for error in cls.tearDown_exceptions:
                        result.capture('class cleanup', error)
            if (result.wasSuccessful() and not result.diagnostics
                    and result.testsRun == 1 and not result.skipped
                    and not os.path.lexists(harness.ROOT)):
                print('PASS: v26-test-001 PostgreSQL + HTTP; cleanup complete')
                return 0
            for diagnostic in result.diagnostics:
                print(diagnostic)
            for test, reason in result.skipped:
                print('BLOCKED: skipped=' + test.id() + '; ' + reason)
            print(f'BLOCKED: tests={result.testsRun}; errors={len(result.errors)}; '
                  f'failures={len(result.failures)}; skipped={len(result.skipped)}')
            if os.path.lexists(harness.ROOT):
                print('BLOCKED: own temporary root retained: ' + str(harness.ROOT))
            return 1
    except BaseException as error:
        reason = safe_diagnostic(error, cls)
        print('BLOCKED: ' + stage + ': ' + reason)
        if os.path.lexists(harness.ROOT):
            print('BLOCKED: own temporary cluster retained; inspect ' + str(harness.ROOT) +
                  '; never stop an existing service')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
