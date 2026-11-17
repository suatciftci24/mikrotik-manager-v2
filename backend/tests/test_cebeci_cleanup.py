"""Retired public surface and fail-closed isolation; no DB or network IO."""
import os
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from app.api.v1 import router_registry, system
from app.core import v26_cebeci
from app.services.router_registry import storage_boundary


class CleanupTests(TestCase):
    def test_retired_routes_are_absent_and_general_routes_remain(self):
        paths = {route.path for route in router_registry.router.routes}
        self.assertFalse(any('cebeci' in path or 'read-only' in path for path in paths))
        for suffix in ('/options', '/inventory', '/verify', '/register', '/{id}/check'):
            self.assertIn('/router-registry' + suffix, paths)
        self.assertFalse(any('cebeci' in route.path for route in system.router.routes))

    def test_retired_capability_rejects_stale_enabled_or_operator_config(self):
        v26_cebeci.validate({})
        v26_cebeci.validate({v26_cebeci.FLAG: 'false'})
        for values in ({v26_cebeci.FLAG: 'true'}, {v26_cebeci.OPERATOR: 'stale'},
                       {v26_cebeci.REVISION: '0'}):
            with self.subTest(values=values), self.assertRaises(RuntimeError):
                v26_cebeci.validate(values)

    def test_v26_storage_guard_runs_before_service(self):
        service = MagicMock()
        method = Mock(return_value='ok')
        with patch.dict(os.environ, {'V2_DEPLOYMENT_PROFILE': 'v26-isolated-acceptance'}), \
             patch('app.services.router_workspace.guard', side_effect=RuntimeError('ISOLATION_STOP')) as guard:
            with self.assertRaisesRegex(RuntimeError, 'ISOLATION_STOP'):
                storage_boundary(method)(service)
        guard.assert_called_once()
        method.assert_not_called()
