"""Opt-in real V2 PostgreSQL acceptance in disposable SYNTHETIC schemas only."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from unittest import TestCase, SkipTest, skipUnless
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.demo_subscriptions import PostgresDemoStore
from app.core.database import engine
from app.demo_repair import preflight, RepairBlocked
from app.services import identity
from app.services.first_admin import FirstAdminInput, FirstAdminStore, ROOT, SetupBlocked, verify_target
from app.services.identity_setup import inspect_setup
from app.services.demo_subscriptions import DemoStorageUnavailable


@skipUnless(os.environ.get('V2_RUN_FIRST_ADMIN_PG_TESTS') == '1', 'Explicit synthetic V2 PostgreSQL acceptance required')
class FirstAdminPostgresTests(TestCase):
    @classmethod
    def digest(cls, connection):
        records = {}
        for table in ('schema_state', 'subscribers', 'events', 'requests', 'users', 'user_audit', 'first_admin_setup', 'alarm_actions', 'alarm_requests'):
            if connection.execute(text('SELECT to_regclass(:table)'), {'table': 'v2_demo.' + table}).scalar_one():
                rows = list(connection.execute(text(f'SELECT to_jsonb(t) FROM v2_demo.{table} t')).scalars())
                records[table] = sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)
        return records

    @classmethod
    def setUpClass(cls):
        # One attempt for the entire suite. No socket workarounds, DB startup, repair or real setup.
        try:
            preflight(engine)
            with engine.connect() as connection:
                verify_target(connection)
                PostgresDemoStore(engine)._verify(connection)
                cls.baseline = cls.digest(connection)
        except (OSError, SQLAlchemyError, RepairBlocked, SetupBlocked, DemoStorageUnavailable):
            raise SkipTest('BLOCKED: isolated local V2 PostgreSQL unavailable; no writes attempted') from None

    @classmethod
    def tearDownClass(cls):
        with engine.connect() as connection:
            if cls.digest(connection) != cls.baseline:
                raise AssertionError('Existing V2 demo/identity/audit data changed')
        engine.dispose()

    def setUp(self):
        self.schema = 'v2_demo_test_' + uuid4().hex
        with engine.begin() as connection:
            sql = (ROOT / 'migrations/versions/002_demo_storage.sql').read_text()
            sql = sql.replace('v2_demo.', self.schema + '.').replace('CREATE SCHEMA v2_demo;', 'CREATE SCHEMA ' + self.schema + ';')
            connection.exec_driver_sql(sql)
        self.addCleanup(self.cleanup_schema)
        with engine.begin() as connection:
            alarm_sql = (ROOT / 'migrations/versions/003_demo_alarm_actions.sql').read_text().replace('v2_demo.', self.schema + '.')
            connection.exec_driver_sql(alarm_sql)
            sql = (ROOT / 'migrations/versions/004_demo_identity.sql').read_text().replace('v2_demo.', self.schema + '.')
            connection.exec_driver_sql(sql)
            fixture = identity.bootstrap()
            connection.execute(text(f'''INSERT INTO {self.schema}.users(id,username,name,email,role,active,password_hash,permissions,revision)
                VALUES (:id,:username,:name,:email,:role,:active,:password_hash,CAST(:permissions AS jsonb),:revision)'''),
                {**fixture, 'permissions': json.dumps(fixture['permissions'])})
        self.store = FirstAdminStore(engine, self.schema)
        self.payload = FirstAdminInput(username='synthetic.fixture', name='Synthetic Acceptance Admin',
                                       email='synthetic@local.test', password='SYNTHETIC-fixture-only-password')

    def cleanup_schema(self):
        # Only the unguessable, generated synthetic schema is ever dropped.
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))

    def create(self):
        return self.store.create(self.payload, os.getuid())

    def test_persisted_local_admin_strong_hash_audit_and_closed_seal(self):
        public = self.create()
        with engine.connect() as connection:
            state = inspect_setup(connection, self.schema)
            record = connection.execute(text(f'SELECT * FROM {self.schema}.users WHERE id=:id'), {'id': public['id']}).mappings().one()
            audit = connection.execute(text(f'SELECT to_jsonb(a) FROM {self.schema}.user_audit a')).scalar_one()
            self.assertTrue(state.closed)
            self.assertEqual(record['account_origin'], 'LOCAL')
            self.assertTrue(identity.verify_password(self.payload.password.get_secret_value(), record['password_hash']))
            self.assertNotIn(self.payload.password.get_secret_value(), json.dumps(audit, default=str))
            self.assertNotIn('password_hash', json.dumps(audit, default=str))
            self.assertEqual(audit['operation'], 'FIRST_ADMIN_CREATE')
            self.assertEqual(audit['target_id'], public['id'])
            self.assertEqual(connection.execute(text(f"SELECT account_origin FROM {self.schema}.users WHERE id='demo-user'")).scalar_one(), 'DEMO')

    def test_one_time_setup_stays_closed_after_first_admin_disabled(self):
        first = self.create()
        with engine.begin() as connection:
            connection.execute(text(f'UPDATE {self.schema}.users SET active=false WHERE id=:id'), {'id': first['id']})
        with self.assertRaisesRegex(SetupBlocked, 'FIRST_ADMIN_SETUP_CLOSED'):
            self.create()
        self.assertTrue(self.store.status().closed)

    def test_concurrent_transactions_create_exactly_one_account(self):
        def attempt():
            try:
                return self.create()['account_origin']
            except SetupBlocked as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(outcomes, ['LOCAL', 'FIRST_ADMIN_SETUP_CLOSED'])
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {self.schema}.user_audit')).scalar_one(), 1)

    def test_actual_audit_constraint_failure_rolls_back_upgrade_and_account(self):
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {self.schema}.user_audit ADD CONSTRAINT synthetic_audit_failure CHECK (operation <> 'FIRST_ADMIN_CREATE')"))
        with self.assertRaises(DemoStorageUnavailable):
            self.create()
        with engine.connect() as connection:
            self.assertFalse(inspect_setup(connection, self.schema).closed)
            self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {self.schema}.users')).scalar_one(), 1)
            self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {self.schema}.user_audit')).scalar_one(), 0)
            self.assertIsNone(connection.execute(text('SELECT to_regclass(:table)'), {'table': self.schema + '.first_admin_setup'}).scalar_one())

    def test_corrupt_closed_marker_fails_closed_without_new_account(self):
        self.create()
        with engine.begin() as connection:
            connection.execute(text(f'DELETE FROM {self.schema}.first_admin_setup'))
        with self.assertRaises(DemoStorageUnavailable):
            self.store.status()
        with self.assertRaises(DemoStorageUnavailable):
            self.create()
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {self.schema}.users')).scalar_one(), 2)

    def test_local_actor_can_ack_synthetic_alarm_without_rewriting_history(self):
        public = self.create()
        with engine.begin() as connection:
            connection.execute(text(f'''INSERT INTO {self.schema}.alarm_actions
                (id,alarm_id,occurrence_id,action,actor_id,owner,source_snapshot)
                VALUES (:id,'demo-alarm-acceptance','synthetic-occurrence','ACK',:actor,'','{{}}')'''),
                {'id': str(uuid4()), 'actor': public['id']})
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text(f'SELECT actor_id FROM {self.schema}.alarm_actions')).scalar_one(), public['id'])
