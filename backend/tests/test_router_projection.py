"""Read-only router association projection; no HTTP, DB or device IO."""
from unittest import TestCase
from unittest.mock import patch
from app.services.details import router_detail
from app.services.demo_data import ROUTERS


class RouterProjection(TestCase):
    def test_saved_router_id_wins_over_legacy_display_name(self):
        router = ROUTERS[0]
        rows = [
            {'id': 'by-id', 'router_id': router['id'], 'router_name': 'Önceki ad'},
            {'id': 'legacy', 'router_name': router['name']},
            {'id': 'other-id', 'router_id': 'demo-router-other', 'router_name': router['name']},
            {'id': 'other-name', 'router_name': 'Başka router'},
        ]
        with patch('app.services.demo_subscriptions.store') as store:
            store.list_items.return_value = rows
            detail = router_detail(router['id'])
        self.assertEqual([row['id'] for row in detail['assigned_subscribers']], ['by-id', 'legacy'])
        self.assertEqual(detail['item'], router)
        self.assertTrue(detail['is_demo'])
        self.assertEqual(rows[0]['router_name'], 'Önceki ad')

    def test_missing_router_never_reads_subscriber_storage(self):
        with patch('app.services.demo_subscriptions.store') as store:
            self.assertIsNone(router_detail('missing'))
            store.list_items.assert_not_called()
