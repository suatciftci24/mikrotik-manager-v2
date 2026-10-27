"""Opt-in real PostgreSQL integration, only disposable schemas in the V2 dev DB."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.core.database import engine
from app.demo_storage import initialize_demo
from app.main import app
from app.schemas.subscriber_events import ExpiryChange
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_subscriptions import DemoChangeError, DemoStorageUnavailable, DemoSubscriptionStore


class DestinationIsolation(TestCase):
    def test_non_v2_database_destinations_are_rejected_before_connection(self):
        for url in ['sqlite:///:memory:', 'postgresql+psycopg://v2_local:v2_local@198.51.100.1:55432/mikrotik_manager_v2',
                    'postgresql+psycopg://v2_local:v2_local@127.0.0.1:5432/mikrotik_manager_v2',
                    'postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/v1',
                    'postgresql+psycopg://postgres:demo@127.0.0.1:55432/mikrotik_manager_v2']:
            with self.subTest(url=url):
                with self.assertRaises(DemoStorageUnavailable):
                    PostgresDemoStore(SimpleNamespace(url=make_url(url)))


class DemoSnapshotValidation(TestCase):
    def test_import_rejects_inconsistent_or_naive_audit_before_database_access(self):
        from copy import deepcopy
        from app.demo_storage import validated_snapshots
        memory = DemoSubscriptionStore(SUBSCRIBERS)
        item = memory.detail('demo-sub-1001')['item']
        change = ExpiryChange.model_validate({'expires_on': (datetime.now(ZoneInfo('Europe/Istanbul')).date()+timedelta(days=90)).isoformat(),
                                             'expected_expires_on': item['expires_on'], 'expected_revision': 0, 'expected_source': 'LOCAL',
                                             'operation': 'RENEWAL', 'request_id': str(uuid4()), 'confirmed': True})
        snapshot = memory.change_expiry(item['id'], change, 'demo-user')
        self.assertEqual(validated_snapshots([snapshot])[0]['item']['revision'], 1)
        for invalid in ['time', 'revision', 'source']:
            changed = deepcopy(snapshot)
            if invalid == 'time': changed['history'][0]['occurred_at'] = '2026-10-27T12:00:00'
            if invalid == 'revision': changed['item']['revision'] = 0
            if invalid == 'source': changed['item']['source'] = None
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validated_snapshots([changed])


@skipUnless(os.environ.get('V2_RUN_PG_TESTS') == '1', 'Explicit V2 development PostgreSQL opt-in required')
class PostgresDemoPersistence(TestCase):
    @classmethod
    def tearDownClass(cls):
        engine.dispose()

    def setUp(self):
        self.schema = 'v2_demo_test_' + uuid4().hex
        self.schemas = [self.schema]
        self.addCleanup(self.cleanup_schemas)
        initialize_demo(engine, schema=self.schema)
        self.store = PostgresDemoStore(engine, self.schema)
        self.mock_store = patch('app.services.demo_subscriptions.store', self.store)
        self.mock_store.start()
        self.addCleanup(self.mock_store.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.client.post('/api/v1/auth/login', json={'username': 'demo', 'password': 'demo-only'})
        self.addCleanup(lambda: self.client.post('/api/v1/auth/logout'))
        self.today = datetime.now(ZoneInfo('Europe/Istanbul')).date()

    def cleanup_schemas(self):
        for schema in self.schemas:
            assert schema.startswith('v2_demo_test_') and len(schema) == len('v2_demo_test_') + 32
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))

    def payload(self, item_id='demo-sub-1001', **changes):
        item = self.store.detail(item_id)['item']
        return {**dict(expires_on=(self.today+timedelta(days=90)).isoformat(), expected_expires_on=item['expires_on'],
                       expected_revision=item['revision'], expected_source=item['source'] or 'LOCAL',
                       operation='RENEWAL', request_id=str(uuid4()), confirmed=True), **changes}

    def test_two_fresh_application_processes_preserve_record_audit_and_retry_result(self):
        payload = self.payload()
        worker = '''
import json, sys
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import engine
from app.adapters.demo_subscriptions import PostgresDemoStore
store=PostgresDemoStore(engine,sys.argv[1])
with patch('app.services.demo_subscriptions.store',store), TestClient(app) as client:
    client.post('/api/v1/auth/login',json={'username':'demo','password':'demo-only'})
    request=json.loads(sys.argv[2])
    response=client.post('/api/v1/subscribers/demo-sub-1001/demo-expiry',json=request,headers={'X-V2-Demo-Action':'expiry'})
    assert response.status_code==200,response.text
    detail=client.get('/api/v1/subscribers/demo-sub-1001').json()
    listed=client.get('/api/v1/subscribers').json()
    print(json.dumps({'response':response.json(),'detail':detail,'list':listed}))
'''
        def run():
            result = subprocess.run([sys.executable, '-c', worker, self.schema, json.dumps(payload)],
                                    env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])},
                                    capture_output=True, text=True, check=True, timeout=20)
            return json.loads(result.stdout)
        first, reopened = run(), run()
        self.assertEqual(first, reopened)
        self.assertEqual(reopened['detail']['persistence'], 'local-postgresql-demo')
        self.assertEqual(len(reopened['detail']['history']), 1)
        self.assertEqual(reopened['detail']['history'][0]['previous_expires_on'], payload['expected_expires_on'])
        self.assertEqual(reopened['detail']['item']['expires_on'], payload['expires_on'])
        self.assertEqual(reopened['detail']['item']['source'], 'LOCAL')
        listed = next(row for row in reopened['list']['items'] if row['id'] == 'demo-sub-1001')
        self.assertEqual(listed, reopened['detail']['item'])

    def test_transaction_rolls_back_record_and_audit_if_request_insert_fails(self):
        before = self.store.detail('demo-sub-1001')
        change = ExpiryChange.model_validate(self.payload())
        def fail(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.startswith(f'INSERT INTO {self.schema}.requests'):
                raise RuntimeError('synthetic transaction failure')
        event.listen(engine, 'before_cursor_execute', fail)
        try:
            with self.assertRaises(RuntimeError):
                self.store.change_expiry('demo-sub-1001', change, 'demo-user')
        finally:
            event.remove(engine, 'before_cursor_execute', fail)
        self.assertEqual(self.store.detail('demo-sub-1001'), before)
        result = self.store.change_expiry('demo-sub-1001', change, 'demo-user')
        self.assertEqual(len(result['history']), 1)

    def test_independent_connections_reject_stale_concurrent_changes(self):
        changes = [ExpiryChange.model_validate(self.payload()), ExpiryChange.model_validate(self.payload(expires_on=(self.today+timedelta(days=91)).isoformat()))]
        def attempt(change):
            try:
                PostgresDemoStore(engine, self.schema).change_expiry('demo-sub-1001', change, 'demo-user')
                return 200
            except DemoChangeError as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, changes))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(len(self.store.detail('demo-sub-1001')['history']), 1)

    def test_global_request_id_cannot_update_two_subscribers(self):
        key = str(uuid4())
        def attempt(item_id):
            try:
                self.store.change_expiry(item_id, ExpiryChange.model_validate(self.payload(item_id, request_id=key)), 'demo-user')
                return 200
            except DemoChangeError as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ['demo-sub-1001', 'demo-sub-1002']))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(sum(len(self.store.detail(item)['history']) for item in ['demo-sub-1001','demo-sub-1002']), 1)

    def test_explicit_setup_never_reseeds_or_overwrites_existing_changes(self):
        result = self.store.change_expiry('demo-sub-1001', ExpiryChange.model_validate(self.payload()), 'demo-user')
        self.assertFalse(initialize_demo(engine, schema=self.schema))
        self.assertEqual(PostgresDemoStore(engine, self.schema).detail('demo-sub-1001'), result)
        self.assertTrue(self.client.get('/api/health').json()['database_connected'])

    def test_missing_schema_is_503_and_never_falls_back_or_migrates(self):
        missing = 'v2_demo_test_' + uuid4().hex
        with patch('app.services.demo_subscriptions.store', PostgresDemoStore(engine, missing)):
            self.assertEqual(self.client.get('/api/v1/subscribers').status_code, 503)
            self.assertEqual(self.client.post('/api/v1/subscribers/demo-sub-1001/demo-expiry', json=self.payload(), headers={'X-V2-Demo-Action':'expiry'}).status_code, 503)
        with engine.connect() as connection:
            self.assertIsNone(connection.execute(text('SELECT to_regnamespace(:name)'), {'name':missing}).scalar_one())
        self.assertEqual(self.store.detail('demo-sub-1001')['history'], [])

    def test_existing_memory_snapshot_import_preserves_audit_and_request_idempotency(self):
        memory = DemoSubscriptionStore(SUBSCRIBERS)
        payload = self.payload()
        change = ExpiryChange.model_validate(payload)
        saved = memory.change_expiry('demo-sub-1001', change, 'demo-user')
        snapshots = [memory.detail(row['id']) for row in SUBSCRIBERS]
        imported_schema = 'v2_demo_test_' + uuid4().hex
        self.schemas.append(imported_schema)
        initialize_demo(engine, snapshots, imported_schema)
        imported = PostgresDemoStore(engine, imported_schema)
        detail = imported.detail('demo-sub-1001')
        self.assertEqual(detail['item'], saved['item'])
        self.assertEqual(len(detail['history']), 1)
        repeated = imported.change_expiry('demo-sub-1001', change, 'demo-user')
        self.assertEqual(repeated, detail)

    def test_real_or_unmarked_payloads_cannot_enter_demo_schema(self):
        with self.assertRaises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(f'INSERT INTO {self.schema}.subscribers(id,payload,revision) VALUES (:id,CAST(:payload AS jsonb),0)'),
                                   {'id':'demo-sub-invalid', 'payload':json.dumps({'id':'demo-sub-invalid','is_demo':False})})
        self.assertEqual(len(self.store.list_items()), 7)
