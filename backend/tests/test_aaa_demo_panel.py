"""New GET presentation boundary only; existing AAA suites are not repeated."""
import unittest
from unittest.mock import patch

import json
from types import SimpleNamespace
from fastapi import FastAPI, HTTPException
from app.api.v1.aaa_demo import router, fixture_preview, current_demo_user


class AaaDemoPanelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Execute sync handlers inline in this in-process harness: the sandbox
        # cannot wake AnyIO worker threads through its restricted socket pair.
        async def inline(function, /, *args, **kwargs):
            return function(*args, **kwargs)
        self.enterContext(patch('fastapi.routing.run_in_threadpool', inline))
        self.enterContext(patch('fastapi.dependencies.utils.run_in_threadpool', inline))
        self.app = FastAPI()
        self.app.include_router(router, prefix='/api/v1')
        self.app.dependency_overrides[current_demo_user] = lambda: {'id': 'viewer'}
        self.client = self

    async def request(self, method, url, params=None):
        from urllib.parse import urlsplit, urlencode
        parts = urlsplit(url)
        query = urlencode(params) if params else parts.query
        messages = []
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(message):
            messages.append(message)
        await self.app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                        'method': method, 'scheme': 'http', 'path': parts.path,
                        'raw_path': parts.path.encode(), 'query_string': query.encode(),
                        'root_path': '', 'headers': [], 'client': ('test', 123), 'server': ('test', 80)},
                       receive, send)
        start = next(m for m in messages if m['type'] == 'http.response.start')
        body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
        return SimpleNamespace(status_code=start['status'],
                               headers={k.decode(): v.decode() for k, v in start['headers']},
                               json=lambda: json.loads(body))

    async def get(self, url, params=None):
        return await self.request('GET', url, params)

    async def post(self, url):
        return await self.request('POST', url)

    async def test_authenticated_get_contract_and_scenarios_without_network_or_postgres(self):
        with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')), \
             patch('psycopg.connect', side_effect=AssertionError('PostgreSQL forbidden')):
            for scenario, terminal, authority, revision in (
                ('PLAN', 'MODELED', 'RADIUS', 4),
                ('COMPENSATION', 'COMPENSATED', 'LOCAL', 5),
                ('RECONCILIATION', 'RECONCILIATION', 'RADIUS', 4),
            ):
                response = await self.client.get('/api/v1/aaa-demo/preview', params={'scenario': scenario})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                data = response.json()
                self.assertEqual(data['mode'], 'SYNTHETIC_FIXTURE_ONLY')
                self.assertEqual(data['account_id'], 'demo-sub-aaa-memory')
                self.assertEqual(data['events'][-1]['state'], terminal)
                self.assertEqual(data['result']['simulated_final_authority'], authority)
                self.assertEqual(data['result']['simulated_final_revision'], revision)
                self.assertFalse(data['result']['live_ready'])
                self.assertFalse(data['result']['external_writes'])
                self.assertEqual(len(data['fingerprint']), 64)
                self.assertTrue(all(e['correlation_id'] == data['correlation_id'] for e in data['events']))
                self.assertTrue(all(e['request_id'] == data['request_id'] for e in data['result']['expected_audit']))
                self.assertEqual(data, (await self.client.get('/api/v1/aaa-demo/preview', params={'scenario': scenario})).json())

    async def test_authentication_is_required_and_write_method_is_absent(self):
        def denied():
            raise HTTPException(401, 'Authentication required')
        self.app.dependency_overrides[current_demo_user] = denied
        self.assertEqual((await self.client.get('/api/v1/aaa-demo/preview')).status_code, 401)
        self.assertEqual((await self.client.post('/api/v1/aaa-demo/preview')).status_code, 405)

    async def test_unknown_scenario_rejected_and_cannot_select_existing_account(self):
        self.assertEqual((await self.client.get('/api/v1/aaa-demo/preview?scenario=LIVE')).status_code, 422)
        data = (await self.client.get('/api/v1/aaa-demo/preview?account_id=real-account')).json()
        self.assertEqual(data['account_id'], 'demo-sub-aaa-memory')
        with self.assertRaises(ValueError):
            fixture_preview('LIVE')
