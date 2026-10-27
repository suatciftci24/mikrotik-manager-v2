"""Synthetic memory-only mutation contract, authorization and atomicity tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from app.main import app
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_subscriptions import DemoSubscriptionStore, DemoChangeError
from app.schemas.subscriber_events import ExpiryChange


class DemoExpiryChanges(TestCase):
    def setUp(self):
        self.store = DemoSubscriptionStore(SUBSCRIBERS)
        self.mock_store = patch('app.services.demo_subscriptions.store', self.store)
        self.mock_store.start()
        self.addCleanup(self.mock_store.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.today = datetime.now(ZoneInfo('Europe/Istanbul')).date()

    def login(self):
        self.client.post('/api/v1/auth/login', json={'username': 'demo', 'password': 'demo-only'})
        self.addCleanup(lambda: self.client.post('/api/v1/auth/logout'))

    def payload(self, item_id='demo-sub-1001', **changes):
        item = self.store.detail(item_id)['item']
        return {**dict(expires_on=(self.today + timedelta(days=70)).isoformat(), expected_expires_on=item['expires_on'],
                       expected_revision=item['revision'], expected_source=item['source'] or 'LOCAL',
                       operation='RENEWAL', request_id=str(uuid4()), confirmed=True), **changes}

    def post(self, payload, item_id='demo-sub-1001'):
        return self.client.post(f'/api/v1/subscribers/{item_id}/demo-expiry', json=payload, headers={'X-V2-Demo-Action': 'expiry'})

    def test_auth_confirmation_and_payload_validation_do_not_mutate(self):
        payload = self.payload()
        self.assertEqual(self.post(payload).status_code, 401)
        self.login()
        self.assertEqual(self.client.post('/api/v1/subscribers/demo-sub-1001/demo-expiry', json=payload).status_code, 403)
        for changes in [{'confirmed': False}, {'status': 'ACTIVE'}, {'expires_on': ''}, {'expires_on': '2026-02-30'},
                        {'expires_on': 123}, {'expires_on': None}, {'expires_on': '2026-12-01T00:00:00Z'}, {'expected_revision': -1}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.post({**payload, **changes}).status_code, 422)
        self.assertEqual(self.store.detail('demo-sub-1001')['history'], [])

    def test_local_and_radius_changes_preserve_source_status_and_update_all_reads(self):
        self.login()
        for item_id in ['demo-sub-1001', 'demo-sub-1002']:
            before = self.store.detail(item_id)['item']
            response = self.post(self.payload(item_id), item_id)
            self.assertEqual(response.status_code, 200, response.text)
            detail = response.json()
            self.assertEqual(detail['item']['source'], before['source'])
            self.assertEqual(detail['item']['status'], before['status'])
            self.assertEqual(detail['item']['revision'], 1)
            self.assertEqual(detail['persistence'], 'process-memory')
            event = detail['history'][0]
            self.assertEqual(event['previous_expires_on'], before['expires_on'])
            self.assertEqual(event['expires_on'], detail['item']['expires_on'])
            self.assertEqual(event['operation'], 'RENEWAL')
            self.assertEqual(event['actor_id'], 'demo-user')
            self.assertEqual(datetime.fromisoformat(event['occurred_at']).utcoffset(), timedelta(0))
            self.assertEqual(self.client.get(f'/api/v1/subscribers/{item_id}').json(), detail)
            listed = next(row for row in self.client.get('/api/v1/subscribers').json()['items'] if row['id'] == item_id)
            self.assertEqual(listed, detail['item'])
            self.assertTrue(detail['is_demo'])

    def test_retries_are_idempotent_and_conflicting_or_stale_changes_fail(self):
        self.login()
        payload = self.payload()
        first = self.post(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.post(payload).json(), first.json())
        self.assertEqual(self.post({**payload, 'expires_on': (self.today + timedelta(days=71)).isoformat()}).status_code, 409)
        self.assertEqual(self.post({**payload, 'request_id': str(uuid4())}).status_code, 409)
        self.assertEqual(len(self.store.detail('demo-sub-1001')['history']), 1)

    def test_source_unknown_changed_source_and_missing_record_fail_closed(self):
        self.login()
        self.assertEqual(self.post(self.payload('demo-sub-1006'), 'demo-sub-1006').status_code, 409)
        self.assertEqual(self.post(self.payload(expected_source='RADIUS')).status_code, 409)
        self.assertEqual(self.post(self.payload(), 'missing').status_code, 404)
        self.assertEqual(self.store.detail('demo-sub-1001')['history'], [])

    def test_date_edit_today_past_same_date_and_renewal_direction(self):
        self.login()
        self.assertEqual(self.post(self.payload(expires_on=(self.today-timedelta(days=1)).isoformat())).status_code, 422)
        current = self.store.detail('demo-sub-1002')['item']['expires_on']
        self.assertEqual(self.post(self.payload('demo-sub-1002', expires_on=current), 'demo-sub-1002').status_code, 422)
        self.assertEqual(self.post(self.payload('demo-sub-1002', expires_on=self.today.isoformat()), 'demo-sub-1002').status_code, 422)
        response = self.post(self.payload('demo-sub-1002', expires_on=self.today.isoformat(), operation='DATE_EDIT'), 'demo-sub-1002')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['history'][0]['operation'], 'DATE_EDIT')
        self.assertEqual(response.json()['item']['expires_on'], self.today.isoformat())

    def test_known_source_can_set_unknown_date_but_unknown_source_cannot(self):
        rows = [{**SUBSCRIBERS[0], 'expires_on': None}]
        store = DemoSubscriptionStore(rows)
        payload = self.payload(expected_expires_on=None, operation='DATE_EDIT')
        result = store.change_expiry(rows[0]['id'], ExpiryChange.model_validate(payload), 'demo-user')
        self.assertIsNone(result['history'][0]['previous_expires_on'])
        self.assertEqual(DemoSubscriptionStore(rows).detail(rows[0]['id'])['history'], [])

    def test_concurrent_updates_publish_exactly_one_history_event(self):
        one = ExpiryChange.model_validate(self.payload())
        two = ExpiryChange.model_validate(self.payload(expires_on=(self.today+timedelta(days=71)).isoformat()))
        def attempt(payload):
            try:
                self.store.change_expiry('demo-sub-1001', payload, 'demo-user')
                return 200
            except DemoChangeError as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, [one, two]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(len(self.store.detail('demo-sub-1001')['history']), 1)

    def test_failure_before_publication_leaves_date_revision_and_history_unchanged(self):
        before = self.store.detail('demo-sub-1001')
        change = ExpiryChange.model_validate(self.payload())
        with patch('app.services.demo_subscriptions.deepcopy', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.store.change_expiry('demo-sub-1001', change, 'demo-user')
        self.assertEqual(self.store.detail('demo-sub-1001'), before)
        self.store.change_expiry('demo-sub-1001', change, 'demo-user')
        self.assertEqual(len(self.store.detail('demo-sub-1001')['history']), 1)

    def test_validation_uses_turkey_day_at_utc_midnight_boundary(self):
        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                fixed = datetime(2030, 1, 1, 21, 0, tzinfo=timezone.utc)
                return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
        self.login()
        with patch('app.services.demo_subscriptions.datetime', Frozen):
            self.assertEqual(self.post(self.payload(expires_on='2030-01-01')).status_code, 422)
            self.assertEqual(self.post(self.payload(expires_on='2030-01-02')).status_code, 200)
