from app.services.identity import bootstrap,public_user
"""Seed/projection regression checks, no PostgreSQL or sockets."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from types import SimpleNamespace
from sqlalchemy.engine import make_url
from app.demo_storage import initialize_demo, seed_examples, validated_snapshots
from app.services.demo_examples import demo_examples
from app.services.demo_data import SUBSCRIBERS
from app.services.demo_reports import router_event_records
from app.services.details import router_detail


class FakeConnection:
    def __init__(self):
        self.items = {}
        self.events = {}
        self.requests = {}
        self.marker = False
        self.exists = False

    def execute(self, sql, parameters=None):
        query = str(sql)
        result = MagicMock()
        if 'to_regnamespace' in query:
            result.scalar_one.return_value = 'v2_demo' if self.exists else None
        elif 'SELECT marker' in query:
            result.scalar_one.return_value = 'mikrotik-manager-v2-synthetic-only'
        elif query.startswith('SELECT payload, revision'):
            item = self.items.get(parameters['id'])
            result.mappings.return_value.one_or_none.return_value = {'payload': deepcopy(item), 'revision': item['revision']} if item else None
        elif query.startswith('SELECT payload FROM'):
            result.scalars.return_value = list(deepcopy(self.items).values())
        elif query.startswith('INSERT INTO v2_demo.subscribers'):
            import json
            key = parameters['id']
            if key in self.items:
                raise AssertionError('Duplicate seed subscriber insert')
            self.items[key] = json.loads(parameters['payload'])
        elif query.startswith('INSERT INTO v2_demo.events'):
            if parameters['id'] in self.events:
                raise AssertionError('Duplicate seed history insert')
            self.events[parameters['id']] = deepcopy(parameters)
        elif query.startswith('INSERT INTO v2_demo.requests'):
            if parameters['id'] in self.requests:
                raise AssertionError('Duplicate seed request insert')
            self.requests[parameters['id']] = deepcopy(parameters)
        elif 'CREATE SCHEMA v2_demo' in query:
            self.exists = True
        return result


def fake_engine():
    connection = FakeConnection()
    @contextmanager
    def begin():
        yield connection
    return SimpleNamespace(url=make_url('postgresql+psycopg://v2_local:v2_local@127.0.0.1:55432/mikrotik_manager_v2'), begin=begin), connection


class DemoIntegrationSeed(TestCase):
    def test_initialization_inserts_each_subscriber_once_and_never_reseeds(self):
        engine, connection = fake_engine()
        self.assertTrue(initialize_demo(engine))
        self.assertEqual(set(connection.items), {row['id'] for row in SUBSCRIBERS})
        self.assertFalse(initialize_demo(engine))
        self.assertEqual(len(connection.items), len(SUBSCRIBERS))

    def test_additive_seed_is_idempotent_and_preserves_edited_user_rows(self):
        engine, connection = fake_engine()
        initialize_demo(engine)
        original = deepcopy(connection.items)
        self.assertEqual(seed_examples(engine), 2)
        samples = validated_snapshots(demo_examples())
        self.assertEqual(len(connection.events), 8)
        self.assertEqual(len(connection.requests), 8)
        for key, value in original.items():
            self.assertEqual(connection.items[key], value)
        sample_id = samples[0]['item']['id']
        connection.items[sample_id]['customer_name'] = 'Kullanıcı düzenlemesi'
        before = deepcopy((connection.items, connection.events, connection.requests))
        self.assertEqual(seed_examples(engine), 0)
        self.assertEqual((connection.items, connection.events, connection.requests), before)

    def test_existing_username_is_not_overwritten_or_duplicated(self):
        engine, connection = fake_engine()
        initialize_demo(engine)
        connection.items['demo-sub-1001']['username'] = 'demo.integration.1'
        self.assertEqual(seed_examples(engine), 1)
        self.assertEqual(connection.items['demo-sub-1001']['username'], 'demo.integration.1')

    def test_seed_reports_and_router_events_share_persisted_identity(self):
        samples = validated_snapshots(demo_examples())
        items = [sample['item'] for sample in samples]
        events = router_event_records(items)
        self.assertTrue(events.available)
        self.assertEqual(len(events.items), 5)
        from datetime import datetime
        ongoing = next(event for event in events.items if event.state == 'OPEN')
        ongoing_report = next(item['demo_report'] for item in items if item['router_id'] == ongoing.router_id)
        self.assertTrue(all(datetime.fromisoformat(sample['measured_at'].replace('Z','+00:00')) < datetime.fromisoformat(ongoing.occurred_at) for sample in ongoing_report['traffic']))
        self.assertEqual(len({event.id for event in events.items}), 5)
        for sample in samples:
            report = sample['item']['demo_report']
            self.assertEqual(report['subscriber_id'], sample['item']['id'])
            self.assertEqual(report['router_id'], sample['item']['router_id'])
            self.assertEqual({event['operation'] for event in sample['history']}, {'CREATE', 'PLAN_CHANGE', 'STATUS_CHANGE', 'RENEWAL'})
        with patch('app.services.demo_subscriptions.store') as store:
            store.list_items.return_value = items
            from app.api.v1.router_events import list_router_events
            self.assertEqual(list_router_events(public_user(bootstrap())), events)
            detail = router_detail(items[0]['router_id'])
            self.assertEqual(detail['assigned_subscribers'], [items[0]])
            self.assertEqual(detail['item']['wan_snapshot']['ip'], '192.0.2.101')

    def test_report_identity_mismatch_is_rejected(self):
        from pydantic import ValidationError
        samples = demo_examples()
        samples[0]['item']['demo_report']['subscriber_id'] = 'wrong'
        with self.assertRaises(ValidationError):
            validated_snapshots(samples)

    def test_management_and_renewal_preserve_report_and_reconstruct_history(self):
        from app.schemas.subscriber_management import SubscriberChange
        from app.schemas.subscriber_events import ExpiryChange
        from app.services.demo_management import calculate_management_change
        from app.services.demo_subscriptions import calculate_change
        from datetime import date, timedelta
        from uuid import uuid4
        sample = validated_snapshots(demo_examples())[0]
        before = deepcopy(sample['item']['demo_report'])
        item = sample['item']
        command = SubscriberChange.model_validate(dict(operation='STATUS_CHANGE',value='PAUSED',expected_value=item['status'],expected_revision=item['revision'],expected_source=item['source'],request_id=str(uuid4()),confirmed=True))
        item, event = calculate_management_change(item,command,'demo-user')
        sample['history'].insert(0,event)
        command = ExpiryChange.model_validate(dict(operation='RENEWAL',expires_on=(date.fromisoformat(item['expires_on'])+timedelta(days=30)).isoformat(),expected_expires_on=item['expires_on'],expected_revision=item['revision'],expected_source=item['source'],request_id=str(uuid4()),confirmed=True))
        item,event = calculate_change(item,command,'demo-user')
        sample['item']=item
        sample['history'].insert(0,event)
        self.assertEqual(validated_snapshots([sample])[0]['item']['demo_report'],before)
        self.assertEqual(item['revision'],6)
