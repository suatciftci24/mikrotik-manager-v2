"""Real private SQLite relations + PG catalogue shim. No sockets or configured DB IO.

Not a PostgreSQL compatibility test: transaction settings/catalogue and JSON decoding
are adapted explicitly; the table-presence predicates and SELECTs run on real tables.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool
from app.services import identity, system_settings as service
from app.services.settings_state import SettingsStateError
from app.adapters.demo_subscriptions import PostgresDemoStore
from app.api.v1.system import preferences
from app.main import demo_storage_unavailable


class Connection:
    def __init__(self, raw, calls):
        self.raw, self.calls = raw, calls
    def __enter__(self):
        self.raw.__enter__(); return self
    def __exit__(self, *args):
        return self.raw.__exit__(*args)
    def execution_options(self, **options):
        # SQLite has no REPEATABLE READ dialect option; no PG claim is made.
        return self
    def begin(self):
        return self.raw.begin()
    def execute(self, statement, params=None):
        sql = str(statement); self.calls.append(sql)
        if sql == 'SET TRANSACTION READ ONLY':
            return self.raw.exec_driver_sql('PRAGMA query_only=ON')
        result = self.raw.execute(statement, params or {})
        if sql.startswith('SELECT * FROM'):
            def one_or_none():
                row = result.mappings().one_or_none()
                if row is None: return None
                row = dict(row)
                if 'payload' in row: row['payload'] = json.loads(row['payload'])
                return row
            return SimpleNamespace(mappings=lambda:SimpleNamespace(one_or_none=one_or_none))
        return result


class SettingsSchemaSelection(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='v26-settings-')
        self.addCleanup(directory.cleanup)
        self.engine = create_engine('sqlite://', poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        @event.listens_for(self.engine, 'connect')
        def attach(db, _):
            for schema in ('v2_demo', 'v26_acceptance'):
                db.execute('ATTACH DATABASE ? AS '+schema, (str(Path(directory.name)/(schema+'.sqlite')),))
            def relation(name):
                schema, table = name.split('.')
                if schema not in ('v2_demo','v26_acceptance'): return None
                found = db.execute('SELECT 1 FROM '+schema+'.sqlite_master WHERE name=? AND type IN (\'table\',\'view\')', (table,)).fetchone()
                return name if found else None
            db.create_function('to_regclass', 1, relation)
        self.calls = []
        self.store = SimpleNamespace(schema='v26_acceptance', engine=SimpleNamespace(
            connect=lambda:Connection(self.engine.connect(), self.calls)))
        self.store._verify = lambda c:PostgresDemoStore._verify(self.store, c)
        p = patch.object(identity, 'adapter', return_value=self.store); p.start(); self.addCleanup(p.stop)
        # The configured PostgreSQL engine is forbidden even if a route drifts.
        from app.core.database import engine
        for method in ('connect', 'begin'):
            p = patch.object(engine, method, side_effect=AssertionError('configured database forbidden'))
            p.start(); self.addCleanup(p.stop)
        with self.engine.begin() as c:
            for schema in ('v2_demo','v26_acceptance'):
                c.execute(text('CREATE TABLE '+schema+'.schema_state(version INTEGER,marker TEXT)'))
                c.execute(text('INSERT INTO '+schema+'.schema_state VALUES(1,\'mikrotik-manager-v2-synthetic-only\')'))

    def seed(self, schema, records=True, audit=True, default=True):
        with self.engine.begin() as c:
            if records:
                c.execute(text('CREATE TABLE '+schema+'.settings_records(id TEXT PRIMARY KEY,payload TEXT,revision INTEGER,updated_at TEXT)'))
                if default:
                    c.execute(text('INSERT INTO '+schema+'.settings_records VALUES(\'default\',:payload,7,NULL)'),
                              {'payload': service.Values(app_name='Synthetic preserved settings').model_dump_json()})
            if audit: c.execute(text('CREATE TABLE '+schema+'.settings_audit(id TEXT)'))

    def test_v26_only_relations_preferences_reads_selected_schema_and_never_writes(self):
        self.seed('v26_acceptance')
        result = preferences(user={'id':'synthetic-user'})
        self.assertTrue(result['storage_ready'])
        self.assertEqual(result['values']['app_name'], 'Synthetic preserved settings')
        self.assertTrue(any('v26_acceptance.settings_records' in s for s in self.calls))
        self.assertFalse(any('v2_demo.' in s for s in self.calls))
        self.assertTrue(all(s.startswith(('SELECT','SET TRANSACTION READ ONLY')) for s in self.calls))

    def test_other_schema_tables_cannot_mask_missing_selected_schema(self):
        self.seed('v2_demo')
        with self.assertRaises(SettingsStateError) as caught: preferences(user={'id':'synthetic-user'})
        response = demo_storage_unavailable(None, caught.exception)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body), {'code':'SETTINGS_SCHEMA_MISSING',
            'detail':'Ayar deposu şeması eksik; açık bakım gerekli.'})
        self.assertFalse(any('v2_demo.' in s for s in self.calls))

    def test_demo_schema_remains_independent(self):
        self.store.schema = 'v2_demo'; self.seed('v2_demo')
        self.assertTrue(service.effective('synthetic-user')['storage_ready'])
        self.assertFalse(any('v26_acceptance.' in s for s in self.calls))

    def test_records_present_but_audit_absent_is_schema_missing(self):
        self.seed('v26_acceptance', audit=False)
        with self.assertRaises(SettingsStateError) as caught: service.effective('synthetic-user')
        self.assertEqual(caught.exception.code, 'SETTINGS_SCHEMA_MISSING')

    def test_audit_present_but_records_absent_is_schema_missing(self):
        self.seed('v26_acceptance', records=False)
        with self.assertRaises(SettingsStateError) as caught: service.effective('synthetic-user')
        self.assertEqual(caught.exception.code, 'SETTINGS_SCHEMA_MISSING')

    def test_tables_present_but_default_absent_is_a_different_error(self):
        self.seed('v26_acceptance', default=False)
        with self.assertRaises(SettingsStateError) as caught: service.effective('synthetic-user')
        self.assertEqual(caught.exception.code, 'DEFAULT_SETTINGS_MISSING')
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT count(*) FROM v26_acceptance.settings_records')).scalar_one(), 0)

    def test_invalid_payload_is_distinct_and_is_never_replaced(self):
        self.seed('v26_acceptance')
        with self.engine.begin() as c:
            c.execute(text("UPDATE v26_acceptance.settings_records SET payload=:p"), {'p':'{"theme":"invalid"}'})
        with self.assertRaises(SettingsStateError) as caught: service.effective('synthetic-user')
        self.assertEqual(caught.exception.code, 'SETTINGS_RECORD_INVALID')
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT payload FROM v26_acceptance.settings_records')).scalar_one(), '{"theme":"invalid"}')

    def test_presence_gate_does_not_validate_columns_or_initialization_flag(self):
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE v26_acceptance.settings_records(id TEXT)'))
            c.execute(text('CREATE TABLE v26_acceptance.settings_audit(id TEXT)'))
        with self.engine.connect() as c:
            self.assertTrue(service.ready(c, 'v26_acceptance'))
        # No settings_initialized column exists either: ready() tests relations only.

    def test_unsafe_schema_is_refused_before_connection(self):
        self.store.schema = 'v26_acceptance; DELETE FROM users'
        from app.services.demo_subscriptions import DemoStorageUnavailable
        with self.assertRaises(DemoStorageUnavailable): service.effective('synthetic-user')
        self.assertEqual(self.calls, [])


class SettingsWriteSchemaRouting(TestCase):
    """Transaction model for SQL routing only; real PG execution is not claimed."""
    def setUp(self):
        from contextlib import contextmanager
        from unittest.mock import Mock
        import backend.tests.test_system_settings as fixtures
        self.db = fixtures.SQL(); self.queries = []
        original = self.db.execute
        def execute(statement, params=None):
            sql = str(statement); self.queries.append((sql, params))
            self.assertNotIn('v2_demo.', sql)
            if 'to_regclass' in sql:
                self.assertEqual(params, {'records':'v26_acceptance.settings_records','audit':'v26_acceptance.settings_audit'})
            if sql.startswith('SELECT count(*) FROM v26_acceptance.settings_audit'):
                return SimpleNamespace(scalar_one=lambda:len(self.db.audit))
            if sql.startswith('SELECT id,record_id,actor_id,previous_values,new_values,result,occurred_at'):
                return SimpleNamespace(mappings=lambda:[{'id':id, **row} for id,row in self.db.audit.items()])
            return original(text(sql.replace('v26_acceptance.', 'v2_demo.')), params)
        self.db.execute = execute
        @contextmanager
        def connect(): yield self.db
        self.store = SimpleNamespace(schema='v26_acceptance', engine=SimpleNamespace(
            begin=self.db.begin,connect=connect), _verify=Mock())
        p=patch.object(identity,'adapter',return_value=self.store);p.start();self.addCleanup(p.stop)

    def test_v26_save_replay_and_audit_are_bound_to_same_selected_schema(self):
        from uuid import uuid4
        command=service.Command(request_id=uuid4(),expected_revision=0,confirmed=True,
                                values=service.Values(app_name='Synthetic V26'))
        first=service.save('default',command,'demo-user')
        self.assertEqual(service.save('default',command,'demo-user'),first)
        result=service.audit('default',1,10)
        self.assertEqual(result['total'],1)
        self.assertTrue(any('INSERT INTO v26_acceptance.settings_records' in sql for sql,_ in self.queries))
        self.assertTrue(any('FROM v26_acceptance.users' in sql for sql,_ in self.queries))
        self.assertTrue(any('INSERT INTO v26_acceptance.settings_audit' in sql for sql,_ in self.queries))

    def test_v26_audit_insert_failure_rolls_back_change(self):
        from uuid import uuid4
        from app.services.demo_subscriptions import DemoStorageUnavailable
        self.db.fail=True
        command=service.Command(request_id=uuid4(),expected_revision=0,confirmed=True,
                                values=service.Values(app_name='Must roll back'))
        with self.assertRaises(DemoStorageUnavailable):service.save('default',command,'demo-user')
        self.assertEqual(self.db.rows['default']['revision'],0);self.assertEqual(self.db.audit,{})

    def test_v26_rejection_audit_is_not_written_to_demo_schema(self):
        from uuid import uuid4
        from app.services.demo_subscriptions import DemoChangeError
        command=service.Command(request_id=uuid4(),expected_revision=0,confirmed=True,values=service.Values())
        service.rejected('default',command,'demo-user',DemoChangeError(409,'Synthetic conflict'))
        self.assertEqual(len(self.db.audit),1)
        self.assertTrue(any('INSERT INTO v26_acceptance.settings_audit' in sql for sql,_ in self.queries))
