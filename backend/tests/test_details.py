"""Synthetic-only contract and authorization checks; no network or DB needed."""
import unittest
from fastapi.testclient import TestClient
from app.main import app


class DetailContracts(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        self.client.post('/api/v1/auth/logout')
        self.client.close()

    def login(self):
        response = self.client.post('/api/v1/auth/login', json={'username': 'demo', 'password': 'demo-only'})
        self.assertEqual(response.status_code, 200)

    def test_details_require_session_even_for_unknown_ids(self):
        for path in ['/routers/demo-router-001', '/subscribers/demo-sub-1001', '/routers/unknown', '/subscribers/unknown']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/api/v1' + path).status_code, 401)

    def test_router_assignments_are_partial_synthetic_inventory(self):
        self.login()
        routers = self.client.get('/api/v1/routers').json()['items']
        subscribers = self.client.get('/api/v1/subscribers').json()['items']
        for router in routers:
            response = self.client.get('/api/v1/routers/' + router['id'])
            self.assertEqual(response.status_code, 200)
            detail = response.json()
            self.assertEqual(detail['item'], router)
            self.assertTrue(detail['is_demo'])
            expected = [s for s in subscribers if s['router_name'] == router['name']]
            self.assertEqual(detail['assigned_subscribers'], expected)
            self.assertLess(len(expected), router['subscriber_count'])

    def test_subscribers_keep_authority_and_unknown_last_seen(self):
        self.login()
        rows = self.client.get('/api/v1/subscribers').json()['items']
        for row in rows:
            response = self.client.get('/api/v1/subscribers/' + row['id'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'item': row, 'is_demo': True, 'history': [], 'persistence': 'process-memory'})
            self.assertIn(response.json()['item']['source'], ('LOCAL', 'RADIUS', None))
        self.assertTrue(any(row['last_seen'] is None for row in rows))
        for module in ('routers', 'subscribers'):
            self.assertEqual(self.client.get(f'/api/v1/{module}/unknown').status_code, 404)
        self.assertEqual(self.client.get('/api/health').json()['device_adapters_connected'], False)
        self.assertEqual(self.client.get('/api/health').json()['database_connected'], False)

    def test_response_contracts_are_documented(self):
        schema = app.openapi()
        for path, model in [('/api/v1/routers/{item_id}', 'RouterDetail'), ('/api/v1/subscribers/{item_id}', 'SubscriberDetail')]:
            self.assertEqual(schema['paths'][path]['get']['responses']['200']['content']['application/json']['schema']['$ref'], '#/components/schemas/' + model)

    def test_expiry_dates_are_explicit_nullable_and_shared_by_list_and_detail(self):
        from datetime import date
        from app.services.demo_data import DEMO_DATE
        self.login()
        rows = self.client.get('/api/v1/subscribers').json()['items']
        offsets = []
        for row in rows:
            value = row['expires_on']
            offsets.append((date.fromisoformat(value) - DEMO_DATE).days if value else None)
            detail = self.client.get('/api/v1/subscribers/' + row['id']).json()
            self.assertEqual(detail['item']['expires_on'], value)
        self.assertEqual(offsets, [-3, 5, 20, 60, 0, None, 30])
        unknown = next(row for row in rows if row['expires_on'] is None)
        self.assertTrue(unknown['joined_at'])
        schema = app.openapi()['components']['schemas']['SubscriberRecord']['properties']['expires_on']
        self.assertIn({'type': 'string', 'format': 'date'}, schema['anyOf'])
        self.assertIn({'type': 'null'}, schema['anyOf'])

    def test_read_source_handles_unknown_without_changing_domain_authorities(self):
        from app.schemas.details import SubscriberRecord
        from app.models.subscriptions import AuthoritativeSource
        from app.services.demo_data import SUBSCRIBERS
        self.assertEqual({source.value for source in AuthoritativeSource}, {'LOCAL', 'RADIUS'})
        record = SUBSCRIBERS[0].copy()
        for value in [None, '', 'UNKNOWN', 'local', 'LOCAL/RADIUS', ['LOCAL', 'RADIUS'], {'router': 'LOCAL'}]:
            record['source'] = value
            self.assertIsNone(SubscriberRecord.model_validate(record).source)
        record.pop('source')
        self.assertIsNone(SubscriberRecord.model_validate(record).source)
        for value in ['LOCAL', 'RADIUS']:
            record['source'] = value
            self.assertEqual(SubscriberRecord.model_validate(record).source, value)
        self.login()
        rows = self.client.get('/api/v1/subscribers').json()['items']
        self.assertEqual([sum(row['source'] == value for row in rows) for value in ['LOCAL', 'RADIUS', None]], [3, 3, 1])
        unknown = next(row for row in rows if row['source'] is None)
        self.assertTrue(unknown['router_name'])
        self.assertIsNone(self.client.get('/api/v1/subscribers/' + unknown['id']).json()['item']['source'])
        router_id = next(router['id'] for router in self.client.get('/api/v1/routers').json()['items'] if router['name'] == unknown['router_name'])
        assigned = self.client.get('/api/v1/routers/' + router_id).json()['assigned_subscribers']
        self.assertIsNone(next(row for row in assigned if row['id'] == unknown['id'])['source'])
