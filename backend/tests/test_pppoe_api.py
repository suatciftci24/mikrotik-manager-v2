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

    def test_observation_time_unknown_fresh_stale_and_utc(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        for stamp, state in ((None, 'UNKNOWN'), ((now-timedelta(seconds=10)).isoformat(), 'FRESH'),
                             ((now-timedelta(minutes=6)).isoformat(), 'STALE'),
                             ((now-timedelta(seconds=10)).astimezone(timezone(timedelta(hours=3))).isoformat(), 'FRESH')):
            binding = self.binding([dict(account_id='account-local', source='LOCAL', observed_at=stamp)])
            result = snapshot(binding.router_id, is_demo=False, binding=binding)
            self.assertEqual(result.items[0].source_status, state)
            if stamp is None:
                self.assertIsNone(result.items[0].observed_at)
            else:
                self.assertEqual(result.items[0].observed_at.utcoffset(), timedelta(0))

    def test_invalid_naive_future_time_rejects_entire_result(self):
        for stamp in ('invalid', '2026-01-01T00:00:00', '2999-01-01T00:00:00Z', 123, True):
            binding = self.binding([dict(account_id='account-radius', source='RADIUS'),
                dict(account_id='account-local', source='LOCAL', observed_at=stamp)])
            result = snapshot(binding.router_id, is_demo=False, binding=binding)
            self.assertEqual(result.error, 'INVALID_DATA')
            self.assertEqual(result.items, [])

    def test_router_source_and_account_scope_preserve_authority(self):
        binding = self.binding([dict(account_id='account-local', source='LOCAL'),
                                dict(account_id='account-radius', source='RADIUS')])
        result = snapshot(binding.router_id, is_demo=False, binding=binding, source='RADIUS')
        self.assertEqual([row.account_id for row in result.items], ['account-radius'])
        self.assertEqual(result.selected_source, 'RADIUS')
        self.transport.reset_mock()
        for account, source in (('missing', 'LOCAL'), ('account-local', 'RADIUS')):
            result = snapshot(binding.router_id, is_demo=False, binding=binding, source=source, account_id=account)
            self.assertEqual(result.error, 'AUTHORITY_MISMATCH')
        self.transport.read_pppoe.assert_not_called()

    def test_last_success_is_scoped_monotonic_and_not_a_cached_session(self):
        from datetime import datetime, timezone, timedelta
        at = datetime.now(timezone.utc)-timedelta(minutes=1)
        binding = self.binding([dict(account_id='account-local', source='LOCAL', observed_at=at)])
        options = dict(is_demo=False, binding=binding, source='LOCAL', account_id='account-local')
        self.assertEqual(snapshot(binding.router_id, **options).last_successful_observed_at, at)
        self.transport.read_pppoe.side_effect = TimeoutError('private')
        failure = snapshot(binding.router_id, **options)
        self.assertEqual(failure.error, 'TIMEOUT')
        self.assertEqual(failure.items, [])
        self.assertEqual(failure.last_successful_observed_at, at)
        other = snapshot(binding.router_id, is_demo=False, binding=binding, source='RADIUS')
        self.assertIsNone(other.last_successful_observed_at)
        self.transport.read_pppoe.side_effect = None
        self.transport.read_pppoe.return_value = [dict(account_id='account-local', source='LOCAL',
                                                       observed_at=at-timedelta(minutes=10))]
        result = snapshot(binding.router_id, **options)
        self.assertEqual(result.last_successful_observed_at, at)
        self.assertEqual(result.items[0].source_status, 'STALE')
        self.transport.read_pppoe.return_value = []
        result = snapshot(binding.router_id, **options)
        self.assertEqual(result.items, [])
        self.assertEqual(result.last_successful_observed_at, at)

    def test_subscriber_api_authorizes_router_before_scoped_read(self):
        from app.api.v1.subscriber_center import pppoe_observations
        binding = self.binding([dict(account_id='account-local', source='LOCAL'),
                                dict(account_id='account-radius', source='RADIUS')])
        with patch.object(routes, 'detail', side_effect=HTTPException(403)):
            with self.assertRaises(HTTPException):
                pppoe_observations(binding.router_id, 'account-local', 'LOCAL', {}, binding)
        self.transport.read_pppoe.assert_not_called()
        with patch.object(routes, 'detail', return_value=Mock(is_demo=True)):
            result = pppoe_observations(binding.router_id, 'account-local', 'LOCAL', {}, binding)
            self.assertEqual(result.error, 'DEMO_ISOLATED')
        self.transport.read_pppoe.assert_not_called()
        with patch.object(routes, 'detail', return_value=Mock(is_demo=False)):
            result = pppoe_observations(binding.router_id, 'account-local', 'LOCAL', {}, binding)
            self.assertEqual([row.account_id for row in result.items], ['account-local'])

    def test_subscriber_openapi_is_read_only_authenticated_and_closed(self):
        from app.main import app
        from app.api.v1.subscriber_center import router
        from app.core.security import current_demo_user
        path = '/subscriber-observations/{router_id}/{account_id}'
        spec = app.openapi()['paths']['/api/v1'+path]
        self.assertEqual(set(spec), {'get'})
        source = next(p for p in spec['get']['parameters'] if p['name'] == 'source')
        self.assertTrue(source['required'])
        route = next(r for r in router.routes if r.path == path)
        calls = {d.call for d in route.dependant.dependencies}
        self.assertIn(current_demo_user, calls)
        self.assertIn(disabled_binding, calls)

    def test_elapsed_deadline_and_direct_settings_validation(self):
        from dataclasses import replace
        binding = self.binding([])
        with patch('app.adapters.pppoe_readonly.monotonic', side_effect=[10, 13]):
            self.assertEqual(snapshot(binding.router_id, is_demo=False, binding=binding).error, 'TIMEOUT')
        self.transport.reset_mock()
        for timeout in (float('nan'), float('inf'), 0, 11):
            result = snapshot(binding.router_id, is_demo=False,
                              binding=replace(binding, settings=replace(binding.settings, timeout_seconds=timeout)))
            self.assertEqual(result.error, 'INVALID_DATA')
        self.transport.read_pppoe.assert_not_called()
