"""Explicit disposable PG16 + real HTTP acceptance. Never run by test discovery.

Run from the repo root with --run, only in a local environment allowing sockets.
No existing DB, environment DSN, external HTTP client, or production service is used.
"""
import argparse
import errno
import http.client
from http.cookies import SimpleCookie
import importlib.util
import json as codec
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2]
ROOT = Path('/tmp/mikrotik-v26-acceptance')
PG = Path('/usr/lib/postgresql/16/bin')
HOST, PORT = '127.0.0.1', 18996
DATABASE_PORT = 55433


class AcceptanceBlocked(RuntimeError):
    pass


ACTIVE_ACCEPTANCE_CLASS = None
ACTIVE_ACCEPTANCE_BIND_ERROR = None


def failed_acceptance_stage(result):
    """Keep the last safe fixture stage when unittest reports setUpClass errors."""
    failures = result.errors + result.failures
    if not failures:
        return None
    for test, _ in failures:
        stage = getattr(test, 'stage', None)
        if stage:
            return stage
    stage = getattr(ACTIVE_ACCEPTANCE_CLASS, 'stage', None)
    return stage or 'FIXTURE_SETUP_OR_CLEANUP'


def failed_acceptance_diagnostic(result):
    stage = failed_acceptance_stage(result)
    if not stage:
        return None
    diagnostic = 'stage=' + stage
    if stage == 'BROWSER_ACCEPTANCE':
        for _, traceback_text in result.errors + result.failures:
            if 'BROWSER_ACCEPTANCE_DID_NOT_COMPLETE' in traceback_text:
                diagnostic += ' reason=BROWSER_PROCESS_FAILED'
                break
    if stage == 'BROWSER_ACCEPTANCE':
        for _, trace in result.errors + result.failures:
            import re
            match = re.search(r'(?:AcceptanceBlocked|AssertionError|TimeoutError|OSError): ([A-Z][A-Z0-9_]{3,100})', trace)
            if match:
                diagnostic += ' failure_code=' + match.group(1)
    failure = ACTIVE_ACCEPTANCE_BIND_ERROR
    if failure and failure['stage'] == stage:
        diagnostic += ' error_class=' + failure['error_class']
        diagnostic += ' errno=' + str(failure['errno'])
        diagnostic += ' errno_name=' + failure['errno_name']
        diagnostic += ' syscall=' + failure['syscall']
        diagnostic += ' host=' + failure['host']
        diagnostic += ' port=' + str(failure['port'])
    elif failure and failure['stage'] in ('HTTP_LISTENER_BIND', 'POSTGRES_LISTENER_RESERVE'):
        # unittest may report a class-setup stage through a different TestCase
        # instance; retain the captured bind evidence without exposing exception text.
        diagnostic += ' bind_stage=' + failure['stage']
        diagnostic += ' bind_error_class=' + failure['error_class']
        diagnostic += ' bind_errno=' + str(failure['errno'])
        diagnostic += ' bind_errno_name=' + failure['errno_name']
        diagnostic += ' bind_syscall=' + failure['syscall']
        diagnostic += ' bind_host=' + failure['host']
        diagnostic += ' bind_port=' + str(failure['port'])
    return diagnostic


def capture_bind_error(stage, error, syscall):
    global ACTIVE_ACCEPTANCE_BIND_ERROR
    error_class = type(error).__name__
    if not error_class.isidentifier():
        error_class = 'OSError'
    code = error.errno if type(error.errno) is int else 'unknown'
    host, port = (HOST, PORT) if stage == 'HTTP_LISTENER_BIND' else (HOST, DATABASE_PORT)
    syscall = syscall if syscall in ('socket', 'bind', 'listen') else 'unknown'
    ACTIVE_ACCEPTANCE_BIND_ERROR = {
        'stage': stage, 'error_class': error_class, 'errno': code,
        'errno_name': errno.errorcode.get(code, 'UNKNOWN') if type(code) is int else 'UNKNOWN',
        'syscall': syscall, 'host': host, 'port': port,
    }


def verify_owned_acceptance_database(connection, store):
    """Revalidate the private V2.6 target immediately before browser startup."""
    from sqlalchemy import text
    store._check(connection)
    if connection.execute(text('SELECT 1')).scalar_one() != 1:
        raise AcceptanceBlocked('OWN_DISPOSABLE_DATABASE_NOT_READY')


def preflight():
    """No sockets/processes/DB IO; refuse rather than reuse an existing fixture."""
    if os.getuid() <= 0 or os.getuid() != os.geteuid() or Path.cwd() != SOURCE:
        raise AcceptanceBlocked('LOCAL_REPO_OWNER_REQUIRED')
    if os.path.lexists(ROOT):
        raise AcceptanceBlocked('ACCEPTANCE_ROOT_ALREADY_EXISTS')
    for name in ('initdb', 'pg_ctl', 'createdb'):
        if not os.access(PG / name, os.X_OK):
            raise AcceptanceBlocked('POSTGRESQL16_TOOLS_REQUIRED')
    for name in ('uvicorn', 'psycopg', 'sqlalchemy', 'fastapi'):
        if importlib.util.find_spec(name) is None:
            raise AcceptanceBlocked('ACCEPTANCE_DEPENDENCY_MISSING')


def isolated_environment(values):
    # Drop inherited targets, credentials and device gates before importing app code.
    values = {k: v for k, v in values.items() if not k.startswith(('V2_', 'PG'))}
    values.update(V2_RUN_V26_IDENTITY_TESTS='1',
                  V2_DEPLOYMENT_PROFILE='v26-isolated-acceptance',
                  V2_ENVIRONMENT='v26-acceptance', V2_API_HOST=HOST, V2_API_PORT=str(PORT),
                  V2_SESSION_SECURE='false', V2_ROUTER_ONBOARDING_ENABLED='false',
                  V2_CEBECI_API_SSL_ENABLED='false', V2_ROUTER_ONBOARDING_OPERATOR_IDS='',
                  # Import-time engine declaration only. Fixture generates a fresh DB secret
                  # and replaces the engine before any request or connection is permitted.
                  V2_DATABASE_URL='postgresql+psycopg://v26_acceptance:synthetic-unused-config-password'
                                  '@127.0.0.1:55433/mikrotik_v26_acceptance')
    return values


class LoopbackClient:
    """Fixed loopback transport: no proxies, redirects, retry or secret output."""
    def __init__(self):
        self.cookies = {}

    def close(self):
        self.cookies.clear()

    def request(self, method, path, *, json=None, headers=None):
        if method not in ('GET', 'POST') or not path.startswith('/api/') or any(
                c in path for c in ('\\', '\r', '\n', '#')):
            raise AcceptanceBlocked('HTTP_TARGET_REJECTED')
        request_headers = dict(headers or {})
        if 'v2_session' in self.cookies:
            request_headers['Cookie'] = 'v2_session=' + self.cookies['v2_session']
        body = None
        if json is not None:
            body = codec.dumps(json).encode()
            request_headers['Content-Type'] = 'application/json'
        connection = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            content = response.read(2 * 1024 * 1024 + 1)
            if len(content) > 2 * 1024 * 1024:
                raise AcceptanceBlocked('HTTP_RESPONSE_TOO_LARGE')
            cookie = SimpleCookie()
            cookie.load(response.getheader('Set-Cookie', ''))
            if 'v2_session' in cookie:
                value = cookie['v2_session'].value
                if value:
                    self.cookies['v2_session'] = value
                else:
                    self.cookies.pop('v2_session', None)
            # Match the assertion client's .text contract without exposing bodies/secrets.
            return SimpleNamespace(status_code=response.status,
                                   text=f'HTTP status={response.status}; response body withheld',
                                   json=lambda: codec.loads(content))
        finally:
            connection.close()

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)


def acceptance_suite(during_acceptance=None, browser_only=False):
    global ACTIVE_ACCEPTANCE_CLASS
    global ACTIVE_ACCEPTANCE_BIND_ERROR
    ACTIVE_ACCEPTANCE_BIND_ERROR = None
    # Lazy import keeps --help and offline harness tests free of app/DB setup.
    from backend.tests.test_v26_identity_postgres import V26IdentityPostgres

    class RealHttpAcceptance(V26IdentityPostgres):
        stage = 'FIXTURE_SETUP'
        pg_port_reservation = None

        @classmethod
        def run_pg(cls, arguments):
            # Keep 55433 reserved through initdb; release only for our own PG start.
            if (Path(arguments[0]).name == 'pg_ctl' and arguments[-1] == 'start'
                    and cls.pg_port_reservation is not None):
                cls.pg_port_reservation.close()
            return super().run_pg(arguments)

        @classmethod
        def setUpClass(cls):
            import socket
            # Bind once, before PG setup. Occupied/forbidden API port means stop;
            # never send synthetic credentials to another listener.
            cls.stage = 'HTTP_LISTENER_BIND'
            listener = None
            syscall = 'socket'
            try:
                listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cls.addClassCleanup(listener.close)
                syscall = 'bind'
                listener.bind((HOST, PORT))
                syscall = 'listen'
                listener.listen(128)
            except OSError as error:
                capture_bind_error(cls.stage, error, syscall)
                raise
            cls.listener = listener
            # Refuse collisions with another local PostgreSQL/service before
            # creating any fixture files. Never connect to the occupying process.
            cls.stage = 'POSTGRES_LISTENER_RESERVE'
            reservation = None
            syscall = 'socket'
            try:
                reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cls.pg_port_reservation = reservation
                cls.addClassCleanup(reservation.close)
                syscall = 'bind'
                reservation.bind((HOST, DATABASE_PORT))
            except OSError as error:
                capture_bind_error(cls.stage, error, syscall)
                raise
            super().setUpClass()

        @classmethod
        def make_client(cls, app):
            import threading
            import time
            import uvicorn
            cls.stage = 'HTTP_SERVER_START'
            cls.server = uvicorn.Server(uvicorn.Config(
                app, host=HOST, port=PORT, lifespan='off', access_log=False,
                log_config=None, log_level='critical'))
            cls.thread = threading.Thread(target=cls.server.run,
                                          kwargs={'sockets': [cls.listener]}, daemon=True)

            def stop():
                cls.server.should_exit = True
                cls.thread.join(timeout=10)
                if cls.thread.is_alive():
                    raise AcceptanceBlocked('OWN_HTTP_PROCESS_STOP_FAILED')

            cls.thread.start()
            cls.addClassCleanup(stop)
            deadline = time.monotonic() + 5
            while not cls.server.started:
                if not cls.thread.is_alive() or time.monotonic() >= deadline:
                    raise AcceptanceBlocked('OWN_HTTP_PROCESS_START_FAILED')
                time.sleep(0.01)
            if app.dependency_overrides:
                raise AcceptanceBlocked('AUTH_DEPENDENCY_OVERRIDE_REJECTED')
            return LoopbackClient()

        def setUp(self):
            self.stage = 'DEMO_SCHEMA_AND_IDENTITY_FIXTURE'
            super().setUp()
            from sqlalchemy import text
            from sqlalchemy.orm import sessionmaker
            from app.api.v1 import subscriber_center as routes
            from app.models.router_workspace import RouterWorkspaceRecord, RouterWorkspaceAudit
            from app.models.subscriber_workspace import SyntheticSubscriber, SyntheticSubscriberEvent
            from app.services.subscriber_center import SubscriberWorkspace
            from app.services.subscriber_operations import SubscriberOperationsService
            # Only this exclusively created cluster. No migration/maintenance CLI.
            self.stage = 'WORKSPACE_SCHEMA_AND_TABLES'
            with self.engine.begin() as connection:
                self.store._check(connection)
                connection.execute(text('CREATE SCHEMA v2_router_workspace'))
                connection.execute(text('CREATE SCHEMA v2_subscriber_workspace'))
                for table in (RouterWorkspaceRecord.__table__, RouterWorkspaceAudit.__table__,
                              SyntheticSubscriber.__table__, SyntheticSubscriberEvent.__table__):
                    table.create(connection)
            sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
            # Use the production workspace guard and real auth, never no-op checks.
            for name, value in (
                    ('workspace', SubscriberWorkspace(sessions)),
                    ('operations', SubscriberOperationsService(sessions))):
                scoped = patch.object(routes, name, value)
                scoped.start()
                self.addCleanup(scoped.stop)
            from uuid import uuid4
            self.router_id = 'demo-managed-router-' + str(uuid4())
            self.stage = 'SYNTHETIC_ROUTER_INSERT'
            with sessions.begin() as session:
                session.add(RouterWorkspaceRecord(id=self.router_id, kind='DEMO_ROUTER',
                            revision=1, fields={'name': 'Synthetic HTTP Router', 'model': 'Test'}))

        def snapshot(self):
            from sqlalchemy import text
            result = {}
            with self.engine.connect() as connection:
                for schema in ('v26_acceptance', 'v2_router_workspace', 'v2_subscriber_workspace'):
                    tables = connection.execute(text(
                        'SELECT tablename FROM pg_tables WHERE schemaname=:schema'),
                        {'schema': schema}).scalars().all()
                    for name in tables:
                        result[schema + '.' + name] = list(connection.execute(text(
                            f'SELECT to_jsonb(t)::text FROM "{schema}"."{name}" t '
                            'ORDER BY to_jsonb(t)::text')).scalars())
            return result

        def checked(self, response, status=200):
            self.assertEqual(response.status_code, status)
            return response.json()

        def test_new_real_http_acceptance(self):
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            from uuid import uuid4
            from app.services import identity
            path = '/api/v1/subscriber-workspace'
            headers = {'X-V2-Demo-Action': 'subscriber-workspace'}
            today = datetime.now(ZoneInfo('Europe/Istanbul')).date()
            self.stage = 'REAL_ADMIN_LOGIN'
            self.checked(self.client.get('/api/v1/auth/me'), 401)
            self.store.create(self.payload, os.getuid())
            admin = self.checked(self.login())
            self.assertEqual(admin['account_origin'], 'LOCAL')
            self.assertEqual(self.checked(self.client.get('/api/v1/auth/me'))['id'], admin['id'])
            self.stage = 'CREATE_EDIT_UUID'
            fields = dict(customer_name='Synthetic HTTP Subscriber', username='synthetic.http.one',
                          router_id=self.router_id, access_type='PPPOE', source='LOCAL',
                          plan='Synthetic 100', status='PAUSED',
                          expires_on=(today + timedelta(days=5)).isoformat())
            command = dict(request_id=str(uuid4()), fields=fields, expected_revision=0, confirmed=True)
            before = self.snapshot()
            self.checked(self.client.post(path, json=command), 403)
            self.assertEqual(self.snapshot(), before)
            created = self.checked(self.client.post(path, json=command, headers=headers))
            update = dict(request_id=str(uuid4()), fields={**fields, 'plan': 'Synthetic 200'},
                          expected_revision=created['revision'], confirmed=True)
            updated = self.checked(self.client.post(path + '/' + created['id'], json=update, headers=headers))
            self.assertEqual(updated['revision'], created['revision'] + 1)
            self.assertEqual(updated['plan'], 'Synthetic 200')
            self.stage = 'RENEWAL_UUID'
            renewal = dict(request_id=str(uuid4()), expected_revision=updated['revision'],
                           expected_source='LOCAL', expected_expires_on=updated['expires_on'],
                           expires_on=(today + timedelta(days=35)).isoformat(), days=30, confirmed=True)
            renewed = self.checked(self.client.post(path + '/' + created['id'] + '/renew',
                                                   json=renewal, headers=headers))
            self.assertEqual(renewed['expires_on'], renewal['expires_on'])
            self.assertEqual(renewed['revision'], updated['revision'] + 1)
            second = self.checked(self.client.post(path, headers=headers, json={
                **command, 'request_id': str(uuid4()),
                'fields': {**fields, 'username': 'synthetic.http.two', 'access_type': 'HOTSPOT'}}))
            self.stage = 'BULK_PARTIAL_UUID'
            def entry(item, revision):
                return dict(request_id=str(uuid4()), item_id=item['id'], expected_revision=revision,
                            expected_router_id=self.router_id, expected_source='LOCAL',
                            operation='STATUS', value='ACTIVE', confirmed=True)
            entries = [entry(renewed, renewed['revision']), entry(second, second['revision'] + 99)]
            bulk = self.checked(self.client.post(path + '/management/execute',
                                                json={'entries': entries}, headers=headers))['results']
            self.assertEqual([row['success'] for row in bulk], [True, False])
            self.assertTrue(all(row['recorded'] and row['actor_id'] == admin['id'] for row in bulk))
            self.stage = 'READONLY_RECEIPTS'
            receipts = [
                (path + '/requests/' + command['request_id'], 'SUCCESS', created),
                (path + '/requests/' + update['request_id'], 'SUCCESS', updated),
                (path + '/renewals/requests/' + renewal['request_id'], 'SUCCESS', renewed),
                (path + '/management/requests/' + entries[0]['request_id'], 'SUCCESS', bulk[0]),
                (path + '/management/requests/' + entries[1]['request_id'], 'FAILED', bulk[1])]
            before = self.snapshot()
            for url, state, original in receipts:
                result = self.checked(self.client.get(url))
                self.assertEqual(result['status'], state)
                self.assertEqual(result['response'], original)
            unknown = self.checked(self.client.get(path + '/requests/' + str(uuid4())))
            self.assertEqual(unknown['status'], 'UNKNOWN')
            self.assertIsNone(unknown['response'])
            self.assertEqual(before, self.snapshot())
            self.stage = 'VIEWER_AND_FOREIGN_ACTOR'
            def user(role, username, permissions):
                password = 'Synthetic-local-acceptance-password-91'
                identity.save_user(identity.UserCreate(
                    request_id=str(uuid4()), username=username, name='Synthetic HTTP Identity',
                    email=username + '@local.test', password=password, role=role, active=True,
                    permissions=permissions, expected_revision=0, confirmed=True), admin['id'])
                self.checked(self.client.post('/api/v1/auth/logout'))
                self.checked(self.login(username, password))
            user('VIEWER', 'synthetic.http.viewer', {})
            before = self.snapshot()
            self.checked(self.client.post(path, json=command, headers=headers), 403)
            self.checked(self.client.get(receipts[0][0]), 403)
            self.assertEqual(before, self.snapshot())
            user('ADMIN', 'synthetic.http.otheradmin', admin['permissions'])
            before = self.snapshot()
            for url, _, _ in receipts:
                result = self.checked(self.client.get(url))
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertIsNone(result['response'])
            self.assertEqual(before, self.snapshot())
            self.stage = 'LOGOUT'
            self.checked(self.client.post('/api/v1/auth/logout'))
            self.checked(self.client.get('/api/v1/auth/me'), 401)
            self.checked(self.client.get(receipts[0][0]), 401)
            if self.during_acceptance is not None:
                self.stage = 'BROWSER_ACCEPTANCE_DATABASE_VERIFY'
                with self.engine.connect() as connection:
                    verify_owned_acceptance_database(connection, self.store)
                self.stage = 'BROWSER_ACCEPTANCE'
                self.during_acceptance()

        def test_browser_only_diagnostic(self):
            """Exercise the isolated browser against owned PG/HTTP without rerunning HTTP cases."""
            self.stage = 'BROWSER_PROFILE_VERIFY'
            response = self.client.get('/api/ready')
            self.assertEqual(response.status_code, 200)
            profile = response.json()
            self.assertEqual(profile.get('service'), 'mikrotik-manager-v2')
            self.assertEqual(profile.get('environment'), 'v26-acceptance')
            self.assertEqual(profile.get('runtime_profile'), 'v26-isolated-acceptance')
            self.assertEqual(profile.get('api_port'), PORT)
            self.assertIs(profile.get('database_checked'), False)
            self.stage = 'BROWSER_ACCEPTANCE_DATABASE_VERIFY'
            with self.engine.connect() as connection:
                verify_owned_acceptance_database(connection, self.store)
            self.stage = 'BROWSER_ACCEPTANCE'
            if self.during_acceptance is not None:
                self.during_acceptance()

    # Explicitly select only the NEW socket scenario, never inherited PASS tests.
    RealHttpAcceptance.during_acceptance = during_acceptance
    RealHttpAcceptance.browser_only = browser_only
    ACTIVE_ACCEPTANCE_CLASS = RealHttpAcceptance
    selected = 'test_browser_only_diagnostic' if browser_only else 'test_new_real_http_acceptance'
    return unittest.TestSuite([RealHttpAcceptance(selected)])


def main(argv=None, during_acceptance=None, browser_only=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, action='store_true',
                        help='create and destroy a new synthetic cluster; never reuse an existing DB')
    parser.parse_args(argv)
    try:
        preflight()
        with patch.dict(os.environ, isolated_environment(os.environ), clear=True):
            result = unittest.TestResult()
            if during_acceptance is not None or browser_only:
                suite = acceptance_suite(during_acceptance, browser_only=browser_only)
            else:
                suite = acceptance_suite()
            suite.run(result)
        if result.wasSuccessful() and result.testsRun == 1 and not result.skipped:
            if browser_only:
                print('PASS: disposable PostgreSQL16 + loopback V2.6 readiness diagnostic; cleanup complete')
            else:
                print('PASS: disposable PostgreSQL16 + real loopback HTTP acceptance; cleanup complete')
            return 0
        diagnostic = failed_acceptance_diagnostic(result)
        if diagnostic:
            print('BLOCKED: acceptance ' + diagnostic)
        if result.skipped:
            print('BLOCKED: acceptance skipped')
        return 1
    except AcceptanceBlocked as error:
        print('BLOCKED: ' + str(error))
    except Exception as error:
        # Never echo DSNs, credentials, payloads or response bodies.
        print('BLOCKED: ' + type(error).__name__)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
