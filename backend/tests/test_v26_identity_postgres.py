"""Opt-in synthetic cluster, never an existing DB. Fixed acceptance target created exclusively."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from app.core import v26_acceptance
from app.services import demo_subscriptions, identity
from app.services.first_admin import FirstAdminInput, SetupBlocked
from app.services.identity_setup import inspect_setup
from app.services.v26_identity import V26FirstAdminStore
from backend.tests.v26_disposable_cluster import DisposableClusterGuard

SOURCE = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('V2_RUN_V26_IDENTITY_TESTS') == '1', 'Explicit disposable cluster opt-in required')
class V26IdentityPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = v26_acceptance.ROOT
        # Refuse any pre-existing acceptance environment, including symlinks.
        cls.root.mkdir(mode=0o700)
        cls.addClassCleanup(shutil.rmtree, cls.root)
        for name in ('backend', 'migrations', 'socket'):
            (cls.root / name).mkdir(mode=0o700)
        cls.pg = Path('/usr/lib/postgresql/16/bin')
        cls.data = cls.root / 'postgres-test'
        cls.password = secrets.token_urlsafe(32)  # Synthetic and ephemeral; never printed.
        pwfile = cls.root / 'test-password'
        pwfile.write_text(cls.password)
        pwfile.chmod(0o600)
        subprocess.run([str(cls.pg / 'initdb'), '-D', str(cls.data), '-U', 'v26_acceptance',
                        '--auth-local=trust', '--auth-host=scram-sha-256', '--pwfile='+str(pwfile)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pwfile.unlink()
        # Capture the identity of THIS newly initialized, private PG16 directory.
        # Only the OS-specific PGDATA check is substituted; target DB/role/port,
        # profile, cwd/owner, marker and every transaction/HTTP assertion remain.
        cluster_guard = DisposableClusterGuard(cls.root)
        guard_patch = patch('app.services.v26_identity.verify_cluster', side_effect=cluster_guard)
        guard_patch.start()
        cls.addClassCleanup(guard_patch.stop)
        subprocess.run([str(cls.pg / 'pg_ctl'), '-D', str(cls.data), '-l', str(cls.root / 'postgres.log'),
                        '-o', '-h 127.0.0.1 -p 55433 -k '+str(cls.root / 'socket'), '-w', 'start'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(subprocess.run, [str(cls.pg / 'pg_ctl'), '-D', str(cls.data), '-m', 'fast', '-w', 'stop'],
                            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([str(cls.pg / 'createdb'), '-h', str(cls.root / 'socket'), '-p', '55433',
                        '-U', 'v26_acceptance', 'mikrotik_v26_acceptance'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = URL.create('postgresql+psycopg', username='v26_acceptance', password=cls.password,
                         host='127.0.0.1', port=55433, database='mikrotik_v26_acceptance')
        env = dict(V2_DEPLOYMENT_PROFILE=v26_acceptance.PROFILE, V2_ENVIRONMENT='v26-acceptance',
                   V2_API_HOST='127.0.0.1', V2_API_PORT='18996', V2_ROUTER_ONBOARDING_ENABLED='false',
                   V2_CEBECI_API_SSL_ENABLED='false', V2_ROUTER_ONBOARDING_OPERATOR_IDS='',
                   V2_DATABASE_URL=url.render_as_string(hide_password=False))
        env_patch = patch.dict(os.environ, env)
        env_patch.start()
        cls.addClassCleanup(env_patch.stop)
        before = Path.cwd()
        os.chdir(cls.root)
        cls.addClassCleanup(os.chdir, before)
        cls.engine = create_engine(url, hide_parameters=True)
        cls.addClassCleanup(cls.engine.dispose)
        engine_patch = patch('app.core.database.engine', cls.engine)
        engine_patch.start()
        cls.addClassCleanup(engine_patch.stop)
        adapter_patch = patch.object(demo_subscriptions.store, '_adapter', None)
        adapter_patch.start()
        cls.addClassCleanup(adapter_patch.stop)
        from app.main import app
        cls.client = TestClient(app)
        cls.addClassCleanup(cls.client.close)

    def setUp(self):
        self.client.cookies.clear()
        with self.engine.begin() as connection:
            # Only the new cluster created above, never an existing installation.
            connection.exec_driver_sql('DROP SCHEMA IF EXISTS v26_acceptance CASCADE')
            sql = (SOURCE / 'migrations/versions/002_demo_storage.sql').read_text()
            for statement in sql.replace('v2_demo', 'v26_acceptance').split(';'):
                if statement.strip():
                    connection.execute(text(statement))
        self.store = V26FirstAdminStore(self.engine)
        self.payload = FirstAdminInput(username='synthetic.admin', name='Synthetic Admin',
                                      email='synthetic@local.test', password='SYNTHETIC-test-only-password-91')

    def login(self, username=None, password=None):
        return self.client.post('/api/v1/auth/login', json=dict(
            username=username or self.payload.username,
            password=password or self.payload.password.get_secret_value()))

    def digest(self):
        with self.engine.connect() as connection:
            tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='v26_acceptance' ORDER BY tablename")).scalars()
            return {name: list(connection.execute(text(f'SELECT to_jsonb(t)::text FROM v26_acceptance.{name} t ORDER BY to_jsonb(t)::text')).scalars()) for name in tables}

    def test_http_before_after_migration_and_idempotent_seal(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        # Nonempty pre-existing synthetic subscription/history/request data must survive.
        from uuid import uuid4
        import json
        with self.engine.begin() as connection:
            connection.execute(text('INSERT INTO v26_acceptance.subscribers(id,payload) VALUES (:id,CAST(:payload AS jsonb))'),
                               dict(id='demo-sub-existing', payload=json.dumps(dict(id='demo-sub-existing', is_demo=True))))
            connection.execute(text('INSERT INTO v26_acceptance.events(id,subscriber_id,revision,payload) VALUES (:id,:subscriber,1,CAST(:payload AS jsonb))'),
                               dict(id=str(uuid4()), subscriber='demo-sub-existing', payload=json.dumps(dict(is_demo=True))))
            connection.execute(text('INSERT INTO v26_acceptance.requests(id,subscriber_id,fingerprint,response) VALUES (:id,:subscriber,:fingerprint,CAST(:response AS jsonb))'),
                               dict(id=str(uuid4()), subscriber='demo-sub-existing', fingerprint='synthetic', response=json.dumps(dict(is_demo=True))))
        before = self.digest()
        self.assertEqual(self.login().status_code, 503)
        self.assertEqual(self.login().json()['code'], 'DATABASE_UNAVAILABLE')
        self.assertEqual(self.digest(), before)  # HTTP never initializes anything.
        self.store.create(self.payload, os.getuid())
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 200)
        self.assertEqual(identity.list_users(1, 10)['total'], 1)
        self.assertEqual(identity.audit_users(1, 10)['total'], 1)
        self.assertEqual(self.login('demo', 'demo-only').status_code, 401)
        snapshot = self.digest()
        with self.assertRaisesRegex(SetupBlocked, 'FIRST_ADMIN_SETUP_CLOSED'):
            self.store.create(self.payload, os.getuid())
        self.assertEqual(snapshot, self.digest())
        for name in before:
            if name != 'schema_state':
                self.assertEqual(before[name], snapshot[name])
        self.assertTrue(self.store.status().closed)

    def test_management_and_rejection_audit_use_acceptance_schema(self):
        from uuid import uuid4
        from app.services.demo_subscriptions import DemoChangeError
        admin = self.store.create(self.payload, os.getuid())
        payload = identity.UserCreate(request_id=str(uuid4()), username='synthetic.viewer',
            name='Synthetic Viewer', email='viewer@local.test', password='SYNTHETIC-viewer-only-password',
            role='VIEWER', active=True, permissions={}, expected_revision=0, confirmed=True)
        user = identity.save_user(payload, admin['id'])
        self.assertEqual(user['account_origin'], 'LOCAL')
        self.assertEqual(self.login(payload.username, payload.password).status_code, 200)
        identity.record_rejection(payload.model_copy(update={'request_id':str(uuid4())}),
                                  admin['id'], user['id'], 'UPDATE', DemoChangeError(409, 'Synthetic rejection'))
        self.assertEqual(identity.list_users(1, 10)['total'], 2)
        self.assertEqual(identity.audit_users(1, 10)['total'], 3)
        from app import first_admin as cli
        import io
        from contextlib import redirect_stdout, redirect_stderr
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(cli.main(['--status'], v26=True), 0)
            with patch.object(cli, 'collect_input') as collect:
                self.assertEqual(cli.main(['--create'], v26=True), 1)
                collect.assert_not_called()
        self.assertIn('FIRST_ADMIN_SETUP_CLOSED', output.getvalue())
        self.assertIn('REAL_TTY_REQUIRED', output.getvalue())
        self.assertNotIn(self.payload.password.get_secret_value(), output.getvalue())

    def test_real_ddl_and_account_rollback_on_failure(self):
        before = self.digest()
        def fail(*args, **kwargs):
            raise RuntimeError('synthetic transaction fault')
        with patch.object(identity, 'hash_password', side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.store.create(self.payload, os.getuid())
        self.assertEqual(before, self.digest())
        self.assertEqual(self.login().status_code, 503)
        self.store.create(self.payload, os.getuid())
        self.assertEqual(self.login().status_code, 200)

    def test_concurrent_setup_and_corrupt_seal_fail_closed(self):
        def create():
            try:
                self.store.create(self.payload, os.getuid())
                return 'created'
            except SetupBlocked as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: create(), range(2))),
                                  ['created', 'FIRST_ADMIN_SETUP_CLOSED'])
        with self.engine.begin() as connection:
            connection.execute(text('DELETE FROM v26_acceptance.first_admin_setup'))
        self.assertEqual(self.login().status_code, 503)
        from app.services.demo_subscriptions import DemoStorageUnavailable
        with self.assertRaises(DemoStorageUnavailable):
            self.store.create(self.payload, os.getuid())

    def test_wrong_profile_target_and_cwd_rejected_before_connection(self):
        from unittest.mock import Mock
        for key, value in (('V2_DEPLOYMENT_PROFILE', 'cebeci-vds'),
                           ('V2_DATABASE_URL', 'postgresql+psycopg://invalid@127.0.0.1:5432/invalid'),
                           ('V2_ROUTER_ONBOARDING_ENABLED', 'true')):
            engine = Mock()
            with patch.dict(os.environ, {key:value}):
                with self.assertRaises(RuntimeError):
                    V26FirstAdminStore(engine)
            engine.connect.assert_not_called()
        os.chdir(SOURCE)
        try:
            with self.assertRaises(SetupBlocked):
                V26FirstAdminStore(self.engine)
        finally:
            os.chdir(self.root)
