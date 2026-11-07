"""Synthetic install/read chain; no sockets, PostgreSQL or real account data."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'backend'))
spec = importlib.util.spec_from_file_location('preferences_install', ROOT/'deploy/fresh-v2-pilot/manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.api.v1.system import router
from app.core.security import current_demo_user
from app.services import system_settings, identity
from app.services.demo_subscriptions import DemoStorageUnavailable


class PreferencesInstall(TestCase):
    def setUp(self):
        self.rows = {}
        self.calls = []
        self.connection = MagicMock()
        self.connection.execution_options.return_value = self.connection
        self.connection.__enter__.return_value = self.connection
        self.connection.execute.side_effect = self.execute
        self.engine = SimpleNamespace(connect=lambda:self.connection)
        self.store = SimpleNamespace(schema='v2_demo',engine=self.engine, _verify=lambda c:None)
        app = FastAPI()
        app.include_router(router, prefix='/api/v1')
        app.dependency_overrides[current_demo_user] = lambda:{'id':'synthetic-admin'}
        @app.exception_handler(DemoStorageUnavailable)
        def unavailable(request, error):
            from app.main import demo_storage_unavailable
            return demo_storage_unavailable(request, error)
        self.client = TestClient(app)
        self.patch = patch.object(identity, 'adapter', return_value=self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def execute(self, statement, params=None):
        sql = str(statement); self.calls.append(sql); value = None
        if 'to_regclass' in sql:
            value = True
        elif sql.startswith('SELECT * FROM v2_demo.settings_records'):
            value = self.rows.get(params['id'])
        elif sql.startswith('INSERT INTO v2_demo.settings_records'):
            if 'default' in self.rows:
                raise OperationalError('synthetic conflict', {}, Exception())
            self.rows['default'] = dict(payload=json.loads(params['values']),revision=0,updated_at=None)
        return SimpleNamespace(scalar_one=lambda:value,mappings=lambda:SimpleNamespace(one_or_none=lambda:value))

    def test_missing_default_is_503_then_explicit_install_enables_read_without_writes(self):
        # Tables exist, but old fresh installation supplied no mandatory default row.
        self.assertEqual(self.client.get('/api/v1/preferences').status_code,503)
        with self.assertRaisesRegex(manage.Blocked,'DEFAULT_PREFERENCES_REJECTED'):
            manage.verify_preferences(self.connection)
        manage.initialize_preferences(self.connection)
        self.calls.clear()
        manage.verify_preferences(self.connection)
        response = self.client.get('/api/v1/preferences')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['values'],system_settings.Values().model_dump())
        self.assertTrue(response.json()['storage_ready'])
        self.assertTrue(all(sql.startswith(('SELECT','SET TRANSACTION READ ONLY')) for sql in self.calls))

    def test_invalid_default_stays_503_and_existing_settings_are_never_overwritten(self):
        self.rows['default'] = dict(payload={'theme':'invalid-synthetic'},revision=7,updated_at=None)
        self.assertEqual(self.client.get('/api/v1/preferences').status_code,503)
        with self.assertRaisesRegex(manage.Blocked,'DEFAULT_PREFERENCES_REJECTED'):
            manage.verify_preferences(self.connection)
        with self.assertRaises(OperationalError):
            manage.initialize_preferences(self.connection)
        self.assertEqual(self.rows['default']['revision'],7)
        self.assertEqual(self.rows['default']['payload']['theme'],'invalid-synthetic')

    def test_install_calls_preferences_after_migration_five_and_empty_gate(self):
        events = []
        manifest = {'migrations':[{'position':i} for i in range(1,10)]}
        def execute(c,sql,params=None):
            if sql.startswith('INSERT INTO v2_migrations.applied'):events.append(params['position'])
        with patch.object(manage,'verify_identity'),patch.object(manage,'require_empty',side_effect=lambda c:events.append('empty')),patch.object(manage,'execute_script'),patch.object(manage,'execute',side_effect=execute),patch.object(manage,'verify_schema'),patch.object(manage,'schema_hash',return_value='synthetic'),patch.object(manage,'verify'),patch('app.services.first_admin.create_local_admin'),patch.object(manage,'initialize_preferences',side_effect=lambda c:events.append('preferences')):
            manage.migrate(self.connection,b'{}',manifest,['']*9,None,1000,'a'*64)
            self.assertLess(events.index('empty'),events.index('preferences'))
            self.assertEqual(events[events.index('preferences')-1],4)
            self.assertEqual(events[events.index('preferences')+1],5)
            with patch.object(manage,'require_empty',side_effect=manage.Blocked('NONEMPTY_TARGET')),patch.object(manage,'initialize_preferences') as seed:
                with self.assertRaises(manage.Blocked):
                    manage.migrate(self.connection,b'{}',manifest,['']*9,None,1000,'a'*64)
                seed.assert_not_called()
