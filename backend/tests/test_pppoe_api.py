"""Synthetic API integration; no sockets, DB, router or RADIUS transport."""
from unittest import TestCase
from unittest.mock import Mock, patch
from fastapi import HTTPException
from pydantic import SecretStr
from app.api.v1 import router_center as routes
from app.adapters.pppoe_readonly import PppoeReadAdapter, RouterReadSettings
from app.services.pppoe_readonly import PppoeReadBinding, disabled_binding, snapshot


class PppoeApiTests(TestCase):
    def binding(self, rows):
        self.transport = Mock()
        self.transport.read_pppoe.return_value = rows
        return PppoeReadBinding('registered-test', PppoeReadAdapter(self.transport),
            RouterReadSettings('192.0.2.1', 'fixture', SecretStr('synthetic-secret'), 'fixture-ca', 'a'*64),
            {'account-local': 'LOCAL', 'account-radius': 'RADIUS'})

    def test_default_and_demo_never_dispatch(self):
        binding = self.binding([])
        self.assertIsNone(disabled_binding())
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            self.assertEqual(snapshot(binding.router_id, is_demo=False, binding=None).error, 'DISABLED')
            self.assertEqual(snapshot(binding.router_id, is_demo=True, binding=binding).error, 'DEMO_ISOLATED')
            self.assertEqual(snapshot('other-router', is_demo=False, binding=binding).error, 'DISABLED')
        self.transport.read_pppoe.assert_not_called()

    def test_explicit_authorities_and_unknown_session_preserved(self):
        binding = self.binding([dict(account_id='account-local', source='LOCAL', connected=True),
                                dict(account_id='account-radius', source='RADIUS')])
        result = snapshot(binding.router_id, is_demo=False, binding=binding)
        self.assertEqual(result.availability, 'AVAILABLE')
        self.assertIsNone(result.items[1].connected)
        self.assertFalse(result.is_demo)
        self.transport.read_pppoe.assert_called_once()

    def test_mismatch_unknown_id_and_errors_never_publish_partial_rows(self):
        for row in (dict(account_id='account-local', source='RADIUS'), dict(account_id='unknown', source='LOCAL')):
            binding = self.binding([dict(account_id='account-radius', source='RADIUS'), row])
            result = snapshot(binding.router_id, is_demo=False, binding=binding)
            self.assertEqual(result.error, 'AUTHORITY_MISMATCH'); self.assertEqual(result.items, [])
        binding = self.binding([])
        self.transport.read_pppoe.side_effect = TimeoutError('private')
        result = snapshot(binding.router_id, is_demo=False, binding=binding)
        self.assertEqual(result.error, 'TIMEOUT'); self.assertNotIn('private', result.model_dump_json())

    def test_route_authorizes_before_dispatch_and_preserves_demo_source(self):
        binding = self.binding([])
        with patch.object(routes, 'detail', side_effect=HTTPException(404)):
            with self.assertRaises(HTTPException): routes.pppoe_observations(binding.router_id, {}, binding)
        self.transport.read_pppoe.assert_not_called()
        with patch.object(routes, 'detail', return_value=Mock(is_demo=True)):
            self.assertEqual(routes.pppoe_observations(binding.router_id, {}, binding).error, 'DEMO_ISOLATED')
        with patch.object(routes, 'detail', return_value=Mock(is_demo=False)):
            self.assertEqual(routes.pppoe_observations(binding.router_id, {}, binding).availability, 'AVAILABLE')

    def test_openapi_get_only_authenticated_default_closed(self):
        from app.main import app
        from app.core.security import current_demo_user
        path = '/api/v1/router-center/{id}/pppoe-observations'
        self.assertEqual(set(app.openapi()['paths'][path]), {'get'})
        route = next(route for route in routes.router.routes if getattr(route, 'path', None) == '/router-center/{id}/pppoe-observations')
        calls = {dep.call for dep in route.dependant.dependencies}
        self.assertIn(current_demo_user, calls); self.assertIn(disabled_binding, calls)
