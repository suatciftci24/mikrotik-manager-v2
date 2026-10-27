"""Socketless contract/security checks; not HTTP integration tests."""
from unittest import TestCase
from fastapi.routing import APIRoute
from pydantic import ValidationError
from app.main import app
from app.api.v1.router_events import list_router_events, router
from app.core.security import current_demo_user
from app.schemas.router_events import RouterEvent, RouterEventList


class RouterEventContract(TestCase):
    def test_unavailable_source_never_creates_fixtures_or_known_zero_coverage(self):
        result = list_router_events({'is_demo': True})
        self.assertEqual(result.model_dump(), {'items': [], 'available': False, 'is_demo': True})
        self.assertEqual(result, list_router_events({'is_demo': True}))
        RouterEventList.model_validate(result)

    def test_only_authenticated_read_route_is_registered(self):
        route = next(route for route in router.routes if isinstance(route, APIRoute) and route.path == '/router-events')
        self.assertEqual(route.methods, {'GET'})
        self.assertIn(current_demo_user, [dep.call for dep in route.dependant.dependencies])
        schema = app.openapi()
        self.assertIn('RouterEventList', schema['components']['schemas'])
        self.assertIn('/api/v1/router-events', schema['paths'])

    def test_contract_never_accepts_non_demo_or_unknown_event_types(self):
        base = dict(id='test-event', router_id='demo-router-001', kind='INTERNET_DOWN', is_demo=True)
        for changes in ({'is_demo': False}, {'kind': 'GUESS_FROM_LAST_SEEN'}):
            with self.assertRaises(ValidationError):
                RouterEvent.model_validate({**base, **changes})
